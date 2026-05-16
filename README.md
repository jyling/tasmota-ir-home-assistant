# Tasmota IR — Home Assistant Integration

A Home Assistant custom integration that turns a Tasmota IR transceiver into first-class `remote.*` entities — one per target device (TV, AC, soundbar, …). Uses HA's standard `remote.send_command` / `remote.learn_command` / `remote.delete_command` services. No YAML required after install.

## Features

- **Auto-discovery** of Tasmota IR blasters via Tasmota's HA discovery topic.
- **One `remote.*` entity per device you control**, each with its own learned-code library.
- **Inline learn / send / delete** via standard HA services — works with any remote-friendly Lovelace card.
- **Persistent storage** of learned codes in HA's `Store` (survives restarts, included in backups).
- **No `input_boolean` toggles, no automations to wire up** — learn mode is a service call, not a global mode.

## Requirements

- Home Assistant **2024.4** or later.
- HA's **MQTT integration** configured (Mosquitto add-on works fine).
- A Tasmota device flashed with **`tasmota-ir.bin`**, IR LED + receiver wired, MQTT pointed at the same broker as HA.
- Tasmota HA discovery on (default for fresh flashes).

## Installation (HACS)

1. HACS → Integrations → ⋮ → **Custom repositories** → add this repo URL, category `Integration`.
2. **Download** `Tasmota IR`. Restart HA.
3. Settings → Devices & Services → **+ Add Integration** → search **Tasmota IR**.
4. Discovery picks up your blaster automatically (or fall back to manual prefix entry).

## Adding a target device

After the integration is added, click **Configure** on its card → **Add a target device** → name it (`Living Room TV`), optionally set manufacturer/model. A new `remote.living_room_tv` entity appears.

## Learning a code

Developer Tools → Services → `remote.learn_command`:

```yaml
service: remote.learn_command
target:
  entity_id: remote.living_room_tv
data:
  command: [power]
  timeout: 20
```

Press the physical remote's Power button at the Tasmota receiver within 20 seconds. The code is stored under the name `power`.

## Sending a code

```yaml
service: remote.send_command
target:
  entity_id: remote.living_room_tv
data:
  command: [power]
```

## Deleting a code

```yaml
service: remote.delete_command
target:
  entity_id: remote.living_room_tv
data:
  command: [power]
```

## What the entity exposes

`remote.living_room_tv.state_attributes`:

```yaml
commands: [power, volume_up, volume_down, ...]
manufacturer: "Hisense"
model: ""
```

Build any Lovelace UI you like on top of this.

## Architecture

See [docs/superpowers/specs/2026-05-16-tasmota-ir-integration-design.md](docs/superpowers/specs/2026-05-16-tasmota-ir-integration-design.md).

## Status

v0.1 — usable but pre-release. No custom Lovelace card yet (planned). Tests run on HA ≥ 2024.4.
