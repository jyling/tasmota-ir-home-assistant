/**
 * Tasmota IR Remote Lovelace card.
 *
 * Generic card bound to a `remote.*` entity produced by the tasmota_ir
 * integration. Renders one tile per command in `attributes.commands`,
 * plus a "+ Learn New Button" tile that prompts for a name and calls
 * `remote.learn_command`.
 *
 * Usage:
 *   type: custom:tasmota-ir-card
 *   entity: remote.living_room_tv
 *   title: Living Room TV       # optional override
 *   subtitle: Hisense · TV       # optional override
 *   columns: 3                   # optional, default 3
 *   learn_timeout: 20            # optional, default 20
 */

const CARD_VERSION = "0.1.0";

const STYLE = `
  :host { display: block; }
  ha-card {
    padding: 16px 16px 20px;
    background: var(--card-background-color, #1c1c1e);
    border-radius: 16px;
  }
  .header { margin-bottom: 16px; }
  .title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--primary-text-color, #fff);
  }
  .subtitle {
    margin-top: 2px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--secondary-text-color, #a0a0a0);
    font-size: 0.9rem;
  }
  .subtitle .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff5555;
    display: inline-block;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(var(--ti-cols, 3), 1fr);
    gap: 10px;
  }
  button.tile {
    appearance: none;
    border: none;
    background: var(--secondary-background-color, #2c2c2e);
    color: var(--primary-text-color, #fff);
    padding: 14px 10px;
    border-radius: 12px;
    font-size: 0.95rem;
    cursor: pointer;
    transition: background 0.15s, transform 0.05s;
    text-transform: capitalize;
  }
  button.tile:hover { background: var(--state-icon-color, #3a3a3c); }
  button.tile:active { transform: scale(0.97); }
  button.learn {
    grid-column: 1 / -1;
    margin-top: 6px;
    background: transparent;
    border: 1px dashed var(--divider-color, #555);
    color: var(--secondary-text-color, #a0a0a0);
    padding: 14px 10px;
    border-radius: 12px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button.learn:hover {
    border-color: var(--primary-color, #03a9f4);
    color: var(--primary-color, #03a9f4);
  }
  button.learn.busy {
    border-style: solid;
    border-color: var(--primary-color, #03a9f4);
    color: var(--primary-color, #03a9f4);
    cursor: wait;
  }
  .empty {
    color: var(--secondary-text-color, #a0a0a0);
    font-size: 0.9rem;
    padding: 16px 0;
    text-align: center;
  }
`;

function prettify(name) {
  return name.replace(/_/g, " ");
}

class TasmotaIrCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._learning = false;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("`entity` is required (e.g. remote.living_room_tv)");
    }
    if (!config.entity.startsWith("remote.")) {
      throw new Error("`entity` must be a remote.* entity");
    }
    this._config = {
      columns: 3,
      learn_timeout: 20,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  _stateObj() {
    if (!this._hass || !this._config) return null;
    return this._hass.states[this._config.entity] || null;
  }

  _commands() {
    const s = this._stateObj();
    return (s && Array.isArray(s.attributes.commands)) ? s.attributes.commands : [];
  }

  _title() {
    if (this._config.title) return this._config.title;
    const s = this._stateObj();
    return (s && s.attributes.friendly_name) || this._config.entity;
  }

  _subtitle() {
    if (this._config.subtitle !== undefined) return this._config.subtitle;
    const s = this._stateObj();
    if (!s) return "";
    const m = s.attributes.manufacturer;
    const md = s.attributes.model;
    if (m && md) return `${m} · ${md}`;
    return m || md || "";
  }

  async _send(cmd) {
    try {
      await this._hass.callService("remote", "send_command", {
        entity_id: this._config.entity,
        command: [cmd],
      });
    } catch (err) {
      alert(`Failed to send "${cmd}": ${err.message || err}`);
    }
  }

  async _learn() {
    if (this._learning) return;
    const name = window.prompt(
      "Name for the new IR button (e.g. power, volume_up):"
    );
    if (!name) return;
    const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    if (!slug) {
      alert("Invalid name.");
      return;
    }
    if (this._commands().includes(slug)) {
      if (!confirm(`"${slug}" already exists. Overwrite?`)) return;
    }

    this._learning = true;
    this._render();
    try {
      await this._hass.callService("remote", "learn_command", {
        entity_id: this._config.entity,
        command: [slug],
        timeout: this._config.learn_timeout,
      });
      // The entity state updates automatically; render will catch up.
    } catch (err) {
      alert(`Learn failed: ${err.message || err}`);
    } finally {
      this._learning = false;
      this._render();
    }
  }

  _render() {
    if (!this.shadowRoot) return;
    if (!this._config) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    const cmds = this._commands();
    const title = this._title();
    const subtitle = this._subtitle();
    const cols = this._config.columns || 3;

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card style="--ti-cols: ${cols};">
        <div class="header">
          <div class="title">${escapeHtml(title)}</div>
          ${subtitle ? `<div class="subtitle"><span class="dot"></span>${escapeHtml(subtitle)}</div>` : ""}
        </div>
        ${cmds.length === 0 ? `<div class="empty">No buttons yet — tap "+ Learn New Button" below.</div>` : ""}
        <div class="grid">
          ${cmds.map(c => `<button class="tile" data-cmd="${escapeAttr(c)}">${escapeHtml(prettify(c))}</button>`).join("")}
          <button class="learn ${this._learning ? "busy" : ""}">
            ${this._learning ? "Press your remote at the IR receiver…" : "+ Learn New Button"}
          </button>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("button.tile").forEach(b => {
      b.addEventListener("click", () => this._send(b.dataset.cmd));
    });
    const learnBtn = this.shadowRoot.querySelector("button.learn");
    if (learnBtn) learnBtn.addEventListener("click", () => this._learn());
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function escapeAttr(s) {
  return escapeHtml(s);
}

// -----------------------------------------------------------------------------
// Visual editor — so the user never has to write YAML to add the card.
// -----------------------------------------------------------------------------

const EDITOR_STYLE = `
  :host { display: block; padding: 8px; }
  .row { display: block; margin-bottom: 12px; }
  label { display: block; font-size: 0.85rem; color: var(--secondary-text-color); margin-bottom: 4px; }
  input[type="text"], input[type="number"] {
    width: 100%;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--divider-color, #555);
    background: var(--card-background-color, #1c1c1e);
    color: var(--primary-text-color, #fff);
    box-sizing: border-box;
  }
  .help { font-size: 0.8rem; color: var(--secondary-text-color); margin-top: 4px; }
`;

class TasmotaIrCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { columns: 3, learn_timeout: 20, ...(config || {}) };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _emit() {
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }

  _onInput(key, value) {
    if (value === "" || value === undefined || value === null) {
      delete this._config[key];
    } else if (key === "columns" || key === "learn_timeout") {
      const n = Number(value);
      if (!Number.isNaN(n) && n > 0) this._config[key] = n;
    } else {
      this._config[key] = value;
    }
    this._emit();
  }

  _remoteEntities() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => id.startsWith("remote."))
      .sort();
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const entities = this._remoteEntities();
    const c = this._config;
    this.shadowRoot.innerHTML = `
      <style>${EDITOR_STYLE}</style>
      <div class="row">
        <label>Remote entity (required)</label>
        <select id="entity">
          <option value="">— select —</option>
          ${entities.map(e => `<option value="${e}" ${e === c.entity ? "selected" : ""}>${e}</option>`).join("")}
        </select>
        <div class="help">Pick the remote.* entity from the Tasmota IR integration.</div>
      </div>
      <div class="row">
        <label>Title override (optional)</label>
        <input type="text" id="title" value="${c.title || ""}" placeholder="(uses entity friendly name)">
      </div>
      <div class="row">
        <label>Subtitle override (optional)</label>
        <input type="text" id="subtitle" value="${c.subtitle || ""}" placeholder="(uses manufacturer · model)">
      </div>
      <div class="row">
        <label>Columns</label>
        <input type="number" id="columns" min="1" max="6" value="${c.columns ?? 3}">
      </div>
      <div class="row">
        <label>Learn timeout (seconds)</label>
        <input type="number" id="learn_timeout" min="5" max="120" value="${c.learn_timeout ?? 20}">
      </div>
    `;

    const wire = (id) => {
      const el = this.shadowRoot.getElementById(id);
      if (!el) return;
      el.addEventListener("change", () => this._onInput(id, el.value));
      el.addEventListener("input", () => this._onInput(id, el.value));
    };
    ["entity", "title", "subtitle", "columns", "learn_timeout"].forEach(wire);
  }
}

customElements.define("tasmota-ir-card-editor", TasmotaIrCardEditor);

// Tell Lovelace this card has a visual editor.
TasmotaIrCard.getConfigElement = function () {
  return document.createElement("tasmota-ir-card-editor");
};
TasmotaIrCard.getStubConfig = function (hass) {
  const firstRemote = Object.keys(hass.states).find(id => id.startsWith("remote."));
  return { entity: firstRemote || "" };
};

customElements.define("tasmota-ir-card", TasmotaIrCard);

// Register in the Lovelace card picker.
window.customCards = window.customCards || [];
window.customCards.push({
  type: "tasmota-ir-card",
  name: "Tasmota IR Remote",
  description: "A generic remote card bound to a tasmota_ir remote.* entity.",
  preview: false,
});

console.info(
  `%c TASMOTA-IR-CARD %c v${CARD_VERSION} `,
  "color: white; background: #03a9f4; font-weight: 700;",
  "color: #03a9f4; background: white; font-weight: 700;"
);
