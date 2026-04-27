"""Hoval Connect API client."""
from __future__ import annotations

import logging
import time

import aiohttp

from .const import (
    API_CIRCUITS,
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
)

_LOGGER = logging.getLogger(__name__)

APP_HEADERS = {
    "User-Agent": "HovalConnect/6022 CFNetwork/3860.400.51 Darwin/25.3.0",
    "Accept": "application/json",
    "x-requested-with": "XMLHttpRequest",
    "hovalconnect-frontend-app-version": "3.1.4",
}

API_SET_CONSTANT = "https://azure-iot-prod.hoval.com/core/v3/plants/{plant_id}/circuits/{path}/programs"

class HovalAuthError(Exception):
    pass

class HovalAPIError(Exception):
    pass

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
        self._token_retry_interval: float = 60.0

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
        token = data.get("access_token") or data.get("id_token")
        if not token:
            raise HovalAPIError("Auth response missing token")

        expires_in = int(data.get("expires_in", default_expires_in))
        lifetime = max(60, expires_in - 60)
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
        self._plant_token = None

        if self._on_token_refresh:
            self._on_token_refresh(self.auth_data())

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
            headers={**APP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
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
            headers={**APP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
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
                self._next_token_retry_at = now + self._token_retry_interval
                _LOGGER.warning(
                    "Token renewal failed; retrying in %.0f seconds while existing token remains valid: %s",
                    self._token_retry_interval,
                    err,
                )
                return
            raise

    async def _ensure_plant_token(self, plant_id: str) -> str:
        if self._plant_token and time.monotonic() < self._plant_token_expires:
            return self._plant_token
        await self._ensure_access_token()
        async with self._session.get(
            API_PLANT_SETTINGS.format(plant_id=plant_id),
            headers={**APP_HEADERS, "Authorization": f"Bearer {self._access_token}"},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        self._plant_token = data["token"]
        self._plant_token_expires = time.monotonic() + 800
        return self._plant_token

    async def _h(self, plant_id: str) -> dict:
        pt = await self._ensure_plant_token(plant_id)
        return {**APP_HEADERS, "Authorization": f"Bearer {self._access_token}", "x-plant-access-token": pt}

    async def get_plants(self) -> list[dict]:
        await self._ensure_access_token()
        async with self._session.get(API_MY_PLANTS,
            headers={**APP_HEADERS, "Authorization": f"Bearer {self._access_token}"}) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def get_circuits(self, plant_id: str) -> list[dict]:
        async with self._session.get(API_CIRCUITS.format(plant_id=plant_id),
            headers=await self._h(plant_id)) as resp:
            if resp.status == 401:
                # Token expired — force refresh of both tokens and retry once
                _LOGGER.debug("401 on circuits, forcing token refresh")
                self._expires_at = 0.0
                self._renew_after = 0.0
                self._next_token_retry_at = 0.0
                self._plant_token = None
                async with self._session.get(API_CIRCUITS.format(plant_id=plant_id),
                    headers=await self._h(plant_id)) as resp2:
                    resp2.raise_for_status()
                    return await resp2.json(content_type=None)
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def get_live_values(self, plant_id: str, circuit_path: str, circuit_type: str) -> dict:
        """Live-Werte für einen Circuit: Temp, Modulation, Betriebsstunden etc."""
        h = await self._h(plant_id)
        url = f"{API_LIVE_VALUES.format(plant_id=plant_id)}?circuitPath={circuit_path}&circuitType={circuit_type}"
        async with self._session.get(url, headers=h) as resp:
            if resp.status in (404, 502):
                return {}
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        # Convert list of {key, value} to dict
        return {item["key"]: item["value"] for item in data if "key" in item}

    async def set_temporary_change(self, plant_id: str, path: str, value: float, duration: str = "fourHours") -> None:
        """Temporary temperature change (weekly program continues)."""
        h = await self._h(plant_id)
        async with self._session.post(
            API_TEMP_CHANGE.format(plant_id=plant_id, path=path),
            json={"duration": duration, "value": value},
            headers={**h, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()

    async def set_constant_temp(self, plant_id: str, path: str, value: float) -> None:
        """Dauerhafte Temperatur im Constant-Programm."""
        h = await self._h(plant_id)
        async with self._session.patch(
            API_SET_CONSTANT.format(plant_id=plant_id, path=path),
            json={"constant": {"value": value}},
            headers={**h, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()

    async def set_program(self, plant_id: str, path: str, program: str) -> None:
        """Switch program: week1, week2, constant."""
        h = await self._h(plant_id)
        async with self._session.post(
            API_SET_PROGRAM.format(plant_id=plant_id, path=path, program=program),
            headers={**h, "Content-Type": "application/x-www-form-urlencoded"},
            data="",
        ) as resp:
            resp.raise_for_status()
