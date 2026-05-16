# Tasmota ↔ Home Assistant IR Bridge — Design

**Date:** 2026-05-16
**Status:** Draft for review

## Goal

Use a Tasmota-flashed IR transceiver as a bidirectional IR bridge for Home Assistant, **configured and operated entirely through the HA UI** (no YAML editing, no shell scripts, no Python helpers). From a Lovelace dashboard the user can:

1. **Send** stored IR codes to any IR-controlled device.
2. **Learn** new IR codes by pointing a physical remote at the device, naming the code, assigning a device group, and having it appear as a new dashboard button — all through HA's UI.

## Non-goals

- No cloud relay; LAN only.
- No support for non-Tasmota IR hardware (this iteration).
- No multi-room / multi-blaster routing (one device).
- No macros / scene chaining (deferred).

## Assumptions

- Tasmota device is flashed with **tasmota-ir.bin**, on the LAN. MQTT pointed at the same broker HA uses.
- HA version **2024.4 or later** (required for Labels UI).
- HA MQTT integration is configured.
- HACS is installed with **`auto-entities` v1.13 or later** (required for the `label:` filter key).
- Lovelace is in **Storage mode** (the default — "Edit dashboard" is available in the UI). YAML-mode dashboards are not supported by this design's "everything UI" claim.

## Architecture

```
[IR remote] →  IR RX  ┐
                      ├─► Tasmota (tasmota-ir)  ◄── MQTT ──►  Broker  ◄── MQTT ──►  Home Assistant
[Target device] ← IR TX ┘                                                          │
                                                                                   └─► Lovelace (UI)
```

**Send path:** Lovelace button → script created from blueprint → `mqtt.publish` to `cmnd/tasmota_ir/IRSend` → Tasmota fires IR LED.

**Learn path:** User toggles learn mode → presses physical remote → Tasmota publishes `IrReceived` on `tele/tasmota_ir/RESULT` → MQTT-trigger automation copies payload into `input_text.ir_last_code` → user opens **Settings → Scripts → Add Script → Use Blueprint "Tasmota IR Send"**, names it, picks a Label (device group), Save. The new script appears on the dashboard automatically because the dashboard filters scripts by label.

## How "everything is UI" is achieved

Every artifact below is either created in the HA Settings UI, the Lovelace card editor, or imported via URL in the UI. **No file is ever edited on disk by the user.**

| Artifact | Where it's created (all UI) |
|---|---|
| `input_text.ir_last_code` | Settings → Devices & Services → Helpers → Create Helper → Text |
| `input_boolean.ir_learn_mode` | Settings → Devices & Services → Helpers → Create Helper → Toggle |
| MQTT capture automation | Settings → Automations → Create Automation (MQTT trigger) |
| Auto-disable learn mode automation | Settings → Automations → Create Automation |
| **"Tasmota IR Send" script blueprint** | Settings → Automations & Scenes → Blueprints → Import Blueprint (paste URL) |
| Each learned IR code (a script) | Settings → Scripts → Add Script → "Create script from blueprint" → fill name + label |
| Device groups | Settings → Labels → Add Label (e.g. `TV`, `AC`, `Receiver`) |
| Dashboard view + cards | Lovelace UI editor ("Edit dashboard" → Add card) |

The blueprint is the **only** file that lives on disk, and it is imported via the UI from a URL (e.g. a GitHub Gist). The user never touches the filesystem.

## Components

### 1. Tasmota device configuration (one-time, on the device)

Done via the Tasmota web console — outside HA, unavoidable, but a one-time job:

```
Backlog Topic tasmota_ir; SetOption38 1; TelePeriod 60; MqttHost <broker>; MqttUser <u>; MqttPassword <p>
```

GPIO setup in Tasmota's web UI: IR Send on the LED GPIO, IR Receive on the receiver GPIO.

**Tasmota auto-discovery (`SetOption19`)**: leave at default. If discovery is on, Tasmota will appear as a device in HA with status entities (power, RSSI, etc.). These don't interfere with this design — we deliberately use raw MQTT topics for `IRSend` and the `RESULT` capture so we are not dependent on the discovery layer.

### 2. Helpers (UI)

- **Text helper** `input_text.ir_last_code` — max length 255 (long AC codes may need a different strategy, see *Open questions*).
- **Toggle helper** `input_boolean.ir_learn_mode`.

### 3. MQTT capture automation (UI)

Created in the automation editor:

- **Trigger:** MQTT, topic `tele/tasmota_ir/RESULT`.
- **Condition:**
  - `input_boolean.ir_learn_mode` is `on`.
  - Template: `{{ 'IrReceived' in trigger.payload }}`.
- **Action:** `input_text.set_value` on `input_text.ir_last_code` with value `{{ trigger.payload_json.IrReceived | to_json }}`.
- **Action:** `persistent_notification.create` — "IR code captured — go to Settings → Scripts to save it."

### 4. Auto-disable learn mode automation (UI)

- **Mode:** `restart` (so re-toggling learn mode resets the 60 s countdown rather than queueing or dropping).
- **Trigger:** state of `input_boolean.ir_learn_mode` → `on`.
- **Action:** delay 60 s, then `input_boolean.turn_off`.

### 5. Script blueprint: "Tasmota IR Send"

Imported once via UI (Settings → Blueprints → Import → paste URL). The blueprint definition (hosted externally):

