# Tasmota IR Bridge — Implementation Plan

> **For agentic workers:** This plan is a **runbook executed by a human in the Home Assistant UI**, not a code-edit plan. There is almost no code, no test framework, and no git repo to commit to. Each step is a discrete UI action with an explicit verification. Tick the checkbox after the verification passes.

**Goal:** Build a bidirectional Tasmota↔HA IR bridge (send + learn, grouped by device labels) configured entirely through the HA UI.

**Architecture:** Tasmota IR transceiver communicates with HA via MQTT. A UI-imported script blueprint turns each learned code into a button-callable script. HA Labels group scripts by device. A Lovelace view uses `auto-entities` (HACS) to render one card per device label.

**Tech stack:** Home Assistant ≥ 2024.4 (Labels), Mosquitto (MQTT broker), Tasmota firmware `tasmota-ir.bin`, HACS + `auto-entities` ≥ v1.13, GitHub Gist (one-time blueprint hosting).

**Reference spec:** [docs/superpowers/specs/2026-05-16-tasmota-ir-bridge-design.md](../specs/2026-05-16-tasmota-ir-bridge-design.md)

---

## Task 0: Prerequisite check

**Files:** none.

- [ ] **Step 0.1: Confirm HA version**

  Open Settings → About. Verify version is **2024.4 or later**. If older, upgrade first (Labels UI is unavailable below 2024.4).

- [ ] **Step 0.2: Confirm MQTT integration is configured**

  Settings → Devices & Services. Verify **MQTT** integration is present and connected (not "retry"). If absent, add it pointing at your Mosquitto broker.

- [ ] **Step 0.3: Confirm HACS + auto-entities**

  Settings → HACS → Frontend. Verify **auto-entities** is installed and **v1.13.0 or later**. If older, update.

- [ ] **Step 0.4: Confirm Lovelace is in Storage mode**

  Open any dashboard, click the pencil ("Edit dashboard") icon top-right. If a "Take control" dialog appears, you are in YAML mode — abort and convert to Storage mode before continuing, or this plan's "UI-only" guarantee will not hold.

---

## Task 1: Tasmota device configuration

**Files:** none (device-side configuration through the Tasmota web console).

- [ ] **Step 1.1: Open Tasmota web console**

  Browse to the device's IP. Click **Console**.

- [ ] **Step 1.2: Apply MQTT + IR settings**

  Paste this single line and press Enter (replace `<broker>`, `<u>`, `<p>` with your broker host/user/password):

  ```
  Backlog Topic tasmota_ir; SetOption38 1; TelePeriod 60; MqttHost <broker>; MqttUser <u>; MqttPassword <p>
  ```

  Expected: device reboots, reconnects to MQTT.

- [ ] **Step 1.3: Confirm GPIO assignments**

  Tasmota main page → **Configuration → Configure Module**. Verify:
  - One GPIO is set to **IRsend (8)** (the IR LED).
  - One GPIO is set to **IRrecv (51)** (the IR receiver).

  Save and reboot if you changed anything.

- [ ] **Step 1.4: Verify IR receive end-to-end (no HA yet)**

  Back on **Console**, point any IR remote at the device and press a button. Expect a log line containing `IrReceived` with `Protocol`, `Bits`, and `Data` fields, e.g.:

  ```
  MQT: tele/tasmota_ir/RESULT = {"IrReceived":{"Protocol":"NEC","Bits":32,"Data":"0x20DF10EF",...}}
  ```

  If nothing appears: GPIO assignment is wrong, or the IR receiver is wired backwards. Fix before continuing.

---

## Task 2: Create the helpers

**Files:** none (HA UI).

- [ ] **Step 2.1: Create text helper `ir_last_code`**

  Settings → Devices & Services → **Helpers** → **+ Create Helper** → **Text**.
  - Name: `IR Last Code`
  - Entity ID: `input_text.ir_last_code`
  - Max length: `255`
  - Mode: text
  - Submit.

- [ ] **Step 2.2: Create toggle helper `ir_learn_mode`**

  Helpers → **+ Create Helper** → **Toggle**.
  - Name: `IR Learn Mode`
  - Entity ID: `input_boolean.ir_learn_mode`
  - Submit.

- [ ] **Step 2.3: Verify the helpers exist**

  Developer Tools → States. Filter by `ir_`. Expect both entities present and `unknown`/`off`.

---

## Task 3: MQTT capture automation

**Files:** none (HA UI).

- [ ] **Step 3.1: Create the automation skeleton**

  Settings → **Automations & Scenes** → **+ Create Automation** → **Start with an empty automation**.

  - Name: `IR: Capture received code`
  - Mode: `single`

- [ ] **Step 3.2: Add MQTT trigger**

  Add trigger → **MQTT**.
  - Topic: `tele/tasmota_ir/RESULT`

