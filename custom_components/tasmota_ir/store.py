"""Persistent code library for Tasmota IR."""
from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


def _slug(name: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "device"


class CodeLibrary:
    """Owns the JSON store of devices and their learned IR commands."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"topic_prefix": "", "devices": {}}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self._data = data
        self._data.setdefault("devices", {})
        self._data.setdefault("topic_prefix", "")

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        return self._data["devices"]

    @property
    def topic_prefix(self) -> str:
        return self._data.get("topic_prefix", "")

    def set_topic_prefix(self, prefix: str) -> None:
        self._data["topic_prefix"] = prefix

    def add_device(self, *, name: str, manufacturer: str = "", model: str = "") -> str:
        device_id = f"{_slug(name)}_{uuid.uuid4().hex[:4]}"
        self._data["devices"][device_id] = {
            "name": name,
            "manufacturer": manufacturer,
            "model": model,
            "commands": {},
        }
        return device_id

    def remove_device(self, device_id: str) -> None:
        self._data["devices"].pop(device_id, None)

    def set_command(self, device_id: str, name: str, payload: dict[str, Any]) -> None:
        self._data["devices"][device_id]["commands"][name] = payload

    def remove_command(self, device_id: str, name: str) -> None:
        self._data["devices"].get(device_id, {}).get("commands", {}).pop(name, None)

    def get_command(self, device_id: str, name: str) -> dict[str, Any] | None:
        return self._data["devices"].get(device_id, {}).get("commands", {}).get(name)
