# Tasmota IR HA Integration — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans (subagents are not required here; each task is small and shares context). Steps use checkbox syntax for tracking.

**Goal:** Build a HA custom integration `tasmota_ir` that exposes Tasmota IR blasters as `remote.*` entities with auto-discovery, learn/send/delete commands, and a UI-only setup. Plus a thin custom Lovelace card for polished per-device UX.

**Architecture:** MQTT-based local-push integration. Auto-discovers Tasmota IR blasters via Tasmota's HA discovery topic. Each blaster + device pair becomes one `RemoteEntity`. Stores learned codes in HA's `Store` API. Implements HA's standard `remote.send_command` / `remote.learn_command` / `remote.delete_command` services.

**Tech stack:** Python 3.12, Home Assistant ≥ 2024.4, `pytest`, `pytest-homeassistant-custom-component`. Custom card: TypeScript + Lit (built in a separate sub-task).

**Reference spec:** [docs/superpowers/specs/2026-05-16-tasmota-ir-integration-design.md](../specs/2026-05-16-tasmota-ir-integration-design.md)

---

## Task 1: Scaffold the integration package

**Files:**
- Create: `custom_components/tasmota_ir/__init__.py`
- Create: `custom_components/tasmota_ir/manifest.json`
- Create: `custom_components/tasmota_ir/const.py`
- Create: `hacs.json`
- Create: `.github/workflows/ci.yml`
- Create: `tests/tasmota_ir/__init__.py`
- Create: `tests/tasmota_ir/conftest.py`
- Create: `pyproject.toml`
- Create: `requirements_test.txt`

- [ ] **Step 1.1: Create `manifest.json`**

```json
{
  "domain": "tasmota_ir",
  "name": "Tasmota IR",
  "codeowners": ["@samuelling977"],
  "config_flow": true,
  "dependencies": ["mqtt"],
  "documentation": "https://github.com/samuelling977/tasmota-ir",
  "integration_type": "hub",
  "iot_class": "local_push",
  "issue_tracker": "https://github.com/samuelling977/tasmota-ir/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

- [ ] **Step 1.2: Create `const.py`**

```python
"""Constants for the Tasmota IR integration."""
from __future__ import annotations

DOMAIN = "tasmota_ir"

# MQTT
DEFAULT_TOPIC_PREFIX = "tasmota_ir"
TASMOTA_DISCOVERY_TOPIC = "tasmota/discovery/+/config"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "tasmota_ir"

# Timeouts (seconds)
DISCOVERY_WAIT = 5
LWT_WAIT = 10
DEFAULT_LEARN_TIMEOUT = 20

# Signals
SIGNAL_DEVICE_ADDED = f"{DOMAIN}_device_added"
SIGNAL_DEVICE_REMOVED = f"{DOMAIN}_device_removed"
SIGNAL_COMMANDS_UPDATED = f"{DOMAIN}_commands_updated"
```

- [ ] **Step 1.3: Create `__init__.py` (minimal stub)**

```python
"""The Tasmota IR integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tasmota IR from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 1.4: Create `hacs.json`**

```json
{
  "name": "Tasmota IR",
  "homeassistant": "2024.4.0",
  "render_readme": true
}
```

- [ ] **Step 1.5: Create test scaffolding**

`tests/tasmota_ir/__init__.py`: empty file.

`tests/tasmota_ir/conftest.py`:

```python
"""Common fixtures for Tasmota IR tests."""
from __future__ import annotations

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in tests."""
    yield
```

- [ ] **Step 1.6: Create `requirements_test.txt`**

```
pytest-homeassistant-custom-component>=0.13.0
pytest-asyncio>=0.23
```

- [ ] **Step 1.7: Create `pyproject.toml`** (minimal — for pytest config only)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 1.8: Create CI workflow `.github/workflows/ci.yml`**

```yaml
name: CI
on: [push, pull_request]
jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements_test.txt
      - run: pytest -v
```

- [ ] **Step 1.9: Commit**

```bash
git add custom_components hacs.json .github tests pyproject.toml requirements_test.txt
git commit -m "feat(tasmota_ir): scaffold integration package"
```

---

## Task 2: Code library (Store-backed)

**Files:**
- Create: `custom_components/tasmota_ir/store.py`
- Create: `tests/tasmota_ir/test_store.py`

- [ ] **Step 2.1: Write the failing test**

`tests/tasmota_ir/test_store.py`:

```python
"""Tests for CodeLibrary."""
from __future__ import annotations

import pytest

