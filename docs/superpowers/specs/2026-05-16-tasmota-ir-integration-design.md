# Tasmota IR — HA Custom Integration — Design

**Date:** 2026-05-16
**Status:** Draft for review
**Supersedes:** the pure-UI design — that approach remains documented as a fallback, but the integration is the chosen path.

## Goal

A first-class Home Assistant custom integration (`tasmota_ir`) that turns a Tasmota IR transceiver into HA `remote.*` entities — one per device (TV, AC, …). Each remote stores its own learned IR codes, exposes HA's standard `send_command` / `learn_command` / `delete_command` services, and renders in a polished per-device Lovelace card with an inline "+ Learn New Button" flow.

## Non-goals

- Multi-blaster routing (one Tasmota device per HA instance for v1).
- Cloud / remote-access concerns (LAN only).
- Macros / scene chaining (HA scripts/scenes can chain `remote.send_command` calls already).
- Importing codes from external databases (SmartIR, Broadlink dumps). Deferred.

## Top-level architecture

```
[IR remote] →  IR RX  ┐                                   ┌──────────────────────────────────┐
                      ├─► Tasmota ◄── MQTT ──► Mosquitto ◄┤ HA tasmota_ir custom integration │
[Target device] ← IR TX ┘                                  │  - remote.* entities             │
                                                           │  - Store-backed code library     │
                                                           │  - Config & Options flows        │
                                                           └─────────────────┬────────────────┘
                                                                             │
                                                                  ┌──────────▼───────────┐
                                                                  │ Custom Lovelace card │
                                                                  │ (HACS Frontend)      │
                                                                  └──────────────────────┘
```

## Components

### 1. Python integration `custom_components/tasmota_ir/`

Files (each with one clear responsibility):

