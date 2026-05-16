"""Remote entity for Tasmota IR."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_LEARN_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota IR remote entities from a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TasmotaIrRemote(runtime, entry, device_id)
        for device_id, info in runtime.library.devices.items()
        if info.get("type", "remote") == "remote"
    ]
    async_add_entities(entities)


class TasmotaIrRemote(RemoteEntity):
    """A Tasmota-backed IR remote for one target appliance."""

    _attr_should_poll = False
    _attr_supported_features = (
        RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
    )

    def __init__(self, runtime, entry: ConfigEntry, device_id: str) -> None:
        self._runtime = runtime
        self._device_id = device_id
        info = runtime.library.devices[device_id]
        self._attr_unique_id = f"tasmota_ir_{device_id}"
        self._attr_name = info["name"]
        self._attr_is_on = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=info["name"],
            manufacturer=info.get("manufacturer") or None,
            model=info.get("model") or None,
            via_device=(DOMAIN, entry.entry_id),
        )
        self._refresh_attrs()

    def _refresh_attrs(self) -> None:
        info = self._runtime.library.devices.get(self._device_id, {"commands": {}})
        self._attr_extra_state_attributes = {
            "commands": sorted(info.get("commands", {}).keys()),
            "manufacturer": info.get("manufacturer", ""),
            "model": info.get("model", ""),
        }

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        num_repeats: int = kwargs.get("num_repeats", 1) or 1
        delay_secs: float = kwargs.get("delay_secs", 0.0) or 0.0
        import asyncio

        for name in command:
            payload = self._runtime.library.get_command(self._device_id, name)
            if payload is None:
                raise ServiceValidationError(
                    f"Command '{name}' not learned on this device"
                )
            for i in range(num_repeats):
                if i > 0 and delay_secs:
                    await asyncio.sleep(delay_secs)
                await self._runtime.bridge.async_send(payload)

    async def async_learn_command(self, **kwargs: Any) -> None:
        commands: list[str] = list(kwargs.get("command", []))
        timeout: int = int(kwargs.get("timeout") or DEFAULT_LEARN_TIMEOUT)
        if not commands:
            raise ServiceValidationError("At least one command name is required")
        for name in commands:
            try:
                payload = await self._runtime.bridge.async_wait_for_ir(timeout=timeout)
            except TimeoutError as err:
                raise HomeAssistantError(
                    f"No IR signal received within {timeout}s"
                ) from err
            self._runtime.library.set_command(self._device_id, name, payload)
        await self._runtime.library.async_save()
        self._refresh_attrs()
        self.async_write_ha_state()

    async def async_delete_command(self, **kwargs: Any) -> None:
        for name in kwargs.get("command", []):
            self._runtime.library.remove_command(self._device_id, name)
        await self._runtime.library.async_save()
        self._refresh_attrs()
        self.async_write_ha_state()