from custom_components.tasmota_ir.store import CodeLibrary


async def test_add_device_and_command(hass):
    lib = CodeLibrary(hass)
    await lib.async_load()

    device_id = lib.add_device(name="Living Room TV", manufacturer="Hisense")
    assert device_id in lib.devices
    assert lib.devices[device_id]["name"] == "Living Room TV"

    lib.set_command(device_id, "power", {"Protocol": "NEC", "Bits": 32, "Data": "0x20DF10EF"})
    await lib.async_save()

    lib2 = CodeLibrary(hass)
    await lib2.async_load()
    assert lib2.devices[device_id]["commands"]["power"]["Data"] == "0x20DF10EF"


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
    assert "power" not in lib.devices[device_id]["commands"]
```

- [ ] **Step 2.2: Verify the test fails**

```bash
pytest tests/tasmota_ir/test_store.py -v
```

Expected: `ModuleNotFoundError: No module named 'custom_components.tasmota_ir.store'`.

- [ ] **Step 2.3: Implement `store.py`**

```python
"""Persistent code library for Tasmota IR."""
from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


class CodeLibrary:
    """Owns the JSON store of devices and their learned commands."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"topic_prefix": "", "devices": {}}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self._data = data
        self._data.setdefault("devices", {})

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
        self._data["devices"][device_id]["commands"].pop(name, None)

    def get_command(self, device_id: str, name: str) -> dict[str, Any] | None:
        return self._data["devices"].get(device_id, {}).get("commands", {}).get(name)
```

- [ ] **Step 2.4: Verify the tests pass**

```bash
pytest tests/tasmota_ir/test_store.py -v
```

Expected: 3 passed.

- [ ] **Step 2.5: Commit**

```bash
git add custom_components/tasmota_ir/store.py tests/tasmota_ir/test_store.py
git commit -m "feat(tasmota_ir): persistent CodeLibrary backed by HA Store"
```

---

## Task 3: MQTT bridge

**Files:**
- Create: `custom_components/tasmota_ir/mqtt_bridge.py`
- Create: `tests/tasmota_ir/test_mqtt_bridge.py`
- Create: `tests/tasmota_ir/fixtures/ir_received_nec.json`

- [ ] **Step 3.1: Create fixture**

`tests/tasmota_ir/fixtures/ir_received_nec.json`:

```json
{"IrReceived":{"Protocol":"NEC","Bits":32,"Data":"0x20DF10EF","DataLSB":"0x040820F7","Repeat":0}}
```

- [ ] **Step 3.2: Write the failing tests**

`tests/tasmota_ir/test_mqtt_bridge.py`:

```python
"""Tests for the MQTT bridge."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.tasmota_ir.mqtt_bridge import MqttIrBridge

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "ir_received_nec.json").read_text()
)