- [ ] **Step 3.3: Add conditions**

  Add condition → **State**: `input_boolean.ir_learn_mode` is `on`.

  Add condition → **Template**:
  ```jinja
  {{ 'IrReceived' in trigger.payload }}
  ```

- [ ] **Step 3.4: Add action — write to helper**

  Add action → **Call service**: `input_text.set_value`.
  - Target: `input_text.ir_last_code`
  - Service data (YAML mode of the action editor):
    ```yaml
    value: "{{ trigger.payload_json.IrReceived | to_json }}"
    ```

- [ ] **Step 3.5: Add action — notification**

  Add action → **Call service**: `persistent_notification.create`.
  - Service data:
    ```yaml
    title: "IR code captured"
    message: "Go to Settings → Scripts → Add → Create from blueprint to save it."
    notification_id: ir_capture
    ```

- [ ] **Step 3.6: Save and verify**

  Save. Then:
  - Turn `input_boolean.ir_learn_mode` on (Developer Tools → Services → `input_boolean.turn_on`).
  - Press a remote button at the Tasmota device.
  - Expect `input_text.ir_last_code` to update with a JSON string and a notification to appear.

---

## Task 4: Auto-disable learn mode automation

**Files:** none (HA UI).

- [ ] **Step 4.1: Create automation**

  Automations → **+ Create Automation** → empty.

  - Name: `IR: Auto-disable learn mode`
  - **Mode: `restart`** (critical — re-toggling resets the timer instead of queuing).

- [ ] **Step 4.2: Trigger**

  State trigger: `input_boolean.ir_learn_mode` changes to `on`.

- [ ] **Step 4.3: Actions**

  - **Delay** 0:01:00 (1 minute).
  - **Call service** `input_boolean.turn_off` → target `input_boolean.ir_learn_mode`.

- [ ] **Step 4.4: Verify**

  Turn learn mode on. Wait 60 s. Expect it to turn off automatically. Then turn on, wait 30 s, turn off, immediately turn on again — expect a full fresh 60 s countdown (not the previous timer continuing).

---

## Task 5: Host the script blueprint

**Files:**
- Create (one-time, on gist.github.com): `tasmota_ir_send.yaml`

