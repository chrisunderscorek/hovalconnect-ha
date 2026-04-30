"""Hoval Connect API client."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

from .const import (
    API_CIRCUITS,
    API_BUSINESS_CIRCUIT_DETAIL,
    API_LIVE_VALUES,
    API_MY_PLANTS,
    API_PLANT_SETTINGS,
    API_SET_PROGRAM,
    API_TEMP_CHANGE,
    AUTH_TOKEN_URL,
    CLIENT_ID,
    CONF_TOKEN_EXPIRES_AT,
    CONF_TOKEN_ISSUED_AT,
    CONF_TOKEN_RENEW_AFTER,
    DEFAULT_FRONTEND_APP_VERSION,
    FRONTEND_VERSION_CHECK_INTERVAL_SECONDS,
    GOOGLE_PLAY_APP_URL,
    TOKEN_RENEWAL_RETRY_BACKOFF_SECONDS,
    TOKEN_RENEWAL_SAFETY_MARGIN_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

BASE_APP_HEADERS = {
    "User-Agent": "HovalConnect/6022 CFNetwork/3860.400.51 Darwin/25.3.0",
    "Accept": "application/json",
    "x-requested-with": "XMLHttpRequest",
}
STORE_HEADERS = {
    "User-Agent": BASE_APP_HEADERS["User-Agent"],
    "Accept": "text/html,application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

API_SET_CONSTANT = "https://azure-iot-prod.hoval.com/core/v3/plants/{plant_id}/circuits/{path}/programs"

class HovalAuthError(Exception):
    pass

class HovalAPIError(Exception):
    pass

def _looks_like_jwt(token: str | None) -> bool:
    return bool(token and token.count(".") == 2)

def _api_bearer_token(data: dict) -> str | None:
    id_token = data.get("id_token")
    access_token = data.get("access_token")

    # SAP IAS may return an opaque OAuth access_token. The Hoval core API expects
    # a JWT-shaped bearer and otherwise returns "Malformed token", so prefer the
    # id_token when it is the JWT-shaped token in the response.
    if _looks_like_jwt(id_token):
        return id_token
    if _looks_like_jwt(access_token):
        return access_token
    return id_token or access_token

def _parse_google_play_version(html: str) -> str | None:
    # Google Play does not expose a stable unauthenticated version API. These
    # patterns target the embedded app detail data and intentionally fail closed
    # so the integration can keep using DEFAULT_FRONTEND_APP_VERSION.
    patterns = (
        r'"141":\[\[\["([0-9]+(?:\.[0-9]+)+)"\]\]',
        r'\[\[\["([0-9]+(?:\.[0-9]+)+)"\]\],\[\[\[[0-9]+\]\]',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None

def _retry_after_seconds(headers) -> float | None:
    if not headers:
        return None

    value = headers.get("Retry-After")
    if not value:
        return None

    value = value.strip()
    if value.isdecimal():
        return max(0.0, float(value))

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())

class HovalConnectAPI:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_issued_at: float | None = None,
        token_expires_at: float | None = None,
        token_renew_after: float | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._email = email
        self._password = password
        self._token_issued_at_epoch: float = float(token_issued_at or 0.0)
        self._expires_at_epoch: float = float(token_expires_at or 0.0)
        self._renew_after_epoch: float = float(token_renew_after or 0.0)
        if access_token:
            now_epoch = time.time()
            now_monotonic = time.monotonic()
            if not self._token_issued_at_epoch:
                self._token_issued_at_epoch = now_epoch
            if not self._expires_at_epoch:
                self._expires_at_epoch = now_epoch + 1800
            if not self._renew_after_epoch:
                lifetime = max(60.0, self._expires_at_epoch - self._token_issued_at_epoch)
                self._renew_after_epoch = self._token_issued_at_epoch + (lifetime / 2)
            self._expires_at = now_monotonic + max(0.0, self._expires_at_epoch - now_epoch)
            self._renew_after = now_monotonic + max(0.0, self._renew_after_epoch - now_epoch)
        else:
            self._expires_at = 0.0
            self._renew_after = 0.0
        self._plant_token: str | None = None
        self._plant_token_expires: float = 0.0
        self._on_token_refresh = None  # callback(auth_data)
        self._next_token_retry_at: float = 0.0
        self._token_renewal_retry_count: int = 0
        self._frontend_app_version = DEFAULT_FRONTEND_APP_VERSION
        self._startup_monotonic = time.monotonic()
        self._last_frontend_version_check_slot: int | None = None
        self._last_frontend_version_skip_warning_slot: int | None = None

    def _app_headers(self) -> dict:
        return {
            **BASE_APP_HEADERS,
            "hovalconnect-frontend-app-version": self._frontend_app_version,
        }

    def _auth_headers(self) -> dict:
        return {**self._app_headers(), "Authorization": f"Bearer {self._access_token}"}

    def _plant_headers(self, plant_token: str) -> dict:
        return {**self._auth_headers(), "x-plant-access-token": plant_token}

    def _frontend_version_check_slot(self) -> int:
        # Slotting from integration startup spreads checks naturally across
        # users instead of making every installation check at a wall-clock time.
        elapsed = max(0.0, time.monotonic() - self._startup_monotonic)
        return int(elapsed // FRONTEND_VERSION_CHECK_INTERVAL_SECONDS)

    async def _fetch_google_play_frontend_version(self) -> tuple[str | None, str | None]:
        timeout = aiohttp.ClientTimeout(total=8)
        async with self._session.get(GOOGLE_PLAY_APP_URL, headers=STORE_HEADERS, timeout=timeout) as resp:
            if resp.status >= 400:
                return None, f"HTTP {resp.status}"
            text = await resp.text()

        version = _parse_google_play_version(text)
        if not version:
            return None, "Version not found"
        return version, None

    async def async_update_frontend_app_version(self, reason: str, force: bool = False) -> bool:
        slot = self._frontend_version_check_slot()
        if not force and self._last_frontend_version_check_slot == slot:
            # 426 may repeat on every polling cycle. Keep one visible warning per
            # slot, then wait for the next 6-hour window before probing again.
            if self._last_frontend_version_skip_warning_slot != slot:
                self._last_frontend_version_skip_warning_slot = slot
                _LOGGER.warning(
                    "HovalConnect frontend app version check skipped after %s: already checked in "
                    "6-hour slot %s since integration start. Default=%s, effective=%s. "
                    "If Hoval requires a newer app version, functionality may remain limited until "
                    "the next 6-hour slot.",
                    reason,
                    slot,
                    DEFAULT_FRONTEND_APP_VERSION,
                    self._frontend_app_version,
                )
            return False

        self._last_frontend_version_check_slot = slot
        previous_version = self._frontend_app_version
        found_version: str | None = None
        error: str | None = None

        try:
            found_version, error = await self._fetch_google_play_frontend_version()
        except Exception as err:
            error = str(err)

        if found_version:
            self._frontend_app_version = found_version

        _LOGGER.warning(
            "HovalConnect frontend app version check (%s): default=%s, google_play=%s, "
            "effective=%s%s. This integration emulates the official HovalConnect app version; "
            "Hoval may require a newer frontend version after app updates and functionality may "
            "be limited until the version is refreshed. The check runs at integration startup and "
            "after HTTP 426 at most once per 6 hours calculated from this integration start.",
            reason,
            DEFAULT_FRONTEND_APP_VERSION,
            found_version or "<not found>",
            self._frontend_app_version,
            f", error={error}" if error else "",
        )
        return self._frontend_app_version != previous_version

    async def _handle_upgrade_required(self, body: str) -> bool:
        _LOGGER.warning("Hoval API returned HTTP 426 Upgrade Required: %s", body or "<empty body>")
        return await self.async_update_frontend_app_version(reason="http_426", force=False)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers_factory,
        empty_statuses: set[int] | None = None,
        **kwargs,
    ):
        retry_on_426 = True
        while True:
            async with self._session.request(method, url, headers=headers_factory(), **kwargs) as resp:
                if empty_statuses and resp.status in empty_statuses:
                    return {}
                if resp.status == 426 and retry_on_426:
                    body = await resp.text()
                    retry_on_426 = False
                    # A 426 normally means Hoval bumped the accepted frontend
                    # app version. Re-check the store version and retry once if
                    # the effective header changed.
                    if await self._handle_upgrade_required(body):
                        continue
                resp.raise_for_status()
                return await resp.json(content_type=None)

    async def _request_no_json(
        self,
        method: str,
        url: str,
        *,
        headers_factory,
        **kwargs,
    ) -> None:
        retry_on_426 = True
        while True:
            async with self._session.request(method, url, headers=headers_factory(), **kwargs) as resp:
                if resp.status == 426 and retry_on_426:
                    body = await resp.text()
                    retry_on_426 = False
                    if await self._handle_upgrade_required(body):
                        continue
                resp.raise_for_status()
                return

    def set_token_refresh_callback(self, callback) -> None:
        """Called whenever tokens are refreshed — use to persist new tokens."""
        self._on_token_refresh = callback

    def auth_data(self) -> dict:
        """Return token data that can be persisted in the config entry."""
        data = {}
        if self._access_token:
            data["access_token"] = self._access_token
        if self._refresh_token:
            data["refresh_token"] = self._refresh_token
        if self._token_issued_at_epoch:
            data[CONF_TOKEN_ISSUED_AT] = self._token_issued_at_epoch
        if self._expires_at_epoch:
            data[CONF_TOKEN_EXPIRES_AT] = self._expires_at_epoch
        if self._renew_after_epoch:
            data[CONF_TOKEN_RENEW_AFTER] = self._renew_after_epoch
        return data

    def _set_auth_tokens(self, data: dict, default_expires_in: int) -> None:
        token = _api_bearer_token(data)
        if not token:
            raise HovalAPIError("Auth response missing token")

        expires_in = int(data.get("expires_in", default_expires_in))
        lifetime = max(60, expires_in - TOKEN_RENEWAL_SAFETY_MARGIN_SECONDS)
        renew_after = max(30, lifetime / 2)
        now_monotonic = time.monotonic()
        now_epoch = time.time()
        self._access_token = token
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_issued_at_epoch = now_epoch
        self._expires_at_epoch = now_epoch + lifetime
        self._renew_after_epoch = now_epoch + renew_after
        self._expires_at = now_monotonic + lifetime
        self._renew_after = now_monotonic + renew_after
        self._next_token_retry_at = 0.0
        self._token_renewal_retry_count = 0
        self._plant_token = None

        if self._on_token_refresh:
            self._on_token_refresh(self.auth_data())

    def _token_renewal_retry_delay(self, err: Exception) -> float:
        index = min(self._token_renewal_retry_count, len(TOKEN_RENEWAL_RETRY_BACKOFF_SECONDS) - 1)
        local_delay = float(TOKEN_RENEWAL_RETRY_BACKOFF_SECONDS[index])
        self._token_renewal_retry_count += 1

        # RFC 9110 defines Retry-After as the server hint for when the next
        # follow-up request should happen. If Hoval/SAP sends it, never retry
        # earlier than that, but keep our local staged backoff as the floor.
        retry_after = _retry_after_seconds(getattr(err, "headers", None))
        if retry_after is None:
            return local_delay
        return max(local_delay, retry_after)

    async def _request_password_token(self) -> None:
        if not self._email or not self._password:
            raise HovalAuthError("Stored token expired; re-authentication required")

        async with self._session.post(
            AUTH_TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "username": self._email,
                "password": self._password,
                "scope": "openid offline_access",
            },
            headers={**self._app_headers(), "Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            if resp.status in (400, 401, 403):
                raise HovalAuthError("Invalid credentials")
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        self._set_auth_tokens(data, default_expires_in=1800)

    async def _request_refresh_token(self) -> None:
        async with self._session.post(
            AUTH_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token, "client_id": CLIENT_ID},
            headers={**self._app_headers(), "Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            if resp.status in (400, 401, 403):
                raise HovalAuthError("Refresh token expired")
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        self._set_auth_tokens(data, default_expires_in=1800)

    async def _renew_access_token(self) -> None:
        if self._refresh_token:
            try:
                await self._request_refresh_token()
                return
            except HovalAuthError:
                if not (self._email and self._password):
                    raise
                _LOGGER.debug("Refresh token failed, falling back to stored credentials")

        await self._request_password_token()

    async def _ensure_access_token(self) -> None:
        now = time.monotonic()
        has_valid_token = bool(self._access_token and now < self._expires_at)
        can_renew = bool(self._refresh_token or (self._email and self._password))

        if has_valid_token and now < self._renew_after:
            return

        if not can_renew:
            if has_valid_token:
                return
            raise HovalAuthError("Stored token expired; re-authentication required")

        if has_valid_token and now < self._next_token_retry_at:
            return

        try:
            await self._renew_access_token()
        except (HovalAuthError, HovalAPIError, aiohttp.ClientError) as err:
            if has_valid_token:
                retry_delay = self._token_renewal_retry_delay(err)
                self._next_token_retry_at = now + retry_delay
                _LOGGER.warning(
                    "Token renewal failed; retrying in %.0f seconds while existing token remains valid: %s",
                    retry_delay,
                    err,
                )
                return
            raise

    async def _ensure_plant_token(self, plant_id: str) -> str:
        if self._plant_token and time.monotonic() < self._plant_token_expires:
            return self._plant_token
        await self._ensure_access_token()
        data = await self._request_json(
            "GET",
            API_PLANT_SETTINGS.format(plant_id=plant_id),
            headers_factory=self._auth_headers,
        )
        self._plant_token = data["token"]
        self._plant_token_expires = time.monotonic() + 800
        return self._plant_token

    async def _h(self, plant_id: str) -> dict:
        pt = await self._ensure_plant_token(plant_id)
        return self._plant_headers(pt)

    async def get_plants(self) -> list[dict]:
        await self._ensure_access_token()
        return await self._request_json(
            "GET",
            API_MY_PLANTS,
            headers_factory=self._auth_headers,
        )

    async def get_circuits(self, plant_id: str) -> list[dict]:
        async def _get_once() -> list[dict]:
            plant_token = await self._ensure_plant_token(plant_id)
            return await self._request_json(
                "GET",
                API_CIRCUITS.format(plant_id=plant_id),
                headers_factory=lambda: self._plant_headers(plant_token),
            )

        try:
            return await _get_once()
        except aiohttp.ClientResponseError as err:
            if err.status != 401:
                raise
            # Token expired — force refresh of both tokens and retry once
            _LOGGER.debug("401 on circuits, forcing token refresh")
            self._expires_at = 0.0
            self._renew_after = 0.0
            self._next_token_retry_at = 0.0
            self._plant_token = None
            return await _get_once()

    async def get_live_values(self, plant_id: str, circuit_path: str, circuit_type: str) -> dict:
        """Live-Werte für einen Circuit: Temp, Modulation, Betriebsstunden etc."""
        plant_token = await self._ensure_plant_token(plant_id)
        url = f"{API_LIVE_VALUES.format(plant_id=plant_id)}?circuitPath={circuit_path}&circuitType={circuit_type}"
        data = await self._request_json(
            "GET",
            url,
            headers_factory=lambda: self._plant_headers(plant_token),
            empty_statuses={404, 502},
        )
        # Convert list of {key, value} to dict
        return {item["key"]: item["value"] for item in data if "key" in item}

    async def get_business_circuit_detail(self, plant_id: str, circuit_path: str) -> dict:
        """Read the business circuit detail tree for stable internal datapoints."""
        plant_token = await self._ensure_plant_token(plant_id)
        return await self._request_json(
            "GET",
            API_BUSINESS_CIRCUIT_DETAIL.format(plant_id=plant_id, path=circuit_path),
            headers_factory=lambda: self._plant_headers(plant_token),
            empty_statuses={404, 417, 502},
        )

    async def set_temporary_change(self, plant_id: str, path: str, value: float, duration: str = "fourHours") -> None:
        """Temporary temperature change (weekly program continues)."""
        plant_token = await self._ensure_plant_token(plant_id)
        await self._request_no_json(
            "POST",
            API_TEMP_CHANGE.format(plant_id=plant_id, path=path),
            json={"duration": duration, "value": value},
            headers_factory=lambda: {**self._plant_headers(plant_token), "Content-Type": "application/json"},
        )

    async def set_constant_temp(self, plant_id: str, path: str, value: float) -> None:
        """Dauerhafte Temperatur im Constant-Programm."""
        plant_token = await self._ensure_plant_token(plant_id)
        await self._request_no_json(
            "PATCH",
            API_SET_CONSTANT.format(plant_id=plant_id, path=path),
            json={"constant": {"value": value}},
            headers_factory=lambda: {**self._plant_headers(plant_token), "Content-Type": "application/json"},
        )

    async def set_program(self, plant_id: str, path: str, program: str) -> None:
        """Switch program: week1, week2, constant."""
        plant_token = await self._ensure_plant_token(plant_id)
        await self._request_no_json(
            "POST",
            API_SET_PROGRAM.format(plant_id=plant_id, path=path, program=program),
            headers_factory=lambda: {
                **self._plant_headers(plant_token),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="",
        )