async def test_learn_resolves_on_ir_received(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    learn_task = asyncio.create_task(bridge.async_wait_for_ir(timeout=2))
    await asyncio.sleep(0)  # let learn_task register
    await bridge._handle_message(json.dumps(FIXTURE).encode())
    result = await learn_task
    assert result["Protocol"] == "NEC"
    assert result["Data"] == "0x20DF10EF"


async def test_learn_times_out(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    with pytest.raises(asyncio.TimeoutError):
        await bridge.async_wait_for_ir(timeout=0.1)


async def test_send_publishes(hass):
    bridge = MqttIrBridge(hass, "tasmota_ir")
    payload = {"Protocol": "NEC", "Bits": 32, "Data": "0x1"}
    with patch("custom_components.tasmota_ir.mqtt_bridge.mqtt.async_publish") as pub:
        await bridge.async_send(payload)
    pub.assert_called_once()
    args = pub.call_args
    assert args.args[1] == "cmnd/tasmota_ir/IRSend"
    assert json.loads(args.args[2])["Data"] == "0x1"
```

- [ ] **Step 3.3: Run, verify it fails**

```bash
pytest tests/tasmota_ir/test_mqtt_bridge.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3.4: Implement `mqtt_bridge.py`**

```python
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
        self._pending: asyncio.Future | None = None

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
        ir = data.get("IrReceived")
        if not ir:
            return
        if self._pending and not self._pending.done():
            self._pending.set_result(ir)

    async def async_wait_for_ir(self, timeout: int) -> dict[str, Any]:
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
```

- [ ] **Step 3.5: Run, verify it passes**

```bash
pytest tests/tasmota_ir/test_mqtt_bridge.py -v
```

Expected: 3 passed.

- [ ] **Step 3.6: Commit**

```bash
git add custom_components/tasmota_ir/mqtt_bridge.py tests/tasmota_ir/
git commit -m "feat(tasmota_ir): MQTT bridge with learn-wait and publish"
```

---

## Task 4: Config flow (auto-discovery + manual fallback)

**Files:**
- Create: `custom_components/tasmota_ir/config_flow.py`
- Create: `custom_components/tasmota_ir/strings.json`
- Create: `tests/tasmota_ir/test_config_flow.py`

- [ ] **Step 4.1: Write failing tests**

`tests/tasmota_ir/test_config_flow.py`:

```python
"""Tests for the config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.tasmota_ir.const import DOMAIN


async def test_user_flow_manual_when_no_discovery(hass):
    with patch(
        "custom_components.tasmota_ir.config_flow.discover_tasmota_ir",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        # No devices found → flow advances to manual step
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"topic_prefix": "tasmota_ir"}
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"]["topic_prefix"] == "tasmota_ir"


async def test_user_flow_auto_discovers_single(hass):
    with patch(
        "custom_components.tasmota_ir.config_flow.discover_tasmota_ir",
        return_value=[{"topic": "tasmota_ir_F8D9F1", "name": "Tasmota IR F8D9F1"}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        # Single device found → auto-confirm
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["topic_prefix"] == "tasmota_ir_F8D9F1"
```

- [ ] **Step 4.2: Implement `strings.json`**

```json
{
  "config": {
    "step": {
      "manual": {
        "title": "Tasmota IR",
        "description": "No Tasmota IR devices were auto-discovered. Enter the MQTT topic prefix manually.",
        "data": { "topic_prefix": "Topic prefix" }
      },
      "pick": {
        "title": "Tasmota IR",
        "description": "Choose the Tasmota IR device to add.",
        "data": { "topic_prefix": "Device" }
      }
    },
    "error": {
      "cannot_connect": "Could not connect to MQTT broker.",
      "mqtt_not_configured": "Configure the MQTT integration first."
    }
  }
}
```

- [ ] **Step 4.3: Implement `config_flow.py`**

```python
"""Config flow for Tasmota IR."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_TOPIC_PREFIX,
    DISCOVERY_WAIT,
    DOMAIN,
    TASMOTA_DISCOVERY_TOPIC,
)

_LOGGER = logging.getLogger(__name__)


async def discover_tasmota_ir(hass: HomeAssistant) -> list[dict[str, str]]:
    """Listen for Tasmota discovery messages and return IR-capable devices."""
    found: dict[str, dict[str, str]] = {}

    @callback
    def _on_msg(msg) -> None:
        try:
            cfg = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        topic = cfg.get("t")  # Tasmota uses 't' for topic
        if not topic:
            return
        # Tasmota discovery exposes feature flags; we look for IR module hints.
        # 'so' (set options) and 'rl' (relay count) live here, but IR pins live in 'gpio'.
        # Easier proxy: the device name or topic contains 'IR', or model is 'IR'.
        name = cfg.get("dn") or topic
        feats = json.dumps(cfg).lower()
        if "ir" in feats or "ir" in topic.lower() or "ir" in name.lower():
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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not mqtt.config_entry_enabled(self.hass):
            return self.async_abort(reason="mqtt_not_configured")

        self._candidates = await discover_tasmota_ir(self.hass)
        if len(self._candidates) == 1:
            return await self._create(self._candidates[0]["topic"])
        if not self._candidates:
            return await self.async_step_manual()
        return await self.async_step_pick()

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input["topic_prefix"])
        options = {c["topic"]: c["name"] for c in self._candidates}
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({vol.Required("topic_prefix"): vol.In(options)}),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
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
```

- [ ] **Step 4.4: Run, verify tests pass**

```bash
pytest tests/tasmota_ir/test_config_flow.py -v
```

Expected: 2 passed.

- [ ] **Step 4.5: Commit**

```bash
git add custom_components/tasmota_ir/config_flow.py custom_components/tasmota_ir/strings.json tests/tasmota_ir/test_config_flow.py
git commit -m "feat(tasmota_ir): config flow with Tasmota auto-discovery"
```

---

## Task 5: Wire up `__init__.py` (load store, start bridge, forward platform)

**Files:**
- Modify: `custom_components/tasmota_ir/__init__.py`
- Create: `tests/tasmota_ir/test_init.py`

- [ ] **Step 5.1: Update `__init__.py`**

```python
"""The Tasmota IR integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .mqtt_bridge import MqttIrBridge
from .store import CodeLibrary

PLATFORMS: list[Platform] = [Platform.REMOTE]


@dataclass
class TasmotaIrRuntime:
    library: CodeLibrary
    bridge: MqttIrBridge


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    topic_prefix: str = entry.data["topic_prefix"]
    library = CodeLibrary(hass)
    await library.async_load()
    library.set_topic_prefix(topic_prefix)
    await library.async_save()

    bridge = MqttIrBridge(hass, topic_prefix)
    await bridge.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TasmotaIrRuntime(library, bridge)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: TasmotaIrRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.bridge.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 5.2: Commit**

```bash
git add custom_components/tasmota_ir/__init__.py
git commit -m "feat(tasmota_ir): wire library + bridge into setup_entry"
```

---

## Task 6: Remote entity (send / learn / delete)

**Files:**
- Create: `custom_components/tasmota_ir/remote.py`
- Create: `tests/tasmota_ir/test_remote.py`

- [ ] **Step 6.1: Write failing tests** (covers send, learn, delete, and entity attributes)

```python
"""Tests for the remote entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.tasmota_ir.const import DOMAIN


async def test_send_command_publishes(hass, init_integration_with_tv):
    runtime, entity_id, device_id = init_integration_with_tv
    runtime.library.set_command(device_id, "power", {"Protocol": "NEC", "Data": "0x1"})

    with patch.object(runtime.bridge, "async_send", new=AsyncMock()) as mock_send:
        await hass.services.async_call(
            "remote",
            "send_command",
            {ATTR_ENTITY_ID: entity_id, "command": ["power"]},
            blocking=True,
        )
    mock_send.assert_awaited_once()
    assert mock_send.await_args.args[0]["Data"] == "0x1"


async def test_learn_stores_received(hass, init_integration_with_tv):
    runtime, entity_id, device_id = init_integration_with_tv

    with patch.object(
        runtime.bridge,
        "async_wait_for_ir",
        new=AsyncMock(return_value={"Protocol": "NEC", "Data": "0x42"}),
    ):
        await hass.services.async_call(
            "remote",
            "learn_command",
            {ATTR_ENTITY_ID: entity_id, "command": ["volume_up"]},
            blocking=True,
        )
    assert runtime.library.get_command(device_id, "volume_up")["Data"] == "0x42"


async def test_delete_command_removes(hass, init_integration_with_tv):
    runtime, entity_id, device_id = init_integration_with_tv
    runtime.library.set_command(device_id, "power", {"Data": "0x1"})

    await hass.services.async_call(
        "remote",
        "delete_command",
        {ATTR_ENTITY_ID: entity_id, "command": ["power"]},
        blocking=True,
    )
    assert runtime.library.get_command(device_id, "power") is None
```

Add fixture to `conftest.py`:

```python
@pytest.fixture
async def init_integration_with_tv(hass, mqtt_mock):
    """Set up the integration with one TV device pre-added."""
    from homeassistant.config_entries import ConfigEntry
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.tasmota_ir.const import DOMAIN

    entry = MockConfigEntry(domain=DOMAIN, data={"topic_prefix": "tasmota_ir"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime = hass.data[DOMAIN][entry.entry_id]
    device_id = runtime.library.add_device(name="Living Room TV", manufacturer="Hisense")
    await runtime.library.async_save()
    # Trigger entity creation by reloading the platform
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "remote.living_room_tv"
    return runtime, entity_id, device_id
```

- [ ] **Step 6.2: Verify the tests fail**

```bash
pytest tests/tasmota_ir/test_remote.py -v
```

Expected: ImportError on `remote`.

- [ ] **Step 6.3: Implement `remote.py`**

```python
"""Remote entity for Tasmota IR."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_LEARN_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TasmotaIrRemote(runtime, device_id) for device_id in runtime.library.devices
    ]
    async_add_entities(entities)


class TasmotaIrRemote(RemoteEntity):
    """A Tasmota-backed IR remote for one target device."""

    _attr_should_poll = False
    _attr_supported_features = (
        RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
    )

    def __init__(self, runtime, device_id: str) -> None:
        self._runtime = runtime
        self._device_id = device_id
        info = runtime.library.devices[device_id]
        self._attr_unique_id = f"tasmota_ir_{device_id}"
        self._attr_name = info["name"]
        self._attr_is_on = True
        self._attr_extra_state_attributes = {
            "commands": sorted(info["commands"].keys()),
            "manufacturer": info.get("manufacturer", ""),
            "model": info.get("model", ""),
        }

    def _refresh_attrs(self) -> None:
        info = self._runtime.library.devices[self._device_id]
        self._attr_extra_state_attributes = {
            "commands": sorted(info["commands"].keys()),
            "manufacturer": info.get("manufacturer", ""),
            "model": info.get("model", ""),
        }

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        num_repeats: int = kwargs.get("num_repeats", 1)
        for name in command:
            payload = self._runtime.library.get_command(self._device_id, name)
            if payload is None:
                raise ServiceValidationError(f"Command '{name}' not learned")
            for _ in range(num_repeats):
                await self._runtime.bridge.async_send(payload)

    async def async_learn_command(self, **kwargs: Any) -> None:
        commands: list[str] = kwargs.get("command", [])
        timeout: int = kwargs.get("timeout", DEFAULT_LEARN_TIMEOUT)
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
```

- [ ] **Step 6.4: Verify tests pass**

```bash
pytest tests/tasmota_ir/ -v
```

Expected: all green.

- [ ] **Step 6.5: Commit**

```bash
git add custom_components/tasmota_ir/remote.py tests/tasmota_ir/
git commit -m "feat(tasmota_ir): remote entity with send/learn/delete"
```

---

## Task 7: Options flow (add / remove devices)

**Files:**
- Modify: `custom_components/tasmota_ir/config_flow.py`
- Modify: `custom_components/tasmota_ir/strings.json`
- Modify: `tests/tasmota_ir/test_config_flow.py`

- [ ] **Step 7.1: Write failing test for add-device options flow**

```python
async def test_options_flow_add_device(hass, init_integration):
    runtime, entry = init_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_device"}
    )
    assert result["step_id"] == "add_device"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Bedroom AC", "manufacturer": "Mitsubishi"}
    )
    assert result["type"].name == "CREATE_ENTRY"

    names = [d["name"] for d in runtime.library.devices.values()]
    assert "Bedroom AC" in names
