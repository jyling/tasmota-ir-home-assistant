# Tasmota IR Bridge — End-User Cheat Sheet

A one-page reference for everyday use after the bridge is set up.

## Add a new IR button

1. Open the **IR Remote** dashboard view.
2. Toggle **IR Learn Mode** on (auto-disables after 60 s).
3. Point the physical remote at the Tasmota device and press the button you want to learn.
4. The **Last captured code** markdown card on the dashboard will update with a JSON string. Copy it.
5. Go to **Settings → Scripts → + Add Script → Create script from blueprint** → pick **Tasmota IR Send**.
6. Paste the JSON into **IR payload (JSON)**.
7. Name the script (e.g. `TV Volume Up`).
8. On the script's edit page, click the **labels** icon and assign the device label (e.g. `TV`).
9. **Save**.

The new button appears automatically on the matching device card — no dashboard edits needed.

## Send an IR code

Tap the button on the IR Remote dashboard. That's it.

## Rename, relabel, or delete a button

**Settings → Scripts** → click the script → edit name / label, or delete. The dashboard updates automatically.

## Add a new device group (label)

**Settings → Labels → + Add Label**. Then add a new dashboard card:

1. IR Remote view → pencil → **+ Add Card** → **Manual** (YAML mode).
2. Paste:
   ```yaml
   type: custom:auto-entities
   card:
     type: grid
     columns: 3
     title: <Device name>
   filter:
     include:
       - domain: script
         label: <label_id>
   sort:
     method: friendly_name
   ```
3. Replace `<Device name>` and `<label_id>`. Save.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Capture doesn't update `input_text.ir_last_code` | Learn mode is off, or the **IR: Capture received code** automation is disabled. Check both. |
| Capture works but JSON looks like `{"IrReceived": …}` (nested) | The capture automation's action value is wrong — should be `{{ trigger.payload_json.IrReceived | to_json }}`, not `{{ trigger.payload }}`. |
| Button on dashboard does nothing, but Tasmota console shows no `IRSend` | Wrong MQTT topic on the script. Default should be `cmnd/tasmota_ir/IRSend`. |
| Tasmota console shows `IRSend Done` but device doesn't respond | IR LED is out of range or wrong angle — get closer, line of sight. |
| New button doesn't appear on dashboard | Label not assigned, or `auto-entities` version is below v1.13 (label filter unsupported). |
| Long AC code is truncated in `input_text` (255-char limit) | Use Tasmota's `IRHvac` payload instead: `{"Vendor":"Mitsubishi","Power":"On","Mode":"Cool","Temp":22}` — much shorter. Tasmota supports many AC protocols natively. |

## Backups

HA's full backups (Settings → System → Backups) automatically include all helpers, automations, labels, scripts, and the dashboard view. No separate IR export is needed.

## Files in this repo

- **`blueprints/script/tasmota_ir/tasmota_ir_send.yaml`** — the script blueprint. Paste this into a public GitHub Gist and import the raw URL via HA's **Settings → Automations & Scenes → Blueprints → Import Blueprint**.
- **`docs/superpowers/specs/2026-05-16-tasmota-ir-bridge-design.md`** — full design spec.
- **`docs/superpowers/plans/2026-05-16-tasmota-ir-bridge.md`** — step-by-step setup runbook.
