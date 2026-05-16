# Tasmota ↔ Home Assistant IR Bridge

A bidirectional IR bridge using a Tasmota-flashed IR transceiver, configured and operated **entirely through the Home Assistant UI** — no YAML editing, no shell scripts.

## What's in this repo

- **[Design spec](docs/superpowers/specs/2026-05-16-tasmota-ir-bridge-design.md)** — architecture, components, decisions.
- **[Setup runbook](docs/superpowers/plans/2026-05-16-tasmota-ir-bridge.md)** — step-by-step UI clicks to build the bridge from scratch.
- **[End-user cheat sheet](docs/superpowers/specs/2026-05-16-tasmota-ir-bridge-runbook.md)** — one-page reference for everyday use.
- **[Script blueprint](blueprints/script/tasmota_ir/tasmota_ir_send.yaml)** — the only YAML file involved. Paste it into a public GitHub Gist and import the raw URL via HA → Settings → Automations & Scenes → Blueprints → Import Blueprint.

## Quick start

Follow the setup runbook. The high-level flow:

1. Flash Tasmota IR firmware onto your ESP device.
2. Configure Tasmota's MQTT to point at your HA broker (one console command).
3. Create two helpers in HA (text + toggle).
4. Create two automations in HA (capture + auto-disable).
5. Host the blueprint as a public Gist and import its raw URL into HA.
6. Create device labels (TV, AC, Receiver, …).
7. Capture and save your first IR code from the HA UI.
8. Build a Lovelace dashboard view with one card per device label.

## Requirements

- Home Assistant ≥ 2024.4 (for Labels UI).
- HACS with `auto-entities` ≥ v1.13.
- Lovelace dashboards in Storage mode (the default).
- Tasmota device flashed with `tasmota-ir.bin`, MQTT pointed at the same broker as HA.