| File | Responsibility |
|---|---|
| `manifest.json` | Integration metadata, HA dependencies (`mqtt`), `iot_class: local_push`, version. |
| `const.py` | Domain name, default topic prefix, storage key, signal names. |
| `__init__.py` | `async_setup_entry` / `async_unload_entry`; wires up the MQTT subscriber, the code store, and forwards setup to the `remote` platform. |
| `store.py` | A `Store`-backed `CodeLibrary` class: load/save `{device_id → {name, manufacturer, model, commands: {cmd_name → payload}}}`. Single source of truth for the integration. |
| `mqtt_bridge.py` | Owns the MQTT subscription to `tele/<topic>/RESULT`. Routes `IrReceived` events to a `Future` held by an in-flight `learn_command` call. Publishes `IRSend` payloads. |
| `config_flow.py` | UI setup: ask for MQTT topic prefix; validate by waiting for one `tele/<topic>/LWT` message within 10 s. Options flow: add / remove devices. |
| `remote.py` | `RemoteEntity` subclass per device. Implements `async_send_command`, `async_learn_command`, `async_delete_command`. Renders `state_attributes` including the sorted command list so cards can read it. |
| `services.yaml` | Custom service schemas (only if we add anything beyond HA's standard `remote.*`). |
| `strings.json` | UI translations for config/options flow. |

Boundaries:
- `store.py` knows nothing about MQTT.
- `mqtt_bridge.py` knows nothing about HA entities — it deals in topics and payloads.
- `remote.py` glues them: a `send` is "ask store for payload, ask bridge to publish"; a `learn` is "ask bridge for the next IrReceived, then ask store to persist".

### 2. Config & Options flow

- **Config flow (initial setup)** — auto-discovery first, manual fallback:
  - Step `user`: integration auto-subscribes to `tasmota/discovery/+/config` for up to 5 s. Every Tasmota device with HA-discovery enabled (`SetOption19 0` on modern Tasmota) publishes a retained config message containing its topic, MAC, model, and feature flags (which include `IRsend` / `IRrecv` GPIO presence).
    - Filters to devices that have either `IRsend` or `IRrecv` configured.
    - Presents the user a multi-select list: "We found these Tasmota IR devices on your broker — select which to add as bridges."
    - If exactly one is found, auto-select it and skip the picker.
  - Step `manual` (fallback): if discovery finds nothing within 5 s, fall back to a text field for the MQTT topic prefix. Validation by waiting for `tele/<prefix>/LWT` for another 10 s.
  - Errors: `cannot_connect`, `mqtt_not_configured`, `no_devices_found` (informational, not fatal — user can still proceed manually).
  - Single config entry per integration instance. Adding more blasters later happens through the options flow.
- **Options flow (add/remove devices)**:
  - Menu: `add_device`, `remove_device`.
  - `add_device` form: friendly name (required), manufacturer (optional), model (optional). Returns to menu.
  - `remove_device` form: dropdown of existing devices; on submit, removes from store and unloads the matching `RemoteEntity`.

### 3. Entities

For each device in the store, one `RemoteEntity`:
- `unique_id`: `f"tasmota_ir_{device_id}"` (device_id is a slug of the friendly name + a short uuid suffix to allow renames without collisions).
- `name`: device's friendly name.
- `device_info`: includes `manufacturer` and `model` if provided, so HA shows them on the device card.
- `state`: `on` (the remote is always available; we don't model power state).
- `state_attributes`: `{"commands": [<sorted command names>], "command_count": N}`.
- Services it implements:
  - `async_send_command(command: list[str], num_repeats: int, delay_secs: float, hold_secs: float)`
    - For each name in `command`, look up payload; publish; optional `delay_secs` between repeats.
  - `async_learn_command(command: list[str], device: str | None, command_type: str | None, alternative: bool, timeout: int)`
    - For each name in `command`: turn on a transient "learn mode" subscription, wait up to `timeout` seconds for an `IrReceived`, store it under that name. If `alternative` is True, store as a second alternate (useful for ACs).
  - `async_delete_command(command: list[str], device: str | None)`
    - For each name, remove from store and save.

### 4. Storage

Single HA `Store(version=1, key="tasmota_ir")` JSON file under `.storage/tasmota_ir`. Schema:

```json
{
  "topic_prefix": "tasmota_ir",
  "devices": {
    "living_room_tv_a4f": {
      "name": "Living Room TV",
      "manufacturer": "Hisense",
      "model": "",
      "commands": {
        "power":     {"Protocol":"NEC","Bits":32,"Data":"0x20DF10EF"},
        "volume_up": {"Protocol":"NEC","Bits":32,"Data":"0x20DF40BF"}
      }
    }
  }
}
```

Atomic writes via `Store.async_save` (HA handles this). All reads are synchronous after a one-time `async_load` at setup.

### 5. MQTT bridge

- **Permanent subscriptions** at integration setup (per discovered/added Tasmota blaster):
  - `tele/<prefix>/RESULT` — the IR-receive feed.
  - `tasmota/discovery/+/config` (one global subscription) — to spot new blasters added later without a HA restart.
- **No "learn mode" gating** — the bridge is always listening. Random IR-receive events during normal use are silently dropped (nothing is in-flight to consume them). When `remote.learn_command` is called, it registers a one-shot future; the next `IrReceived` resolves it.
- This means **learning is entirely an in-app action**: the user (or the custom card) calls `remote.learn_command`, presses the remote, and the result is stored. No external toggle, no `input_boolean.ir_learn_mode`, no automation. The previous spec's "learn mode" toggle disappears entirely.
- A message handler parses JSON. If it contains `IrReceived`:
  - If `learn_command` has an in-flight `Future`, resolve it with the `IrReceived` payload.
  - Otherwise drop silently.
- Publish helper: `async_send(prefix, payload) → await mqtt.async_publish(hass, f"cmnd/{prefix}/IRSend", json.dumps(payload), qos=0, retain=False)`.

Concurrency: `learn_command` calls take a single in-process `asyncio.Lock` — only one learn in flight at a time across all remotes. Overlapping learns would race for the next IR press; the lock makes the second call wait until the first completes or times out.

### 6. Custom Lovelace card (separate repo / HACS frontend)

Out of scope for the integration itself but designed for it. Repo `lovelace-tasmota-ir-card/`:

- Lit + TypeScript single-file element.
- Card config: `entity: remote.living_room_tv`.
- Reads `state_attributes.commands` for the button list; reads `device_info` for the subtitle.
- Buttons call `remote.send_command` with `command: [<name>]`.
- "+ Learn New Button" tile:
  1. Pops a small modal asking for a command name.
  2. Calls `remote.learn_command` with `command: [name]` and a 20 s timeout.
  3. Shows a "Press your remote now…" overlay until the entity's `state_attributes.commands` updates (proves the code was stored).
  4. On success, the new tile appears.

Distribution: a separate GitHub repo; user adds it as a custom HACS Frontend repository.

## Data flow examples

**Send "TV power":**
1. Card renders `Power` tile from `state_attributes.commands`.
2. Tap → calls `remote.send_command` (entity_id = `remote.living_room_tv`, command = `["power"]`).
3. `remote.py` looks up the stored payload, asks `mqtt_bridge.async_send(payload)`.
4. Tasmota fires IR LED.

**Learn "TV volume up":**
1. Tap "+ Learn New Button" → modal → user types `volume_up` → calls `remote.learn_command` (command = `["volume_up"]`, timeout 20).
2. `remote.py` acquires the learn lock, asks `mqtt_bridge` for the next `IrReceived`, returns a `Future`.
3. User points remote at Tasmota, presses Vol+.
4. `mqtt_bridge` resolves the `Future` with the parsed payload.
5. `remote.py` stores `volume_up → payload` in the store, saves, fires `state_changed` so the card refreshes.
6. New `volume_up` tile appears.

## Error handling

| Condition | Behavior |
|---|---|
| MQTT not configured during config flow | Reject with `mqtt_not_configured`. |
| Topic prefix doesn't see an LWT within 10 s | Warn (not fatal) — user may set up before powering the device. Allow continue. |
| Learn timeout (no IR seen) | Service raises `HomeAssistantError("No IR signal received within Ns")`. Card surfaces toast. |
| Duplicate command name on learn | Overwrite, with a debug-log entry. (UI confirmation lives in the card.) |
| Send for unknown command | Raise `ServiceValidationError("Command 'X' not learned on device Y")`. |
| Storage corruption / decode failure | Log, start with empty library — never crash. |

## Testing

Three layers:

1. **Unit tests** (pytest, no HA fixtures):
   - `store.py`: round-trip, add/remove device, add/remove command.
   - `mqtt_bridge.py`: payload parsing (with mock `mqtt.async_publish`), learn-future resolution, non-`IrReceived` messages are dropped.
2. **Integration tests** (with `pytest-homeassistant-custom-component`):
   - Config flow happy path + cannot-connect path.
   - Options flow add/remove device.
   - `remote.send_command` publishes the right MQTT topic + payload.
   - `remote.learn_command` happy path + timeout.
3. **Manual tests** (against a real Tasmota device): documented in the plan.

CI: GitHub Actions on push — runs hassfest, HACS validation, and the test suite against the supported HA versions.

## File layout (this repo)

```
custom_components/tasmota_ir/
├── __init__.py
├── manifest.json
├── const.py
├── store.py
├── mqtt_bridge.py
├── config_flow.py
├── remote.py
├── services.yaml
└── strings.json

tests/tasmota_ir/
├── conftest.py
├── test_store.py
├── test_mqtt_bridge.py
├── test_config_flow.py
├── test_remote.py
└── fixtures/
    └── ir_received_nec.json

docs/superpowers/
├── specs/2026-05-16-tasmota-ir-integration-design.md   (this file)
└── plans/2026-05-16-tasmota-ir-integration.md          (implementation plan)

.github/workflows/
├── ci.yml      (pytest + hassfest)
└── hacs.yml    (HACS validate)

hacs.json
```

## Compatibility & dependencies

- HA `>= 2024.4`.
- `manifest.json` declares `dependencies: ["mqtt"]` — HA's MQTT integration must be configured by the user before adding `tasmota_ir`.
- For auto-discovery: Tasmota with HA discovery enabled (`SetOption19 0` on modern firmware, which is the default for `tasmota-ir.bin`). If a user has discovery disabled, the manual-prefix fallback covers them.
- No external Python dependencies — uses HA's bundled libraries only.

## Open questions / deferred

- **Renaming a learned command**: v1 has add/delete; rename = delete + relearn. Add a proper rename in v2 if needed.
- **Long-press / hold simulation**: HA's `remote.send_command` exposes `hold_secs`. Tasmota's `IRSend` doesn't natively hold — we can emulate via repeated sends. Decide during implementation; if the device protocol's `Repeat` field works, prefer that.
- **AC raw codes**: same fallback as the pure-UI design — recommend `IRHvac` payloads.
- **Multiple Tasmota blasters**: deferred. Architecture allows it (the bridge could subscribe per-prefix and the store could key by both device and blaster) but not in v1.

## Out of scope

- Web-installer or auto-flashing Tasmota onto a fresh ESP.
- Pre-populated code databases.
- Non-MQTT transports (HTTP, ESPHome native).
