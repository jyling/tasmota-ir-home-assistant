"""MQTT bridge for the Tasmota IR integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


class MqttIrBridge:
    """Owns MQTT subscription to tele/<prefix>/RESULT and the IRSend publish helper."""

    def __init__(self, hass: HomeAssistant, topic_prefix: str) -> None:
        self.hass = hass
        self.topic_prefix = topic_prefix
        self._unsub = None
        self._learn_lock = asyncio.Lock()
        self._pending: asyncio.Future[dict[str, Any]] | None = None

    async def async_start(self) -> None:
        self._unsub = await mqtt.async_subscribe(
            self.hass,
            f"tele/{self.topic_prefix}/RESULT",
            self._on_message,
            qos=0,
        )

    async def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _on_message(self, msg) -> None:
        self.hass.async_create_task(self._handle_message(msg.payload))

    async def _handle_message(self, raw: bytes | str) -> None:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return
        if not isinstance(data, dict):
            return
        ir = data.get("IrReceived")
        if not ir:
            return
        if self._pending and not self._pending.done():
            self._pending.set_result(ir)

    async def async_wait_for_ir(self, timeout: int) -> dict[str, Any]:
        """Wait for the next IrReceived event, respecting a single-flight lock."""
        async with self._learn_lock:
            self._pending = asyncio.get_event_loop().create_future()
            try:
                return await asyncio.wait_for(self._pending, timeout=timeout)
            finally:
                self._pending = None

    async def async_send(self, payload: dict[str, Any]) -> None:
        await mqtt.async_publish(
            self.hass,
            f"cmnd/{self.topic_prefix}/IRSend",
            json.dumps(payload),
            qos=0,
            retain=False,
        )

    async def async_send_hvac(self, payload: dict[str, Any]) -> None:
        """Publish an IRHvac payload — stateful AC control."""
        await mqtt.async_publish(
            self.hass,
            f"cmnd/{self.topic_prefix}/IRHvac",
            json.dumps(payload),
            qos=0,
            retain=False,
        )