- [ ] **Step 5.1: Create a public Gist**

  Go to https://gist.github.com → **+** New gist (you may need to sign in).
  - Filename: `tasmota_ir_send.yaml`
  - Content (paste exactly):

  ```yaml
  blueprint:
    name: Tasmota IR Send
    description: Send a stored IR code through a Tasmota IR blaster.
    domain: script
    input:
      ir_payload:
        name: IR payload (JSON)
        description: The IrReceived JSON object captured during learn mode, or an IRHvac payload.
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

  Click **Create public gist**.

- [ ] **Step 5.2: Copy the raw URL**

  On the gist page, click **Raw**. Copy the URL from the browser (it ends with `/raw/tasmota_ir_send.yaml`). Save this URL — you'll paste it next.

- [ ] **Step 5.3: Import blueprint into HA**

  HA → Settings → **Automations & Scenes** → **Blueprints** tab → **Import Blueprint** (top-right button).
  - Paste the raw URL.
  - Preview shows "Tasmota IR Send" — click **Preview & Import** → **Import**.

- [ ] **Step 5.4: Verify**

  The Blueprints list now shows **Tasmota IR Send** under the **Script** section. If it appears under "Automation", the `domain: script` line was edited incorrectly — fix the gist and re-import.

---

## Task 6: Create device-group labels

**Files:** none (HA UI).

- [ ] **Step 6.1: Open Labels**

  Settings → **Labels**.

- [ ] **Step 6.2: Create initial labels**

  Click **+ Add Label** and create one per device you plan to learn codes for. Suggested starting set:
  - `TV` (id: `tv`)
  - `AC` (id: `ac`)
  - `Receiver` (id: `receiver`)

  More can be added any time.

- [ ] **Step 6.3: Verify**

  Settings → Labels list shows the labels with their auto-generated IDs (lowercased). Note the **label ID** strings — you'll use them in the dashboard cards.

---

## Task 7: Capture your first IR code and save it as a script

This task is the end-to-end smoke test for the whole bridge.

**Files:** none (HA UI).

- [ ] **Step 7.1: Toggle learn mode on**

  Developer Tools → Services → `input_boolean.turn_on` → target `input_boolean.ir_learn_mode`. (A dashboard toggle will exist after Task 8.)

- [ ] **Step 7.2: Press your TV remote's Power button**

  Aim at the Tasmota device.

- [ ] **Step 7.3: Confirm capture**

  Developer Tools → States → `input_text.ir_last_code`. The value should be a JSON string like:
  ```
  {"Protocol":"NEC","Bits":32,"Data":"0x20DF10EF","DataLSB":"0x0,...","Repeat":0}
  ```
  Copy this value — you'll paste it into the blueprint form.

- [ ] **Step 7.4: Create the script from the blueprint**

  Settings → **Scripts** → **+ Add Script** → **Create script from blueprint** → select **Tasmota IR Send**.
  - Name: `TV Power`
  - `IR payload (JSON)`: paste the JSON from step 7.3.
  - `MQTT command topic`: leave default `cmnd/tasmota_ir/IRSend`.
  - Click the **labels** icon on this script's edit page → assign label `TV`.
  - Save.

- [ ] **Step 7.5: Test the new script**

  In the Scripts list, click the play icon next to `TV Power`. Expect the actual TV to power on/off. If nothing happens:
  - Tasmota console should still show `MQT: stat/tasmota_ir/RESULT = {"IRSend":"Done"}`. If yes, IR-LED-to-TV alignment/range is the issue.
  - If no `IRSend` log: the MQTT topic was wrong — re-check the script's payload and topic.

---

## Task 8: Build the Lovelace dashboard

**Files:** none (HA dashboard editor).

- [ ] **Step 8.1: Add a new view**

  Open your dashboard → pencil (Edit) → **+** to the right of the view tabs → **New view**.
  - Title: `IR Remote`
  - Icon: `mdi:remote`
  - View type: `Sections` (or `Masonry`, your preference).
  - Save.

- [ ] **Step 8.2: Add the Learn card**

  Add card → **Entities**.
  - Title: `IR Learn`
  - Entities:
    - `input_boolean.ir_learn_mode`
    - `input_text.ir_last_code` (set "Secondary info" to `last-changed` so you can see when it was captured).
  - Below, add a **Markdown** card with:
    > Toggle learn mode, press your remote, then **Settings → Scripts → Add → Create from blueprint** to save it.

- [ ] **Step 8.3: Add one Send card per label**

  For **each label** you created in Task 6, add a card → **Manual** (or click the YAML toggle) and paste:

  ```yaml
  type: custom:auto-entities
  card:
    type: grid
    columns: 3
    square: false
    title: TV
  filter:
    include:
      - domain: script
        label: tv
  sort:
    method: friendly_name
  ```

  Substitute the **label ID** (lowercase) and the **title** for each device. Save.

- [ ] **Step 8.4: Verify**

  The `TV` card should now show a button for `TV Power` (from Task 7). Tap it — the TV should respond.

- [ ] **Step 8.5: Add a Recent-Captures markdown card (optional)**

  Add a **Markdown** card to make the last captured code easier to copy when saving new scripts:

  ```yaml
  type: markdown
  content: |
    **Last captured code (copy this when creating a script):**
    ```
    {{ states('input_text.ir_last_code') }}
    ```
  ```

---

## Task 9: Acceptance tests

Run all of these in order. Tick each only after the listed expected outcome is observed.

- [ ] **9.1 Learn round-trip:** Toggle learn mode from the dashboard → press a remote → `input_text.ir_last_code` updates → notification appears. ✔
- [ ] **9.2 Auto-disable:** Learn mode turns off 60 s after toggling on. ✔
- [ ] **9.3 Auto-disable reset:** Toggle on, wait 30 s, toggle off, immediately toggle on → fresh 60 s countdown begins. ✔
- [ ] **9.4 Save flow:** Create a second script from the blueprint with a captured code, label it. New button appears on the matching dashboard card without editing the dashboard. ✔
- [ ] **9.5 Send works:** Tap the new button → target device responds. ✔
- [ ] **9.6 Multi-group:** Create at least one code per device group. Each appears only in its own card. ✔
- [ ] **9.7 Persistence:** Restart HA (Settings → System → Restart). After restart, all helpers, automations, labels, scripts, and the dashboard view are intact and functional. ✔
- [ ] **9.8 Rename/relabel:** Edit one script's name and change its label via the Scripts UI. The dashboard reflects the change (it moves to the other group's card). ✔

---

## Task 10: Document for the user

**Files:**
- Create: `docs/superpowers/specs/2026-05-16-tasmota-ir-bridge-runbook.md` (a short end-user reference distilled from this plan).

- [ ] **Step 10.1: Write a one-page "How to add a new IR button" cheat sheet** that covers:
  1. Toggle learn mode on the IR Remote view.
  2. Press the remote button.
  3. Copy `input_text.ir_last_code` from the dashboard (the markdown card in step 8.5).
  4. Settings → Scripts → Add → Create from blueprint → *Tasmota IR Send* → paste payload → name → assign label → Save.
  5. Done — the button is on the dashboard.

- [ ] **Step 10.2: Note the long-AC-code workaround** (use Tasmota's `IRHvac` command with a parsed payload). Reference the spec's open-questions section.

---

## Out of scope (for reference)

- Macros / scene chaining (multiple IR codes from one button).
- Multiple Tasmota blasters with routing.
- Programmatic export/import of the IR code library — covered by HA full backups.
