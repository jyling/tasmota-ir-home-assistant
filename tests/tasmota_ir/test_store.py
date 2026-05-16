"""Tests for CodeLibrary."""
from __future__ import annotations

from custom_components.tasmota_ir.store import CodeLibrary


async def test_add_device_and_persist_round_trip(hass):
    lib = CodeLibrary(hass)
    await lib.async_load()

    device_id = lib.add_device(name="Living Room TV", manufacturer="Hisense")
    assert device_id in lib.devices
    assert lib.devices[device_id]["name"] == "Living Room TV"
    assert lib.devices[device_id]["manufacturer"] == "Hisense"

    lib.set_command(
        device_id, "power", {"Protocol": "NEC", "Bits": 32, "Data": "0x20DF10EF"}
    )
    await lib.async_save()

    lib2 = CodeLibrary(hass)
    await lib2.async_load()
    assert lib2.get_command(device_id, "power")["Data"] == "0x20DF10EF"


async def test_remove_device(hass):
    lib = CodeLibrary(hass)
    await lib.async_load()
    device_id = lib.add_device(name="Bedroom AC")
    lib.remove_device(device_id)
    assert device_id not in lib.devices


async def test_remove_command(hass):
    lib = CodeLibrary(hass)
    await lib.async_load()
    device_id = lib.add_device(name="TV")
    lib.set_command(device_id, "power", {"Data": "0x1"})
    lib.remove_command(device_id, "power")
    assert lib.get_command(device_id, "power") is None
