# Tasmota IR — Home Assistant Integration

A Home Assistant custom integration that turns a Tasmota IR transceiver into first-class HA entities — one per target device (TV, AC, soundbar, …). Includes a bundled custom Lovelace card. **No YAML, anywhere.**

## What you get

- **`remote.*` entities** for TV-style devices: learn buttons individually, send them with HA's standard `remote.*` services.
- **`climate.*` entities** for ACs: HA's built-in thermostat card just works, no learning needed — Tasmota's `IRHvac` generates the IR signal from mode/temp/fan/swing.
- **Auto-discovery** of Tasmota IR blasters via Tasmota's HA-discovery topic.
- **Auto-detect AC vendor** by pressing a button on the physical remote — no need to know whether it's `DAIKIN64` or `MITSUBISHI112`.
- **Bundled Lovelace card** that auto-renders one tile per learned button with an inline **+ Learn New Button** flow. Long-press / right-click a tile for **Send / Re-learn / Delete**.
- **Physical-remote sync** — when you use the real remote, HA's climate state mirrors it automatically, keeping HA and the AC in lockstep.
- **Differential-protocol support** (Daikin64 et al.) via Tasmota's `StateMode: SendStore`.
- **Persistent storage** of all learned codes and AC state in HA's `Store` — survives restarts, included in HA backups.

## Requirements

- Home Assistant **2024.4** or later.
- HA's **MQTT integration** configured.
- A Tasmota device flashed with **`tasmota-ir.bin`**, IR LED + receiver wired, MQTT pointed at the same broker as HA. Tasmota HA discovery on (default).
- HACS (for one-click install).

## Installation

1. HACS → Integrations → ⋮ → **Custom repositories** → add `https://github.com/jyling/tasmota-ir-home-assistant`, category `Integration`.
2. **Download** *Tasmota IR*. Restart HA.
3. Settings → Devices & Services → **+ Add Integration** → search **Tasmota IR** — discovery picks up your blaster.

## Adding a TV-style device

1. Settings → Devices & Services → Tasmota IR → ⚙ **Configure**.
2. **Add a TV-style device** → name it (`Living Room TV`), optional manufacturer/model.
3. A `remote.living_room_tv` entity is created.
4. Add the bundled **Tasmota IR Remote** card to your dashboard (under Add Card → Tasmota IR Remote). Pick the entity from the dropdown. Save.
5. On the card, tap **+ Learn New Button** → type a name (`power`, `volume_up`, …) → press the physical remote at the Tasmota receiver. The new tile appears.
6. **Long-press / right-click** any tile for Send / Re-learn / Delete.

## Adding an AC

Two routes:

**Auto-detect (recommended)** — Configure → **Add an AC (auto-detect from remote)** → enter a name → press any button on the AC's physical remote within 20 s. The integration reads Tasmota's parsed `IRHVAC` payload and uses its `Vendor` field as the protocol. The new entity is created with the AC's current state pre-filled.

**Manual** — Configure → **Add an AC (pick vendor manually)** → choose from a list of common Tasmota AC protocols (`DAIKIN64`, `MITSUBISHI112`, `LG`, …).

Either way, you get a `climate.*` entity. Add HA's stock **Thermostat** card pointing at it.

## Removing a device

- **Device page** → ⋮ menu → **Delete**, or
- Configure → **Remove a device** → pick from list.

## Using HA services directly

The integration uses HA-standard services so you can call them from automations, scripts, or Developer Tools without any vendor-specific knowledge.

```yaml
service: remote.learn_command
target: { entity_id: remote.living_room_tv }
data: { command: [power], timeout: 20 }

service: remote.send_command
target: { entity_id: remote.living_room_tv }
data: { command: [power] }

service: remote.delete_command
target: { entity_id: remote.living_room_tv }
data: { command: [power] }
```

For climate entities, use the normal `climate.set_hvac_mode`, `climate.set_temperature`, etc.

## What each entity exposes

**Remote entity** (`remote.living_room_tv`):

```yaml
state: on
attributes:
  commands: [power, volume_up, volume_down, ...]
  manufacturer: Hisense
  model: ""
```

**Climate entity** (`climate.bedroom_ac`): standard HA climate attributes (`hvac_mode`, `target_temperature`, `fan_mode`, `swing_mode`) plus the Tasmota protocol stored on the underlying HA device.

## Architecture

- Single MQTT bridge per Tasmota blaster — subscribes once to `tele/<topic>/RESULT`, publishes to `cmnd/<topic>/IRSend` and `cmnd/<topic>/IRHvac`.
- All learned codes and AC state in one HA `Store` JSON file.
- Auto-discovery via `tasmota/discovery/+/config`.
- Lovelace card auto-registered as a frontend resource on setup — no manual resource entry.

Full design spec: [docs/superpowers/specs/2026-05-16-tasmota-ir-integration-design.md](docs/superpowers/specs/2026-05-16-tasmota-ir-integration-design.md).

## Status

v0.1 — feature-complete for the common path (TV remotes, ACs with auto-detect, bundled card with edit menu). Tested against HA 2024.x with Daikin64 and basic NEC TV remotes. Tests cover the storage and MQTT bridge layers; config flow and entity tests are scaffolded.

Known limitations:
- One Tasmota blaster per integration entry (add more via separate config entries).
- Macros / scene chaining: use stock HA scripts to chain `remote.send_command` calls.
- Brand assets are not yet submitted to `home-assistant/brands`, so the integration shows the default placeholder icon.

## License

MIT.