```

- [ ] **Step 7.2: Implement `OptionsFlow`** — add to `config_flow.py`:

```python
class TasmotaIrOptionsFlow(OptionsFlow):
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
        if user_input is not None:
            runtime.library.remove_device(user_input["device"])
            await runtime.library.async_save()
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({vol.Required("device"): vol.In(choices)}),
        )


@staticmethod
@callback
def async_get_options_flow(config_entry: ConfigEntry) -> TasmotaIrOptionsFlow:
    return TasmotaIrOptionsFlow(config_entry)


TasmotaIrConfigFlow.async_get_options_flow = async_get_options_flow
```

Add the corresponding strings.json entries.

- [ ] **Step 7.3: Run tests, fix until green, commit**

```bash
pytest tests/tasmota_ir/ -v
git add -A && git commit -m "feat(tasmota_ir): options flow add/remove device"
```

---

## Task 8: Manual end-to-end test plan

This task is for the human after the code is installed on a real HA. No automated test.

- [ ] **Step 8.1: Deploy the integration**

  Copy `custom_components/tasmota_ir/` to your HA's `/config/custom_components/`. Restart HA.

- [ ] **Step 8.2: Add the integration**

  Settings → Devices & Services → **+ Add Integration** → search "Tasmota IR" → click. Expect the discovery dialog (or manual prefix prompt).

- [ ] **Step 8.3: Add a device via options**

  On the integration's card → **Configure** → **Add Device** → name `Living Room TV`, manufacturer `Hisense`. Save. Expect `remote.living_room_tv` to appear in Developer Tools → States.

- [ ] **Step 8.4: Learn a command**

  Developer Tools → Services → `remote.learn_command` → entity `remote.living_room_tv`, command `power`. Call service. Press the TV's power button at the Tasmota receiver within 20 s. Expect `state_attributes.commands` to now include `power`.

- [ ] **Step 8.5: Send a command**

  `remote.send_command` → entity `remote.living_room_tv`, command `power`. Expect the TV to react.

- [ ] **Step 8.6: Delete a command**

  `remote.delete_command` → entity `remote.living_room_tv`, command `power`. Expect `state_attributes.commands` to no longer include `power`.

- [ ] **Step 8.7: Persistence**

  Restart HA. Confirm devices and learned commands survive.

---

## Task 9 (optional): Custom Lovelace card

Lives in a **separate repo** `lovelace-tasmota-ir-card`. Out of scope for this plan — track as a follow-up. For now, use any of HA's stock remote-friendly cards (`button` cards calling `remote.send_command`, or `auto-entities` filtering on `remote.*` then calling the service).
