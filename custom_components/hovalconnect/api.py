"""Hoval Connect API client."""
from __future__ import annotations
import logging, time
import aiohttp
from .const import AUTH_TOKEN_URL, CLIENT_ID, API_MY_PLANTS, API_PLANT_SETTINGS, API_CIRCUITS, API_TEMP_CHANGE, API_SET_PROGRAM, API_LIVE_VALUES

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
    def __init__(self, session: aiohttp.ClientSession, access_token: str, refresh_token: str) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at: float = time.monotonic() + 1800
        self._plant_token: str | None = None
        self._plant_token_expires: float = 0.0
        self._on_token_refresh = None  # callback(access_token, refresh_token)
        # Proaktiv alle 20 min erneuern (nicht erst wenn abgelaufen)
        self._proactive_refresh_interval: float = 20 * 60

    def set_token_refresh_callback(self, callback) -> None:
        """Called whenever tokens are refreshed — use to persist new tokens."""
        self._on_token_refresh = callback

    async def _ensure_access_token(self) -> None:
        # Proaktiv erneuern wenn weniger als 20 min verbleiben
        proactive_threshold = self._expires_at - self._proactive_refresh_interval
        if time.monotonic() < proactive_threshold:
            return
        async with self._session.post(
            AUTH_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token, "client_id": CLIENT_ID},
            headers={**APP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            if resp.status in (400, 401):
                raise HovalAuthError("Refresh token expired")
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._expires_at = time.monotonic() + data.get("expires_in", 1800) - 60
        self._plant_token = None
        if self._on_token_refresh:
            self._on_token_refresh(self._access_token, self._refresh_token)

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
        """Temporäre Temperaturänderung (Wochenprogramm läuft weiter)."""
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
        """Programm wechseln: week1, week2, constant."""
        h = await self._h(plant_id)
        async with self._session.post(
            API_SET_PROGRAM.format(plant_id=plant_id, path=path, program=program),
            headers={**h, "Content-Type": "application/x-www-form-urlencoded"},
            data="",
        ) as resp:
            resp.raise_for_status()
