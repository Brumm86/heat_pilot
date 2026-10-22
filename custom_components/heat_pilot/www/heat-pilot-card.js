/**
 * Heat Pilot Lovelace card.
 *
 * Framework-free custom element (no lit, no build step, no import/export, so
 * the same file can be served as module and as ES5-fallback script).
 *
 * Registered automatically by the integration (add_extra_js_url) - no manual
 * Lovelace resource is needed. Add it with "type: custom:heat-pilot-card".
 *
 * The card needs no configuration: it discovers every entity of the
 * integration through the entity/device registry. Optional config:
 *   title: "Heizung"        - card title (default "Heat Pilot")
 */
(function () {
  "use strict";

  var TXT = {
    de: {
      title: "Heat Pilot",
      absence: "Abwesenheitsmodus",
      return_at: "Rückkehr",
      period: "Heizperiode",
      period_active: "aktiv",
      period_inactive: "inaktiv",
      period_edit: "Heizperiode ändern",
      period_save: "Speichern",
      period_cancel: "Abbrechen",
      start_day: "Starttag",
      start_month: "Startmonat",
      end_day: "Endtag",
      end_month: "Endmonat",
      period_override: "Heizperiode erzwingen",
      frost_temp: "Frostschutz",
      max_temp: "Maximaltemperatur",
      comfort: "Komfort",
      setback: "Absenkung",
      door_warning: "Türwarnung",
      opening_shutdown: "Aus bei offener Tür/Fenster",
      absence_shutdown: "Aus bei Raumabwesenheit",
      max_limit: "Maximaltemperatur begrenzen",
      skip_setback: "Absenkung heute überspringen",
      edit_plan: "Plan bearbeiten",
      next_change: "Nächster Wechsel",
      open: "offen",
      current: "Ist",
      target: "Soll",
      no_rooms: "Noch keine Räume. Füge sie in den Einstellungen der Integration hinzu.",
      no_entities: "Keine Heat-Pilot-Entitäten gefunden.",
    },
    en: {
      title: "Heat Pilot",
      absence: "Absence mode",
      return_at: "Return",
      period: "Heating period",
      period_active: "active",
      period_inactive: "inactive",
      period_edit: "Edit heating period",
      period_save: "Save",
      period_cancel: "Cancel",
      start_day: "Start day",
      start_month: "Start month",
      end_day: "End day",
      end_month: "End month",
      period_override: "Force heating period",
      frost_temp: "Frost protection",
      max_temp: "Maximum temperature",
      comfort: "Comfort",
      setback: "Setback",
      door_warning: "Door warning",
      opening_shutdown: "Off when door/window open",
      absence_shutdown: "Off when room absent",
      max_limit: "Limit maximum temperature",
      skip_setback: "Skip setback today",
      edit_plan: "Edit schedule",
      next_change: "Next change",
      open: "open",
      current: "Now",
      target: "Target",
      no_rooms: "No rooms yet. Add them on the integration's settings page.",
      no_entities: "No Heat Pilot entities found.",
    },
  };

  var ROOM_SWITCHES = [
    "skip_setback",
    "door_warning",
    "opening_shutdown",
    "absence_shutdown",
    "max_limit",
  ];

  function esc(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function num(value) {
    var n = parseFloat(value);
    return isNaN(n) ? null : n;
  }

  function fmtTemp(value) {
    var n = num(value);
    return n === null ? "–" : n.toFixed(1).replace(".", ",") + " °C";
  }

  var STYLE =
    ":host{display:block}" +
    "ha-card{padding:12px 16px 16px}" +
    "h2{margin:0 0 8px;font-size:1.3em;font-weight:500}" +
    "h3{margin:0;font-size:1.1em;font-weight:500}" +
    ".sec{border-top:1px solid var(--divider-color);padding:12px 0 4px;margin-top:8px}" +
    ".row{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:40px;flex-wrap:wrap}" +
    ".sub{color:var(--secondary-text-color);font-size:.9em}" +
    ".chip{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.85em;background:var(--secondary-background-color)}" +
    ".chip.on{background:var(--primary-color);color:var(--text-primary-color,#fff)}" +
    ".chip.warn{background:var(--error-color,#e53935);color:#fff}" +
    ".stepper{display:flex;align-items:center;gap:6px}" +
    ".stepper button{width:34px;height:34px;border-radius:50%;border:1px solid var(--divider-color);" +
    "background:var(--card-background-color);color:var(--primary-text-color);font-size:1.2em;cursor:pointer;line-height:1}" +
    ".stepper .v{min-width:64px;text-align:center;font-variant-numeric:tabular-nums}" +
    "button.link{background:none;border:1px solid var(--primary-color);color:var(--primary-color);" +
    "border-radius:16px;padding:6px 14px;cursor:pointer;font:inherit}" +
    "button.primary{background:var(--primary-color);color:var(--text-primary-color,#fff);border:none;" +
    "border-radius:16px;padding:6px 14px;cursor:pointer;font:inherit}" +
    ".grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}" +
    ".temps{display:flex;gap:16px;flex-wrap:wrap}" +
    ".editor{padding:8px 0;display:grid;grid-template-columns:1fr 1fr;gap:8px}" +
    ".editor label{display:flex;flex-direction:column;font-size:.85em;gap:2px}" +
    ".editor input,.editor select{font:inherit;padding:6px;border:1px solid var(--divider-color);" +
    "border-radius:6px;background:var(--card-background-color);color:var(--primary-text-color)}" +
    ".actions{display:flex;gap:8px;justify-content:flex-end;margin-top:8px}" +
    ".empty{padding:16px 0;color:var(--secondary-text-color)}";

  class HeatPilotCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {};
      this._sig = "";
      this._periodOpen = false;
      this._periodDraft = null;
      this._bound = false;
    }

    setConfig(config) {
      this._config = config || {};
      this._sig = "";
      this._render();
    }

    static getStubConfig() {
      return {};
    }

    getCardSize() {
      return 10;
    }

    set hass(hass) {
      this._hass = hass;
      var sig = this._signature();
      if (sig !== this._sig) {
        this._sig = sig;
        this._render();
      }
    }

    // ------------------------------------------------------------ helpers

    _t(key) {
      var lang = ((this._hass && this._hass.language) || "en").split("-")[0];
      var table = TXT[lang] || TXT.en;
      return table[key] !== undefined ? table[key] : TXT.en[key] || key;
    }

    /** Find all entities of this integration, grouped by device. */
    _collect() {
      var hass = this._hass;
      var out = { global: {}, rooms: {}, found: 0 };
      if (!hass || !hass.entities) {
        return out;
      }
      var entities = hass.entities;
      var devices = hass.devices || {};
      Object.keys(entities).forEach(function (entityId) {
        var entry = entities[entityId];
        if (!entry || entry.platform !== "heat_pilot" || entry.hidden) {
          return;
        }
        if (!hass.states[entityId]) {
          return;
        }
        var key = entry.translation_key;
        if (!key) {
          return;
        }
        out.found += 1;
        var device = entry.device_id ? devices[entry.device_id] : null;
        if (device && device.entry_type === "service") {
          out.global[key] = entityId;
          return;
        }
        var id = entry.device_id || entityId;
        if (!out.rooms[id]) {
          out.rooms[id] = {
            name: device ? device.name_by_user || device.name : id,
            ents: {},
          };
        }
        out.rooms[id].ents[key] = entityId;
      });
      return out;
    }

    _relevantIds(data) {
      var hass = this._hass;
      var ids = [];
      Object.keys(data.global).forEach(function (k) {
        ids.push(data.global[k]);
      });
      Object.keys(data.rooms).forEach(function (rid) {
        var ents = data.rooms[rid].ents;
        Object.keys(ents).forEach(function (k) {
          ids.push(ents[k]);
        });
        var status = ents.status && hass.states[ents.status];
        var thermostats = (status && status.attributes.thermostats) || [];
        thermostats.forEach(function (t) {
          ids.push(t);
        });
      });
      return ids;
    }

    _signature() {
      var hass = this._hass;
      if (!hass) {
        return "";
      }
      var data = this._collect();
      var parts = [hass.language || "", String(data.found)];
      this._relevantIds(data).forEach(function (id) {
        var st = hass.states[id];
        parts.push(id + "@" + (st ? st.last_updated : "-"));
      });
      Object.keys(data.rooms).forEach(function (rid) {
        parts.push(data.rooms[rid].name);
      });
      return parts.join("|");
    }

    _state(id) {
      return id && this._hass.states[id] ? this._hass.states[id] : null;
    }

    _display(st) {
      if (!st) {
        return "";
      }
      if (typeof this._hass.formatEntityState === "function") {
        try {
          return this._hass.formatEntityState(st);
        } catch (e) {
          /* fall through */
        }
      }
      return st.state;
    }

    // ------------------------------------------------------------- render

    _stepper(entityId, label) {
      var st = this._state(entityId);
      if (!st) {
        return "";
      }
      var unavailable = st.state === "unavailable" || st.state === "unknown";
      return (
        '<div class="row"><span>' + esc(label) + "</span>" +
        '<span class="stepper">' +
        '<button data-act="step" data-ent="' + esc(entityId) + '" data-dir="-1">−</button>' +
        '<span class="v">' + (unavailable ? "–" : fmtTemp(st.state)) + "</span>" +
        '<button data-act="step" data-ent="' + esc(entityId) + '" data-dir="1">+</button>' +
        "</span></div>"
      );
    }

    _toggle(entityId, label) {
      var st = this._state(entityId);
      if (!st) {
        return "";
      }
      return (
        '<div class="row"><span>' + esc(label) + "</span>" +
        '<ha-switch data-act="toggle" data-ent="' + esc(entityId) + '"' +
        (st.state === "on" ? " checked" : "") + "></ha-switch></div>"
      );
    }

    _renderGlobal(g) {
      var html = "";
      var period = this._state(g.heating_period);
      if (period) {
        var a = period.attributes;
        var range = a.start_day + "." + a.start_month + ". – " + a.end_day + "." + a.end_month + ".";
        var active = period.state === "active";
        html +=
          '<div class="row"><span>' + esc(this._t("period")) + " " +
          '<span class="chip ' + (active ? "on" : "") + '">' +
          esc(active ? this._t("period_active") : this._t("period_inactive")) +
          '</span> <span class="sub">' + esc(range) + "</span></span>" +
          '<button class="link" data-act="period-edit">' + esc(this._t("period_edit")) + "</button></div>";
        if (this._periodOpen) {
          var d = this._periodDraft || {
            start_month: a.start_month,
            start_day: a.start_day,
            end_month: a.end_month,
            end_day: a.end_day,
          };
          var self = this;
          var field = function (key, max) {
            return (
              "<label>" + esc(self._t(key)) +
              '<input type="number" inputmode="numeric" min="1" max="' + max + '" data-field="' + key +
              '" value="' + esc(d[key]) + '"></label>'
            );
          };
          html +=
            '<div class="editor">' +
            field("start_day", 31) + field("start_month", 12) +
            field("end_day", 31) + field("end_month", 12) +
            '</div><div class="actions">' +
            '<button class="link" data-act="period-cancel">' + esc(this._t("period_cancel")) + "</button>" +
            '<button class="primary" data-act="period-save">' + esc(this._t("period_save")) + "</button></div>";
        }
      }
      html += this._toggle(g.period_override, this._t("period_override"));
      html += this._toggle(g.absence_mode, this._t("absence"));
      var ret = this._state(g.return_at);
      if (ret) {
        var value = ret.state && ret.state !== "unknown" && ret.state !== "unavailable"
          ? ret.state.replace(" ", "T").slice(0, 16) : "";
        html +=
          '<div class="row"><span>' + esc(this._t("return_at")) + "</span>" +
          '<span data-slot="return" data-ent="' + esc(g.return_at) + '" data-value="' + esc(value) +
          '"></span></div>';
      }
      html += this._stepper(g.frost_temp, this._t("frost_temp"));
      html += this._stepper(g.max_temp, this._t("max_temp"));
      return html;
    }

    _renderRoom(room) {
      var e = room.ents;
      var hass = this._hass;
      var status = this._state(e.status);
      var attrs = status ? status.attributes : {};
      var thermostat = this._state((attrs.thermostats || [])[0]);
      var opening = this._state(e.opening);
      var html = '<div class="sec"><div class="row"><h3>' + esc(room.name) + "</h3><span>";
      if (opening && opening.state === "on") {
        html += '<span class="chip warn">' + esc(this._t("open")) + "</span> ";
      }
      if (status) {
        html += '<span class="chip on">' + esc(this._display(status)) + "</span>";
      }
      html += "</span></div>";
      if (thermostat) {
        html +=
          '<div class="temps sub"><span>' + esc(this._t("current")) + ": " +
          fmtTemp(thermostat.attributes.current_temperature) + "</span><span>" +
          esc(this._t("target")) + ": " + fmtTemp(thermostat.attributes.temperature) + "</span>";
        if (attrs.next_change) {
          html += "<span>" + esc(this._t("next_change")) + ": " + esc(this._fmtTime(attrs.next_change)) + "</span>";
        }
        html += "</div>";
      }
      if ((attrs.thermostats || []).length) {
        html += this._stepper(e.comfort, this._t("comfort"));
        html += this._stepper(e.setback, this._t("setback"));
      }
      var self = this;
      ROOM_SWITCHES.forEach(function (key) {
        if (e[key]) {
          html += self._toggle(e[key], self._t(key));
        }
      });
      if (attrs.schedule && hass.states[attrs.schedule]) {
        html +=
          '<div class="actions"><button class="link" data-act="plan" data-ent="' +
          esc(attrs.schedule) + '">' + esc(this._t("edit_plan")) + "</button></div>";
      }
      return html + "</div>";
    }

    _fmtTime(value) {
      var d = new Date(value);
      if (isNaN(d.getTime())) {
        return String(value);
      }
      try {
        return d.toLocaleString(this._hass.language, {
          weekday: "short", hour: "2-digit", minute: "2-digit",
        });
      } catch (e) {
        return d.toLocaleString();
      }
    }

    _render() {
      var root = this.shadowRoot;
      if (!root) {
        return;
      }
      if (!this._hass) {
        root.innerHTML = "<style>" + STYLE + "</style><ha-card></ha-card>";
        return;
      }
      var data = this._collect();
      var html = "<style>" + STYLE + "</style><ha-card><h2>" +
        esc(this._config.title || this._t("title")) + "</h2>";
      if (!data.found) {
        html += '<div class="empty">' + esc(this._t("no_entities")) + "</div>";
      } else {
        html += this._renderGlobal(data.global);
        var ids = Object.keys(data.rooms).sort(function (a, b) {
          return String(data.rooms[a].name).localeCompare(String(data.rooms[b].name));
        });
        if (!ids.length) {
          html += '<div class="empty">' + esc(this._t("no_rooms")) + "</div>";
        }
        for (var i = 0; i < ids.length; i++) {
          html += this._renderRoom(data.rooms[ids[i]]);
        }
      }
      html += "</ha-card>";
      root.innerHTML = html;
      this._wire(root);
    }

    // ------------------------------------------------------------- events

    _wire(root) {
      var self = this;
      var nodes = root.querySelectorAll("[data-act]");
      Array.prototype.forEach.call(nodes, function (node) {
        var act = node.getAttribute("data-act");
        if (act === "toggle") {
          node.addEventListener("change", function () {
            self._call("switch", node.checked ? "turn_on" : "turn_off", {
              entity_id: node.getAttribute("data-ent"),
            });
          });
        } else {
          node.addEventListener("click", function () {
            self._click(act, node);
          });
        }
      });
      this._mountDatetime(root);
      var inputs = root.querySelectorAll("[data-field]");
      Array.prototype.forEach.call(inputs, function (input) {
        input.addEventListener("input", function () {
          self._periodDraft = self._periodDraft || {};
          self._periodDraft[input.getAttribute("data-field")] = input.value;
        });
      });
    }

    /** HA's own selector when available (works in the companion app), else a native input. */
    _mountDatetime(root) {
      var self = this;
      var slot = root.querySelector('[data-slot="return"]');
      if (!slot) {
        return;
      }
      var ent = slot.getAttribute("data-ent");
      var value = slot.getAttribute("data-value");
      var send = function (v) {
        var data = { entity_id: ent };
        if (v) {
          data.datetime = String(v).replace("T", " ").slice(0, 16) + ":00";
        }
        self._call("datetime", "set_value", data);
      };
      if (customElements.get("ha-selector")) {
        var el = document.createElement("ha-selector");
        el.hass = this._hass;
        el.selector = { datetime: {} };
        el.value = value ? value.replace("T", " ") + ":00" : undefined;
        el.addEventListener("value-changed", function (ev) {
          ev.stopPropagation();
          if (ev.detail && ev.detail.value && ev.detail.value !== el.value) {
            el.value = ev.detail.value;
            send(ev.detail.value);
          }
        });
        slot.appendChild(el);
      } else {
        var input = document.createElement("input");
        input.type = "datetime-local";
        input.value = value;
        input.addEventListener("change", function () {
          send(input.value);
        });
        slot.appendChild(input);
      }
    }

    _click(act, node) {
      var ent = node.getAttribute("data-ent");
      if (act === "step") {
        var st = this._state(ent);
        if (!st) {
          return;
        }
        var step = num(st.attributes.step) || 0.5;
        var min = num(st.attributes.min);
        var max = num(st.attributes.max);
        var value = (num(st.state) || 0) + step * parseInt(node.getAttribute("data-dir"), 10);
        if (min !== null) value = Math.max(min, value);
        if (max !== null) value = Math.min(max, value);
        this._call("number", "set_value", { entity_id: ent, value: Math.round(value * 100) / 100 });
      } else if (act === "plan") {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: ent },
            bubbles: true,
            composed: true,
          })
        );
      } else if (act === "period-edit") {
        this._periodOpen = !this._periodOpen;
        this._periodDraft = null;
        this._render();
      } else if (act === "period-cancel") {
        this._periodOpen = false;
        this._periodDraft = null;
        this._render();
      } else if (act === "period-save") {
        var d = this._periodDraft || {};
        var current = this._state(this._collect().global.heating_period);
        var a = current ? current.attributes : {};
        var pick = function (key) {
          var n = parseInt(d[key] !== undefined ? d[key] : a[key], 10);
          return isNaN(n) ? a[key] : n;
        };
        this._call("heat_pilot", "set_heating_period", {
          start_month: pick("start_month"),
          start_day: pick("start_day"),
          end_month: pick("end_month"),
          end_day: pick("end_day"),
        });
        this._periodOpen = false;
        this._periodDraft = null;
        this._render();
      }
    }

    _call(domain, service, data) {
      return this._hass.callService(domain, service, data).catch(function (err) {
        // Surface validation errors (e.g. an invalid date) to the user.
        window.alert(err && err.message ? err.message : String(err));
      });
    }
  }

  if (!customElements.get("heat-pilot-card")) {
    customElements.define("heat-pilot-card", HeatPilotCard);
  }

  // Same recovery as the family_tasks card: some Android WebViews swap out
  // window.customElements after this script ran, so Lovelace would not find
  // the element. Re-define it once <home-assistant> is known to the registry
  // that is current at that point. The guard avoids a second define() on the
  // same registry, which would throw.
  if (typeof customElements !== "undefined" && customElements.whenDefined) {
    customElements
      .whenDefined("home-assistant")
      .then(function () {
        if (!customElements.get("heat-pilot-card")) {
          customElements.define("heat-pilot-card", HeatPilotCard);
        }
      })
      .catch(function () {
        /* not inside a normal HA frontend - nothing to recover */
      });
  }

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "heat-pilot-card",
    name: "Heat Pilot",
    description: "Raumweise Heizungssteuerung: Status, Temperaturen, Schalter und Zeitplan.",
  });
})();
