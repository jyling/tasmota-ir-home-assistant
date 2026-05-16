"""Tests for the MQTT bridge."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.tasmota_ir.mqtt_bridge import MqttIrBridge

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "ir_received_nec.json").read_text()
)


async def test_learn_resolves_on_ir_received(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")

    async def feed_after_delay():
        await asyncio.sleep(0.05)
        await bridge._handle_message(json.dumps(FIXTURE).encode())

    feeder = asyncio.create_task(feed_after_delay())
    result = await bridge.async_wait_for_ir(timeout=2)
    await feeder

    assert result["Protocol"] == "NEC"
    assert result["Data"] == "0x20DF10EF"


async def test_learn_times_out(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    with pytest.raises((asyncio.TimeoutError, TimeoutError)):
        await bridge.async_wait_for_ir(timeout=0.1)


async def test_non_ir_message_is_ignored(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    # Should not raise or resolve any future.
    await bridge._handle_message(b'{"Time":"2026-01-01T00:00:00","Vcc":3.3}')


async def test_send_publishes_correct_topic_and_payload(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    payload = {"Protocol": "NEC", "Bits": 32, "Data": "0x1"}

    with patch(
        "custom_components.tasmota_ir.mqtt_bridge.mqtt.async_publish",
        new=AsyncMock(),
    ) as pub:
        await bridge.async_send(payload)

    pub.assert_awaited_once()
    args = pub.await_args
    assert args.args[1] == "cmnd/tasmota_ir/IRSend"
    assert json.loads(args.args[2])["Data"] == "0x1"
