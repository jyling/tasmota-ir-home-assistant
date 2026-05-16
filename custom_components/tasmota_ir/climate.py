"""Climate platform for Tasmota IR (AC devices using Tasmota IRHvac)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# HA HVACMode → Tasmota Mode string
HA_TO_TASMOTA_MODE = {
    HVACMode.OFF: "Off",
    HVACMode.AUTO: "Auto",
    HVACMode.COOL: "Cool",
    HVACMode.HEAT: "Heat",
    HVACMode.DRY: "Dry",
    HVACMode.FAN_ONLY: "Fan",
}
SUPPORTED_HVAC_MODES = list(HA_TO_TASMOTA_MODE.keys())

FAN_MODES = ["auto", "min", "low", "medium", "high", "max"]
HA_TO_TASMOTA_FAN = {
    "auto": "Auto",
    "min": "Min",
    "low": "Low",
    "medium": "Med",
    "high": "High",
    "max": "Max",
}

SWING_MODES = ["off", "vertical", "horizontal", "both"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tasmota IR climate entities (AC devices) from a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TasmotaIrClimate(runtime, entry, device_id)
        for device_id, info in runtime.library.devices.items()
        if info.get("type") == "climate"
    ]
    async_add_entities(entities)


class TasmotaIrClimate(ClimateEntity):
    """A Tasmota-backed AC. State is stored in the library and re-sent on each change."""

    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = SWING_MODES
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, runtime, entry: ConfigEntry, device_id: str) -> None:
        self._runtime = runtime
        self._device_id = device_id
        info = runtime.library.devices[device_id]
        self._vendor = info.get("vendor", "")
        self._attr_unique_id = f"tasmota_ir_climate_{device_id}"
        self._attr_name = info["name"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=info["name"],
            manufacturer=info.get("manufacturer") or info.get("vendor") or None,
            model=info.get("model") or None,
            via_device=(DOMAIN, entry.entry_id),
        )
        # Restore last known state.
        state = runtime.library.get_climate_state(device_id) or {}
        self._attr_hvac_mode = HVACMode(state.get("hvac_mode", HVACMode.OFF))
        self._attr_target_temperature = state.get("target_temperature", 24)
        self._attr_fan_mode = state.get("fan_mode", "auto")
        self._attr_swing_mode = state.get("swing_mode", "off")
        # The last *active* (non-off) HVAC mode. Some AC protocols (Daikin64,
        # Mitsubishi, Toshiba, …) need the active mode preserved in the IR
        # payload when Power=Off — sending Mode=Off causes the AC to treat
        # the signal as a power-toggle instead of a state-sync.
        last_active = state.get("last_active_mode", HVACMode.COOL.value)
        try:
            self._last_active_mode = HVACMode(last_active)
        except ValueError:
            self._last_active_mode = HVACMode.COOL

    async def _async_publish(self) -> None:
        """Compose an IRHvac payload from current entity state and publish it.

        Power vs Mode: many AC protocols want a real cooling/heating mode
        always present in the payload, with Power toggled to On/Off. Sending
        Mode=Off is treated by some AC firmwares as a separate command and
        triggers a power-toggle. We track the last *active* mode and
        re-use it whenever HA says "off".
        """
        is_off = self._attr_hvac_mode == HVACMode.OFF
        if not is_off:
            self._last_active_mode = self._attr_hvac_mode
        mode_for_payload = (
            self._last_active_mode if is_off else self._attr_hvac_mode
        )
        power = "Off" if is_off else "On"
        mode = HA_TO_TASMOTA_MODE.get(mode_for_payload, "Cool")
        swing = self._attr_swing_mode or "off"
        payload: dict[str, Any] = {
            "Vendor": self._vendor,
            # StateMode=SendStore makes Tasmota track its own copy of the
            # remote's state for differential protocols (Daikin64 et al.),
            # so it only emits the IR delta — Power=On stops behaving as
            # a toggle on every redundant call.
            "StateMode": "SendStore",
            "Power": power,
            "Mode": mode,
            "FanSpeed": HA_TO_TASMOTA_FAN.get(self._attr_fan_mode or "auto", "Auto"),
            "Temp": int(self._attr_target_temperature or 24),
            "Celsius": "On",
            "SwingV": "Auto" if swing in ("vertical", "both") else "Off",
            "SwingH": "Auto" if swing in ("horizontal", "both") else "Off",
        }
        await self._runtime.bridge.async_send_hvac(payload)
        self._runtime.library.set_climate_state(
            self._device_id,
            {
                "hvac_mode": self._attr_hvac_mode.value
                if hasattr(self._attr_hvac_mode, "value")
                else str(self._attr_hvac_mode),
                "target_temperature": self._attr_target_temperature,
                "fan_mode": self._attr_fan_mode,
                "swing_mode": self._attr_swing_mode,
                "last_active_mode": self._last_active_mode.value
                if hasattr(self._last_active_mode, "value")
                else str(self._last_active_mode),
            },
        )
        await self._runtime.library.async_save()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._attr_hvac_mode = hvac_mode
        await self._async_publish()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._attr_target_temperature = float(temp)
        await self._async_publish()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._attr_fan_mode = fan_mode
        await self._async_publish()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        self._attr_swing_mode = swing_mode
        await self._async_publish()

    async def async_turn_on(self) -> None:
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = HVACMode.COOL
        await self._async_publish()

    async def async_turn_off(self) -> None:
        self._attr_hvac_mode = HVACMode.OFF
        await self._async_publish()