```yaml
blueprint:
  name: Tasmota IR Send
  description: Send a stored IR code through a Tasmota IR blaster.
  domain: script
  input:
    ir_payload:
      name: IR payload (JSON)
      description: The IrReceived JSON object captured during learn mode.
      selector:
        text:
          multiline: true
    mqtt_topic:
      name: MQTT command topic
      default: cmnd/tasmota_ir/IRSend
      selector:
        text: {}
mode: single
sequence:
  - service: mqtt.publish
    data:
      topic: !input mqtt_topic
      payload: !input ir_payload
```

Each learned code is a script **created from this blueprint via the UI**:
- Settings → Scripts → Add Script → "Create script from blueprint" → pick *Tasmota IR Send*.
- Paste the captured JSON (from `input_text.ir_last_code`) into the `ir_payload` field.
- Give the script a friendly name (e.g. "TV Power").
- Assign a **Label** (e.g. `TV`) via the label picker on the script edit page.
- Save.

### 6. Labels = device groups (UI)

Labels are HA's native, fully UI-managed tagging system (Settings → Labels). Each device group becomes a label (`TV`, `AC`, `Receiver`, `Lights`, ...). Scripts can be tagged with one or more labels (HA supports multi-label, useful e.g. for a "macro candidate" tag layered on top of the device tag — though macros themselves are out of scope for v1). This replaces the earlier `ir_group` variable and the `ir_groups.yaml` file from previous drafts.

### 7. Dashboard (Lovelace UI editor)

A new view "IR Remote" built entirely in the dashboard editor. All cards are added via "Add card" and configured in the visual / YAML editor for that card (which is part of the HA UI, no filesystem access).

Cards:

- **Learn card** (Entities card):
  - `input_boolean.ir_learn_mode`
  - `input_text.ir_last_code` (read-only display of last captured code)
  - Markdown note: *"Toggle learn mode, press your remote, then go to Settings → Scripts → Add → Create from blueprint."*

- **One Send card per label**, using `auto-entities` (HACS):
  ```yaml
  type: custom:auto-entities
  card:
    type: grid
    columns: 3
    title: TV
  filter:
    include:
      - domain: script
        label: tv
    exclude: []
  ```
  One such card per label the user creates. Adding a new label = add one more card via the editor (a few clicks).

Optional polish: a single `auto-entities` card that groups all `script.*` entries by label using a template, eliminating the need to add a card per label. Decide during implementation based on UX (one big card vs. one per device).

## Data flow examples

**Send "TV Power":**
1. Tap button on dashboard → script (created from blueprint) runs.
2. HA publishes `cmnd/tasmota_ir/IRSend` with the stored payload — the JSON captured during learn mode is passed through verbatim. Tasmota uses the fields it recognises (`Protocol`, `Bits`, `Data`) and ignores extras (`DataLSB`, `Repeat`, etc.).
3. Tasmota fires IR LED.

**Learn "AC Cool 22":**
1. User toggles learn mode (dashboard).
2. User points AC remote at Tasmota, presses "cool 22".
3. Tasmota publishes `tele/tasmota_ir/RESULT` with `IrReceived` JSON.
4. Capture automation writes the JSON into `input_text.ir_last_code` and pops a notification.
5. User opens Settings → Scripts → Add Script → Create from blueprint *Tasmota IR Send*; pastes the JSON from the helper; names it "AC Cool 22"; assigns label `AC`; Save.
6. The dashboard's `auto-entities` "AC" card picks up the new script automatically — no edits needed.

## Error handling

| Condition | Behavior |
|---|---|
| Learn mode left on | Auto-off after 60 s. |
| No code captured before user goes to save | The "last code" helper is empty/stale — user notices and re-presses remote. |
| MQTT broker down | HA MQTT integration shows unavailable; sends fail with normal HA toast. |
| Long AC code exceeds 255 chars | `input_text` truncates. See *Open questions*. |

## Testing

Manual tests:

1. **MQTT round-trip** — in Developer Tools → Services, call `mqtt.publish` with a known payload; confirm Tasmota log shows `IRSend Done` and target device responds.
2. **Learn flow** — toggle learn mode, press a known remote, confirm `input_text.ir_last_code` updates and the notification fires.
3. **Save flow** — create a script from the blueprint with that payload, label it, confirm it appears on the matching dashboard card and firing it controls the device.
4. **Auto-disable** — toggle learn on, wait 60 s, confirm off.
5. **Persistence** — restart HA; confirm learned scripts, labels, helpers, and dashboard still present.

## Open questions / deferred

- **Long AC codes exceeding 255 chars** in `input_text`: the cleanest fix that stays pure-UI is to use Tasmota's `IRHvac` command instead of raw `IRSend`. Tasmota understands many AC protocols natively (Mitsubishi, Toshiba, Panasonic, LG, Daikin, …) and accepts a short structured payload like `{"Vendor":"Mitsubishi","Power":"On","Mode":"Cool","Temp":22}` — well under 255 chars. For ACs Tasmota doesn't recognise, fall back to capturing the `IrReceived.IRHVAC` parsed object (also short) rather than the raw `Data` blob. Only ACs whose protocol Tasmota cannot parse at all would need a different storage strategy — defer until we hit one.
- **Renaming / deleting / re-labeling codes**: fully supported by HA's native Scripts UI (rename, change label, delete). No extra work needed.
- **Backups**: rely on HA's standard full backups; learned codes live in `.storage/` and labels live in HA's registry, both included automatically.
- **Blueprint hosting**: needs a public URL (GitHub Gist or repo) for the blueprint YAML so the user can import via the UI. Will set up during implementation.

## Out of scope

- Macros / scene chaining (multiple IR codes from one button).
- Multiple Tasmota blasters.
- Programmatic export/import of the IR code library (HA backups cover this implicitly).
