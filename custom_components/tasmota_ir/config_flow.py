"""Config flow for Tasmota IR."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_TOPIC_PREFIX,
    DISCOVERY_WAIT,
    DOMAIN,
    TASMOTA_DISCOVERY_TOPIC,
)

_LOGGER = logging.getLogger(__name__)


async def discover_tasmota_ir(hass: HomeAssistant) -> list[dict[str, str]]:
    """Listen for retained Tasmota discovery messages and return IR-capable devices."""
    found: dict[str, dict[str, str]] = {}

    @callback
    def _on_msg(msg) -> None:
        try:
            cfg = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if not isinstance(cfg, dict):
            return
        topic = cfg.get("t")
        if not topic:
            return
        name = cfg.get("dn") or topic
        # Heuristic: a Tasmota-IR device's name or topic typically contains "IR".
        # Stricter detection would parse the GPIO list ('gpio'/'g' fields) for
        # IRsend / IRrecv components, but the heuristic catches the common case.
        haystack = f"{topic} {name} {json.dumps(cfg.get('g', ''))}".lower()
        if "ir" in haystack:
            found[topic] = {"topic": topic, "name": name}

    unsub = await mqtt.async_subscribe(hass, TASMOTA_DISCOVERY_TOPIC, _on_msg, qos=0)
    try:
        await asyncio.sleep(DISCOVERY_WAIT)
    finally:
        unsub()
    return list(found.values())


class TasmotaIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tasmota IR."""

    VERSION = 1

    def __init__(self) -> None:
        self._candidates: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not mqtt.config_entry_enabled(self.hass):
            return self.async_abort(reason="mqtt_not_configured")

        self._candidates = await discover_tasmota_ir(self.hass)
        if len(self._candidates) == 1:
            return await self._create(self._candidates[0]["topic"])
        if not self._candidates:
            return await self.async_step_manual()
        return await self.async_step_pick()

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input["topic_prefix"])
        options = {c["topic"]: c["name"] for c in self._candidates}
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({vol.Required("topic_prefix"): vol.In(options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input["topic_prefix"])
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {vol.Required("topic_prefix", default=DEFAULT_TOPIC_PREFIX): str}
            ),
        )

    async def _create(self, topic_prefix: str) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{DOMAIN}_{topic_prefix}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Tasmota IR ({topic_prefix})",
            data={"topic_prefix": topic_prefix},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "TasmotaIrOptionsFlow":
        return TasmotaIrOptionsFlow(config_entry)


class TasmotaIrOptionsFlow(OptionsFlow):
    """Add or remove target devices on an existing Tasmota IR config entry."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="menu", menu_options=["add_device", "remove_device"]
        )

    async def async_step_add_device(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            runtime = self.hass.data[DOMAIN][self.entry.entry_id]
            runtime.library.add_device(
                name=user_input["name"],
                manufacturer=user_input.get("manufacturer", ""),
                model=user_input.get("model", ""),
            )
            await runtime.library.async_save()
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("manufacturer", default=""): str,
                    vol.Optional("model", default=""): str,
                }
            ),
        )

    async def async_step_remove_device(self, user_input=None) -> ConfigFlowResult:
        runtime = self.hass.data[DOMAIN][self.entry.entry_id]
        choices = {d_id: d["name"] for d_id, d in runtime.library.devices.items()}
        if not choices:
            return self.async_abort(reason="no_devices")
        if user_input is not None:
            runtime.library.remove_device(user_input["device"])
            await runtime.library.async_save()
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({vol.Required("device"): vol.In(choices)}),
        )
