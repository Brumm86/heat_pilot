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
 *
 * Layout: header with status chips, alert banner, collapsible general
 * settings and one tile per room (current/target temperature, quick +/-).
 * Tapping a tile opens its details across the full width (one at a time).
 *
 * Tiles can be rearranged by drag and drop (mouse: drag; touch: long-press,
 * then drag). The order is stored per user (frontend user data, with
 * localStorage as fallback) and survives reloads and device changes.
 */
(function () {
  "use strict";

  var TXT = {
    de: {
      title: "Heat Pilot",
      general: "Allgemeine Einstellungen",
      expand: "Aufklappen",
      collapse: "Einklappen",
      absence: "Abwesenheitsmodus",
      absence_chip: "Abwesend",
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
      period_paused: "Heizperiode pausieren",
      plan_paused: "Heizplan heute pausieren",
      pair_start: "Anlernmodus starten",
      pair_started: "Anlernmodus aktiv (2 Min.)",
      frost_temp: "Frostschutz",
      max_temp: "Maximaltemperatur",
      comfort: "Komfort",
      setback: "Absenkung",
      door_warning: "Türwarnung",
      door_warning_setback_only: "Türwarnung nur in der Absenkung",
      door_warning_heating_only: "Türwarnung nur beim Heizen",
      alerts: "Aktive Meldungen",
      since: "seit",
      opening_shutdown: "Aus bei offener Tür/Fenster",
      absence_shutdown: "Aus bei Raumabwesenheit",
      max_limit: "Maximaltemperatur begrenzen",
      skip_setback: "Absenkung heute überspringen",
      boost: "Boost",
      boost_until: "bis",
      boost_minutes: "Boost-Dauer",
      night_setback: "Erzwungene Nachtabsenkung",
      night_next: "Nächste Absenkung",
      night_later: "+1 Std.",
      night_weekday: "Nacht So–Do",
      night_weekend: "Nacht Fr+Sa",
      night_to: "bis",
      setpoint: "Solltemperatur",
      edit_plan: "Plan bearbeiten",
      next_change: "Nächster Wechsel",
      open: "offen",
      closed: "geschlossen",
      current: "Ist",
      target: "Soll",
      status: "Status",
      grp_temps: "Temperaturen",
      grp_boost: "Boost",
      grp_plan: "Plan",
      grp_door: "Tür / Fenster",
      grp_protect: "Schutz",
      grp_limits: "Grenzwerte",
      grp_night: "Nachtabsenkung",
      lower: "Soll senken",
      raise: "Soll erhöhen",
      dismiss: "Schließen",
      no_rooms: "Noch keine Räume. Füge sie in den Einstellungen der Integration hinzu.",
      no_entities: "Keine Heat-Pilot-Entitäten gefunden.",
    },
    en: {
      title: "Heat Pilot",
      general: "General settings",
      expand: "Expand",
      collapse: "Collapse",
      absence: "Absence mode",
      absence_chip: "Away",
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
      period_paused: "Pause heating period",
      plan_paused: "Pause schedule today",
      pair_start: "Start pairing mode",
      pair_started: "Pairing mode active (2 min)",
      frost_temp: "Frost protection",
      max_temp: "Maximum temperature",
      comfort: "Comfort",
      setback: "Setback",
      door_warning: "Door warning",
      door_warning_setback_only: "Door warning only during setback",
      door_warning_heating_only: "Door warning only while heating",
      alerts: "Active alerts",
      since: "since",
      opening_shutdown: "Off when door/window open",
      absence_shutdown: "Off when room absent",
      max_limit: "Limit maximum temperature",
      skip_setback: "Skip setback today",
      boost: "Boost",
      boost_until: "until",
      boost_minutes: "Boost duration",
      night_setback: "Forced night setback",
      night_next: "Next setback",
      night_later: "+1 h",
      night_weekday: "Night Sun–Thu",
      night_weekend: "Night Fri+Sat",
      night_to: "to",
      setpoint: "Target temperature",
      edit_plan: "Edit schedule",
      next_change: "Next change",
      open: "open",
      closed: "closed",
      current: "Now",
      target: "Target",
      status: "Status",
      grp_temps: "Temperatures",
      grp_boost: "Boost",
      grp_plan: "Schedule",
      grp_door: "Door / window",
      grp_protect: "Protection",
      grp_limits: "Limits",
      grp_night: "Night setback",
      lower: "Lower target",
      raise: "Raise target",
      dismiss: "Dismiss",
      no_rooms: "No rooms yet. Add them on the integration's settings page.",
      no_entities: "No Heat Pilot entities found.",
    },
  };

  // Switches per detail group (a group is hidden when none of them exists).
  var PLAN_SWITCHES = ["skip_setback", "plan_paused", "night_setback"];
  var PROTECT_SWITCHES = ["absence_shutdown", "max_limit"];

  // Everything that belongs to a door/window sensor; shown only for rooms that
  // have such a sensor (they own the "opening" entity).
  var DOOR_SWITCHES = [
    "door_warning",
    "door_warning_setback_only",
    "door_warning_heating_only",
    "opening_shutdown",
  ];

  // Room status shown as an icon (the text is the tooltip and shown in the details).
  var STATUS_ICONS = {
    outside_period: "mdi:radiator-off",
    absence_mode: "mdi:home-export-outline",
    opening: "mdi:door-open",
    room_absent: "mdi:account-off-outline",
    comfort: "mdi:white-balance-sunny",
    setback: "mdi:weather-night",
    comfort_skipped: "mdi:weather-night-off",
    boost: "mdi:fire",
    plan_paused: "mdi:calendar-remove-outline",
    night_setback: "mdi:weather-night",
  };

  // Tile colour per status: heat (warm), night (cool), off (grey), warn (red).
  var STATUS_TONE = {
    comfort: "heat",
    boost: "heat",
    setback: "night",
    night_setback: "night",
    plan_paused: "night",
    comfort_skipped: "night",
    outside_period: "off",
    absence_mode: "off",
    room_absent: "off",
    opening: "warn",
  };

  var ORDER_KEY = "heat_pilot_card_order";
  var LONG_PRESS_MS = 350; // touch: hold this long before a drag starts
  var MOVE_THRESHOLD = 6; // px: mouse drag start / touch long-press cancel
  // Controls inside a tile that must keep working and never start a drag.
  var NO_DRAG = ".sbtn,.detail,input,select,ha-switch,ha-slider,ha-selector,button.link,button.primary";

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

  function fmtNum(value) {
    var n = num(value);
    return n === null ? "–" : n.toFixed(1).replace(".", ",");
  }

  function fmtTemp(value) {
    var n = num(value);
    return n === null ? "–" : fmtNum(n) + " °C";
  }

  function fmtMinutes(value) {
    var n = num(value);
    return n === null ? "–" : Math.round(n) + " min";
  }

  function icon(name) {
    return '<ha-icon icon="' + esc(name) + '"></ha-icon>';
  }

  var STYLE =
    ":host{display:block}" +
    "ha-card{padding:16px;--hp-heat:var(--state-climate-heat-color,#ef6c00);" +
    "--hp-night:var(--state-climate-cool-color,#3f7fd9);--hp-off:var(--disabled-text-color,#9e9e9e);" +
    "--hp-warn:var(--error-color,#e53935);--hp-radius:14px}" +
    "button{font:inherit;color:inherit}" +
    "h2{margin:0;font-size:1.3em;font-weight:500;line-height:1.2}" +
    "h3{margin:0;font-size:1em;font-weight:500}" +
    ".bar{display:flex;align-items:center;justify-content:space-between;gap:8px 12px;flex-wrap:wrap;margin-bottom:12px}" +
    ".chips{display:flex;gap:6px;flex-wrap:wrap}" +
    ".chip{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:12px;font-size:.85em;" +
    "background:var(--secondary-background-color);color:var(--primary-text-color);--mdc-icon-size:16px}" +
    ".chip.on{background:var(--primary-color);color:var(--text-primary-color,#fff)}" +
    ".chip.warn{background:var(--hp-warn);color:#fff}" +
    ".sub{color:var(--secondary-text-color);font-size:.9em}" +
    // errors and alerts
    ".error{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 12px;padding:8px 12px;" +
    "border-radius:var(--hp-radius);background:var(--hp-warn);color:#fff}" +
    ".error button{background:none;border:1px solid #fff;border-radius:12px;color:#fff;padding:2px 10px;cursor:pointer}" +
    ".alerts{border:1px solid var(--hp-warn);border-left-width:5px;border-radius:var(--hp-radius);padding:8px 12px;margin:0 0 12px}" +
    ".alerts h3{color:var(--hp-warn);display:flex;align-items:center;gap:6px;--mdc-icon-size:20px}" +
    ".alert{padding:8px 0;border-top:1px solid var(--divider-color)}" +
    ".alert:first-of-type{border-top:none}" +
    ".alert b{display:block}" +
    // general settings
    ".gbtn{width:100%;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:8px;" +
    "min-height:48px;padding:0 12px;margin-bottom:12px;background:var(--secondary-background-color);border:none;" +
    "border-radius:var(--hp-radius);cursor:pointer;text-align:left;--mdc-icon-size:22px}" +
    ".gbtn .t{display:flex;align-items:center;gap:10px}" +
    ".chev{display:inline-flex;transition:transform .15s;color:var(--secondary-text-color)}" +
    "[aria-expanded=true] .chev{transform:rotate(180deg)}" +
    ".panel{margin:-4px 0 12px;padding:4px 12px 8px;border:1px solid var(--divider-color);border-radius:var(--hp-radius)}" +
    ".groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:0 28px}" +
    ".group{padding-bottom:6px}" +
    ".gtitle{margin:12px 0 2px;font-size:.78em;font-weight:500;letter-spacing:.06em;text-transform:uppercase;" +
    "color:var(--secondary-text-color)}" +
    // rows and controls
    ".row{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:44px;flex-wrap:wrap}" +
    ".stepper{display:flex;align-items:center;gap:6px}" +
    ".stepper .v{min-width:70px;text-align:center;font-variant-numeric:tabular-nums}" +
    ".sbtn{width:44px;height:44px;flex:none;display:inline-flex;align-items:center;justify-content:center;" +
    "border-radius:50%;border:1px solid var(--divider-color);background:var(--card-background-color);" +
    "color:var(--primary-text-color);font-size:1.4em;line-height:1;cursor:pointer;padding:0}" +
    ".sbtn:active{background:var(--secondary-background-color)}" +
    "button.link{min-height:36px;background:none;border:1px solid var(--primary-color);color:var(--primary-color);" +
    "border-radius:18px;padding:4px 14px;cursor:pointer}" +
    "button.primary{min-height:36px;background:var(--primary-color);color:var(--text-primary-color,#fff);border:none;" +
    "border-radius:18px;padding:4px 16px;cursor:pointer}" +
    ".editor{padding:8px 0;display:grid;grid-template-columns:1fr 1fr;gap:8px}" +
    ".editor label{display:flex;flex-direction:column;font-size:.85em;gap:2px}" +
    ".editor input,.editor select{font:inherit;padding:8px;border:1px solid var(--divider-color);" +
    "border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color)}" +
    ".actions{display:flex;gap:8px;justify-content:flex-end;margin:6px 0}" +
    ".slider{display:flex;align-items:center;gap:10px;flex:1;min-width:180px;justify-content:flex-end}" +
    ".slider ha-slider,.slider input{flex:1;min-width:120px}" +
    ".slider .v{min-width:64px;text-align:right;font-variant-numeric:tabular-nums}" +
    ".empty{padding:16px 0;color:var(--secondary-text-color)}" +
    // room tiles
    ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}" +
    ".tile{--accent:var(--hp-off);box-sizing:border-box;display:flex;flex-direction:column;min-width:0;" +
    "border:1px solid var(--divider-color);border-top:4px solid var(--accent);border-radius:var(--hp-radius);" +
    "background:var(--card-background-color);overflow:hidden}" +
    ".tile.tone-heat{--accent:var(--hp-heat)}" +
    ".tile.tone-night{--accent:var(--hp-night)}" +
    ".tile.tone-warn{--accent:var(--hp-warn)}" +
    ".tile.tone-idle{--accent:var(--primary-color)}" +
    ".tile.open{grid-column:1/-1}" +
    ".tile{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}" +
    ".tile.dragging{position:relative;z-index:10;transition:none;opacity:.92;cursor:grabbing;" +
    "box-shadow:0 8px 24px rgba(0,0,0,.35);pointer-events:none}" +
    ".thead{display:flex;flex-direction:column;align-items:stretch;gap:2px;width:100%;box-sizing:border-box;" +
    "padding:10px 12px 6px;background:none;border:none;text-align:left;cursor:pointer}" +
    ".trow{display:flex;align-items:center;justify-content:space-between;gap:6px}" +
    ".tname{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".ticons{display:inline-flex;gap:4px;flex:none;--mdc-icon-size:20px;color:var(--accent)}" +
    ".ticons .warn{color:var(--hp-warn)}" +
    ".tcur{font-size:1.9em;font-weight:300;line-height:1.15;font-variant-numeric:tabular-nums}" +
    ".tcur small{font-size:.45em;margin-left:2px;color:var(--secondary-text-color)}" +
    ".tcur.text{font-size:1.1em;font-weight:400;padding:6px 0;display:flex;align-items:center;gap:6px;--mdc-icon-size:22px}" +
    ".tset{color:var(--secondary-text-color);font-size:.85em}" +
    ".tctl{display:flex;justify-content:space-between;padding:4px 12px 10px}" +
    ".detail{padding:0 12px 10px;border-top:1px solid var(--divider-color)}" +
    ".info{display:flex;gap:4px 16px;flex-wrap:wrap;padding:10px 0 0;color:var(--secondary-text-color);font-size:.9em}" +
    ".info span{display:inline-flex;align-items:center;gap:4px;--mdc-icon-size:18px}";

  class HeatPilotCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._config = {};
      this._sig = "";
      this._periodOpen = false;
      this._periodDraft = null;
      this._globalOpen = false;
      this._room = null; // device id of the one open room tile
      this._error = "";
      this._errorTimer = null;
      this._order = null; // saved room order (device ids)
      this._orderLoaded = false;
      this._drag = null;
      this._noClickUntil = 0;
      this._pendingRender = false;
      this._onDragMove = this._dragMove.bind(this);
      this._onDragEnd = this._dragEnd.bind(this, false);
      this._onDragCancel = this._dragEnd.bind(this, true);
      this._wireDrag();
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
      return 8;
    }

    set hass(hass) {
      this._hass = hass;
      if (!this._orderLoaded) {
        this._orderLoaded = true;
        this._loadOrder();
      }
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

    // ------------------------------------------------- tile order, drag & drop

    _loadOrder() {
      var self = this;
      try {
        var raw = window.localStorage.getItem(ORDER_KEY);
        var list = raw ? JSON.parse(raw) : null;
        if (Array.isArray(list)) {
          this._order = list;
        }
      } catch (e) {
        /* storage not available */
      }
      if (this._hass && typeof this._hass.callWS === "function") {
        this._hass.callWS({ type: "frontend/get_user_data", key: ORDER_KEY }).then(
          function (res) {
            var value = res && res.value;
            if (Array.isArray(value)) {
              self._order = value;
              self._render();
            }
          },
          function () {
            /* keep the local order */
          }
        );
      }
    }

    _saveOrder(ids) {
      this._order = ids;
      try {
        window.localStorage.setItem(ORDER_KEY, JSON.stringify(ids));
      } catch (e) {
        /* storage not available */
      }
      if (this._hass && typeof this._hass.callWS === "function") {
        this._hass.callWS({ type: "frontend/set_user_data", key: ORDER_KEY, value: ids }).then(
          function () {},
          function () {
            /* the local copy still holds the order */
          }
        );
      }
    }

    /** Room ids: saved order first, rooms without a saved position by name. */
    _sortedRoomIds(rooms) {
      var order = this._order || [];
      return Object.keys(rooms).sort(function (a, b) {
        var ia = order.indexOf(a);
        var ib = order.indexOf(b);
        if (ia === -1 && ib === -1) {
          return String(rooms[a].name).localeCompare(String(rooms[b].name));
        }
        if (ia === -1) {
          return 1;
        }
        if (ib === -1) {
          return -1;
        }
        return ia - ib;
      });
    }

    _wireDrag() {
      var self = this;
      var root = this.shadowRoot;
      root.addEventListener("pointerdown", function (ev) {
        self._dragStart(ev);
      });
      // A drag must not end in a click on the tile below the pointer.
      root.addEventListener(
        "click",
        function (ev) {
          if (Date.now() < self._noClickUntil) {
            ev.stopPropagation();
            ev.preventDefault();
          }
        },
        true
      );
      root.addEventListener("contextmenu", function (ev) {
        if (self._drag) {
          ev.preventDefault();
        }
      });
      // Once a touch drag runs, the page must not scroll with it.
      root.addEventListener(
        "touchmove",
        function (ev) {
          if (self._drag && self._drag.active && ev.cancelable) {
            ev.preventDefault();
          }
        },
        { passive: false }
      );
    }

    _dragStart(ev) {
      if (this._drag || !ev.target || !ev.target.closest) {
        return;
      }
      if (ev.pointerType === "mouse" && ev.button !== 0) {
        return;
      }
      var tile = ev.target.closest(".tile");
      if (!tile || ev.target.closest(NO_DRAG)) {
        return;
      }
      if (this.shadowRoot.querySelectorAll(".tile").length < 2) {
        return;
      }
      var self = this;
      this._drag = {
        id: tile.getAttribute("data-id"),
        tile: tile,
        pointerId: ev.pointerId,
        type: ev.pointerType,
        startX: ev.clientX,
        startY: ev.clientY,
        x: ev.clientX,
        y: ev.clientY,
        active: false,
        timer: null,
      };
      if (ev.pointerType !== "mouse") {
        this._drag.timer = setTimeout(function () {
          self._dragBegin();
        }, LONG_PRESS_MS);
      }
      window.addEventListener("pointermove", this._onDragMove);
      window.addEventListener("pointerup", this._onDragEnd);
      window.addEventListener("pointercancel", this._onDragCancel);
    }

    _dragMove(ev) {
      var d = this._drag;
      if (!d || ev.pointerId !== d.pointerId) {
        return;
      }
      d.x = ev.clientX;
      d.y = ev.clientY;
      if (!d.active) {
        var dist = Math.sqrt(Math.pow(d.x - d.startX, 2) + Math.pow(d.y - d.startY, 2));
        if (dist > MOVE_THRESHOLD) {
          if (d.type === "mouse") {
            this._dragBegin();
          } else {
            this._dragEnd(true, ev); // the finger moves: the user scrolls
          }
        }
        return;
      }
      if (ev.cancelable) {
        ev.preventDefault();
      }
      this._dragUpdate();
    }

    _dragBegin() {
      var d = this._drag;
      if (!d || d.active) {
        return;
      }
      if (d.timer) {
        clearTimeout(d.timer);
        d.timer = null;
      }
      // Collapse an open tile first: all tiles then have the same size.
      if (this._room) {
        this._room = null;
        this._render();
        d.tile = this.shadowRoot.querySelector('.tile[data-id="' + d.id + '"]');
        if (!d.tile) {
          this._dragEnd(true);
          return;
        }
      }
      d.active = true;
      var rect = d.tile.getBoundingClientRect();
      d.grabX = d.x - rect.left;
      d.grabY = d.y - rect.top;
      d.tile.classList.add("dragging");
      if (navigator.vibrate) {
        try {
          navigator.vibrate(15);
        } catch (e) {
          /* not supported */
        }
      }
      this._dragUpdate();
    }

    /** Swap into the slot under the pointer and let the tile follow the pointer. */
    _dragUpdate() {
      var d = this._drag;
      var tile = d.tile;
      var grid = tile.parentNode;
      tile.style.transform = "";
      var tiles = Array.prototype.slice.call(grid.querySelectorAll(".tile"));
      var target = null;
      for (var i = 0; i < tiles.length; i++) {
        if (tiles[i] === tile) {
          continue;
        }
        var r = tiles[i].getBoundingClientRect();
        if (d.x >= r.left && d.x <= r.right && d.y >= r.top && d.y <= r.bottom) {
          target = tiles[i];
          break;
        }
      }
      if (target) {
        if (tiles.indexOf(tile) < tiles.indexOf(target)) {
          grid.insertBefore(tile, target.nextSibling);
        } else {
          grid.insertBefore(tile, target);
        }
      }
      var own = tile.getBoundingClientRect();
      tile.style.transform =
        "translate(" + Math.round(d.x - d.grabX - own.left) + "px," + Math.round(d.y - d.grabY - own.top) + "px)";
    }

    _dragEnd(cancelled) {
      var d = this._drag;
      if (!d) {
        return;
      }
      this._drag = null;
      if (d.timer) {
        clearTimeout(d.timer);
      }
      window.removeEventListener("pointermove", this._onDragMove);
      window.removeEventListener("pointerup", this._onDragEnd);
      window.removeEventListener("pointercancel", this._onDragCancel);
      if (!d.active) {
        return;
      }
      this._noClickUntil = Date.now() + 400;
      d.tile.style.transform = "";
      d.tile.classList.remove("dragging");
      if (!cancelled) {
        var ids = Array.prototype.map.call(this.shadowRoot.querySelectorAll(".tile"), function (t) {
          return t.getAttribute("data-id");
        });
        this._saveOrder(ids);
      }
      this._pendingRender = false;
      this._render();
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
            id: id,
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

    _fmtClock(value) {
      var d = new Date(value);
      if (isNaN(d.getTime())) {
        return String(value);
      }
      try {
        return d.toLocaleTimeString(this._hass.language, { hour: "2-digit", minute: "2-digit" });
      } catch (e) {
        return String(value);
      }
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

    // ------------------------------------------------------ render pieces

    _stepper(entityId, label, format) {
      var st = this._state(entityId);
      if (!st) {
        return "";
      }
      var fmt = format || fmtTemp;
      var unavailable = st.state === "unavailable" || st.state === "unknown";
      return (
        '<div class="row"><span>' + esc(label) + "</span>" +
        '<span class="stepper">' +
        '<button class="sbtn" data-act="step" data-ent="' + esc(entityId) + '" data-dir="-1" aria-label="−">−</button>' +
        '<span class="v">' + (unavailable ? "–" : fmt(st.state)) + "</span>" +
        '<button class="sbtn" data-act="step" data-ent="' + esc(entityId) + '" data-dir="1" aria-label="+">+</button>' +
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

    _group(title, inner) {
      return inner ? '<div class="group"><div class="gtitle">' + esc(title) + "</div>" + inner + "</div>" : "";
    }

    /** Slider for the room's setpoint (HA's slider, a native range as fallback). */
    _slider(entityId, label) {
      var st = this._state(entityId);
      if (!st) {
        return "";
      }
      var min = num(st.attributes.min) !== null ? num(st.attributes.min) : 5;
      var max = num(st.attributes.max) !== null ? num(st.attributes.max) : 30;
      var step = num(st.attributes.step) || 0.5;
      var value = num(st.state);
      var common =
        ' min="' + min + '" max="' + max + '" step="' + step + '" value="' + (value === null ? min : value) +
        '" data-act="slider" data-ent="' + esc(entityId) + '"' +
        (st.state === "unavailable" ? " disabled" : "");
      var control = customElements.get("ha-slider")
        ? "<ha-slider labeled" + common + "></ha-slider>"
        : '<input type="range"' + common + ">";
      return (
        '<div class="row"><span>' + esc(label) + '</span><span class="slider">' + control +
        '<span class="v" data-slider-label>' + (value === null ? "–" : fmtTemp(value)) + "</span></span></div>"
      );
    }

    /** One global night window: start and end, each opens its time dialog. */
    _nightRow(g, kind) {
      var start = this._state(g["night_" + kind + "_start"]);
      var end = this._state(g["night_" + kind + "_end"]);
      if (!start || !end) {
        return "";
      }
      var link = function (st, id) {
        return (
          '<button class="link" data-act="plan" data-ent="' + esc(id) + '">' +
          esc(String(st.state).slice(0, 5)) + "</button>"
        );
      };
      return (
        '<div class="row"><span>' + esc(this._t("night_" + kind)) + "</span><span>" +
        link(start, g["night_" + kind + "_start"]) + " " + esc(this._t("night_to")) + " " +
        link(end, g["night_" + kind + "_end"]) + "</span></div>"
      );
    }

    /** Alerts that were sent to the phones and whose cause still exists. */
    _renderAlerts(entityId) {
      var st = this._state(entityId);
      var alerts = (st && st.attributes.alerts) || [];
      if (!alerts.length) {
        return "";
      }
      var self = this;
      var html = '<div class="alerts"><h3>' + icon("mdi:alert-circle-outline") +
        esc(this._t("alerts")) + " (" + alerts.length + ")</h3>";
      alerts.forEach(function (a) {
        html +=
          '<div class="alert"><b>' + esc(a.title) + "</b>" + esc(a.message) +
          ' <span class="sub">(' + esc(self._t("since")) + " " + esc(self._fmtClock(a.since)) + ")</span>";
        if (a.kind === "unavailable") {
          html +=
            '<div class="actions"><button class="link" data-act="pair">' +
            esc(self._pairing ? self._t("pair_started") : self._t("pair_start")) + "</button></div>";
        }
        html += "</div>";
      });
      return html + "</div>";
    }

    _renderHeader(g) {
      var chips = "";
      var period = this._state(g.heating_period);
      if (period) {
        var active = period.state === "active";
        chips +=
          '<span class="chip ' + (active ? "on" : "") + '">' + icon(active ? "mdi:radiator" : "mdi:radiator-off") +
          esc(this._t("period") + " " + this._t(active ? "period_active" : "period_inactive")) + "</span>";
      }
      var absence = this._state(g.absence_mode);
      if (absence && absence.state === "on") {
        chips += '<span class="chip warn">' + icon("mdi:home-export-outline") + esc(this._t("absence_chip")) + "</span>";
      }
      return '<div class="bar"><h2>' + esc(this._config.title || this._t("title")) +
        '</h2><div class="chips">' + chips + "</div></div>";
    }

    _renderGlobalSection(g) {
      var open = this._globalOpen;
      var html =
        '<button class="gbtn" data-act="global" aria-expanded="' + (open ? "true" : "false") +
        '" title="' + esc(this._t(open ? "collapse" : "expand")) + '">' +
        '<span class="t">' + icon("mdi:cog-outline") + "<h3>" + esc(this._t("general")) + "</h3></span>" +
        '<span class="chev">' + icon("mdi:chevron-down") + "</span></button>";
      if (!open) {
        return html;
      }
      return html + '<div class="panel"><div class="groups">' + this._renderGlobal(g) + "</div></div>";
    }

    _renderGlobal(g) {
      var self = this;
      var periodHtml = "";
      var period = this._state(g.heating_period);
      if (period) {
        var a = period.attributes;
        var range = a.start_day + "." + a.start_month + ". – " + a.end_day + "." + a.end_month + ".";
        var active = period.state === "active";
        periodHtml +=
          '<div class="row"><span><span class="chip ' + (active ? "on" : "") + '">' +
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
          var field = function (key, max) {
            return (
              "<label>" + esc(self._t(key)) +
              '<input type="number" inputmode="numeric" min="1" max="' + max + '" data-field="' + key +
              '" value="' + esc(d[key]) + '"></label>'
            );
          };
          periodHtml +=
            '<div class="editor">' +
            field("start_day", 31) + field("start_month", 12) +
            field("end_day", 31) + field("end_month", 12) +
            '</div><div class="actions">' +
            '<button class="link" data-act="period-cancel">' + esc(this._t("period_cancel")) + "</button>" +
            '<button class="primary" data-act="period-save">' + esc(this._t("period_save")) + "</button></div>";
        }
      }
      periodHtml += this._toggle(g.period_override, this._t("period_override"));
      periodHtml += this._toggle(g.period_paused, this._t("period_paused"));

      var absenceHtml = this._toggle(g.absence_mode, this._t("absence"));
      var absence = this._state(g.absence_mode);
      var ret = absence && absence.state === "on" ? this._state(g.return_at) : null;
      if (ret) {
        var value = ret.state && ret.state !== "unknown" && ret.state !== "unavailable"
          ? ret.state.replace(" ", "T").slice(0, 16) : "";
        absenceHtml +=
          '<div class="row"><span>' + esc(this._t("return_at")) + "</span>" +
          '<span data-slot="return" data-ent="' + esc(g.return_at) + '" data-value="' + esc(value) +
          '"></span></div>';
      }

      var limits = this._stepper(g.frost_temp, this._t("frost_temp")) +
        this._stepper(g.max_temp, this._t("max_temp"));
      var night = this._nightRow(g, "weekday") + this._nightRow(g, "weekend");

      return (
        this._group(this._t("period"), periodHtml) +
        this._group(this._t("absence"), absenceHtml) +
        this._group(this._t("grp_limits"), limits) +
        this._group(this._t("grp_night"), night)
      );
    }

    /** Mean of the numeric values, or null. */
    _mean(values) {
      var list = values.filter(function (v) {
        return v !== null;
      });
      if (!list.length) {
        return null;
      }
      return (
        list.reduce(function (a, b) {
          return a + b;
        }, 0) / list.length
      );
    }

    _renderRoom(room, periodActive) {
      var e = room.ents;
      var hass = this._hass;
      var self = this;
      var status = this._state(e.status);
      var attrs = status ? status.attributes : {};
      var thermostats = (attrs.thermostats || [])
        .map(function (id) {
          return self._state(id);
        })
        .filter(Boolean);
      var opening = this._state(e.opening);
      var isOpen = !!opening && opening.state === "on";
      var open = this._room === room.id;

      var tone = isOpen ? "warn" : (status && STATUS_TONE[status.state]) || (status ? "idle" : "off");
      var current = this._mean(
        thermostats.map(function (t) {
          return num(t.attributes.current_temperature);
        })
      );
      var setpointSt = this._state(e.setpoint);
      var target = setpointSt && num(setpointSt.state) !== null
        ? num(setpointSt.state)
        : this._mean(
            thermostats.map(function (t) {
              return num(t.attributes.temperature);
            })
          );

      // Header (tap = open/close the details).
      var icons = "";
      if (isOpen) {
        icons += '<span class="warn" title="' + esc(this._t("open")) + '">' + icon("mdi:door-open") + "</span>";
      }
      if (status) {
        icons += '<span title="' + esc(this._display(status)) + '">' +
          icon(STATUS_ICONS[status.state] || "mdi:information-outline") + "</span>";
      }
      var main;
      var sub = "";
      if (thermostats.length) {
        main = '<span class="tcur">' + fmtNum(current) + "<small>°C</small></span>";
        sub = '<span class="tset">' + esc(this._t("target")) + " " + fmtTemp(target) + "</span>";
      } else if (opening) {
        main = '<span class="tcur text">' + icon(isOpen ? "mdi:door-open" : "mdi:door-closed") +
          esc(this._t(isOpen ? "open" : "closed")) + "</span>";
      } else {
        main = '<span class="tcur">–</span>';
      }
      var html =
        '<div class="tile tone-' + tone + (open ? " open" : "") + '" data-id="' + esc(room.id) + '">' +
        '<button class="thead" data-act="room" data-key="' + esc(room.id) + '" aria-expanded="' +
        (open ? "true" : "false") + '" title="' + esc(this._t(open ? "collapse" : "expand")) + '">' +
        '<span class="trow"><span class="tname">' + esc(room.name) + '</span><span class="ticons">' + icons +
        "</span></span>" + main + sub + "</button>";

      // Quick +/- on the tile.
      if (setpointSt && thermostats.length) {
        html +=
          '<div class="tctl">' +
          '<button class="sbtn" data-act="step" data-ent="' + esc(e.setpoint) + '" data-dir="-1" aria-label="' +
          esc(this._t("lower")) + '">−</button>' +
          '<button class="sbtn" data-act="step" data-ent="' + esc(e.setpoint) + '" data-dir="1" aria-label="' +
          esc(this._t("raise")) + '">+</button></div>';
      }

      if (!open) {
        return html + "</div>";
      }

      // Details across the full width.
      html += '<div class="detail"><div class="info">';
      if (status) {
        html += "<span>" + icon(STATUS_ICONS[status.state] || "mdi:information-outline") +
          esc(this._display(status)) + "</span>";
      }
      if (attrs.next_change) {
        html += "<span>" + esc(this._t("next_change")) + ": " + esc(this._fmtTime(attrs.next_change)) + "</span>";
      }
      html += '</div><div class="groups">';

      var temps = "";
      if (thermostats.length) {
        temps += this._slider(e.setpoint, this._t("setpoint"));
        temps += this._stepper(e.comfort, this._t("comfort"));
        temps += this._stepper(e.setback, this._t("setback"));
      }
      html += this._group(this._t("grp_temps"), temps);

      var boost = periodActive ? this._state(e.boost) : null;
      if (boost) {
        var until = boost.state === "on" && boost.attributes.ends_at
          ? this._fmtClock(boost.attributes.ends_at) : "";
        html += this._group(
          this._t("grp_boost"),
          this._toggle(e.boost, this._t("boost") + (until ? " (" + this._t("boost_until") + " " + until + ")" : "")) +
            this._stepper(e.boost_minutes, this._t("boost_minutes"), fmtMinutes)
        );
      }

      var plan = "";
      PLAN_SWITCHES.forEach(function (key) {
        if (e[key]) {
          plan += self._toggle(e[key], self._t(key));
        }
      });
      var nextNight = this._state(e.next_night_setback);
      if (nextNight && nextNight.state !== "unavailable" && nextNight.state !== "unknown") {
        var shift = num(nextNight.attributes.shift_hours) || 0;
        plan +=
          '<div class="row"><span>' + esc(this._t("night_next")) + ": " +
          esc(this._fmtTime(nextNight.state)) + (shift ? " (+" + shift + " h)" : "") + "</span>" +
          (e.night_setback_later
            ? '<button class="link" data-act="press" data-ent="' + esc(e.night_setback_later) + '">' +
              esc(this._t("night_later")) + "</button>"
            : "") +
          "</div>";
      }
      if (attrs.schedule && hass.states[attrs.schedule]) {
        plan +=
          '<div class="actions"><button class="link" data-act="plan" data-ent="' +
          esc(attrs.schedule) + '" data-view="settings">' + esc(this._t("edit_plan")) + "</button></div>";
      }
      html += this._group(this._t("grp_plan"), plan);

      var door = "";
      if (e.opening) {
        DOOR_SWITCHES.forEach(function (key) {
          if (e[key]) {
            door += self._toggle(e[key], self._t(key));
          }
        });
      }
      html += this._group(this._t("grp_door"), door);

      var protect = "";
      PROTECT_SWITCHES.forEach(function (key) {
        if (e[key]) {
          protect += self._toggle(e[key], self._t(key));
        }
      });
      html += this._group(this._t("grp_protect"), protect);

      return html + "</div></div></div>";
    }

    _render() {
      var root = this.shadowRoot;
      if (!root) {
        return;
      }
      if (this._drag && this._drag.active) {
        this._pendingRender = true; // re-rendering would destroy the tile being dragged
        return;
      }
      if (!this._hass) {
        root.innerHTML = "<style>" + STYLE + "</style><ha-card></ha-card>";
        return;
      }
      var data = this._collect();
      var html = "<style>" + STYLE + "</style><ha-card>";
      if (!data.found) {
        html += '<div class="bar"><h2>' + esc(this._config.title || this._t("title")) + "</h2></div>" +
          '<div class="empty">' + esc(this._t("no_entities")) + "</div>";
      } else {
        html += this._renderHeader(data.global);
        if (this._error) {
          html += '<div class="error" role="alert"><span>' + esc(this._error) + "</span>" +
            '<button data-act="dismiss">' + esc(this._t("dismiss")) + "</button></div>";
        }
        html += this._renderAlerts(data.global.active_alerts);
        html += this._renderGlobalSection(data.global);
        var periodState = this._state(data.global.heating_period);
        var periodActive = !!periodState && periodState.state === "active";
        var ids = this._sortedRoomIds(data.rooms);
        if (!ids.length) {
          html += '<div class="empty">' + esc(this._t("no_rooms")) + "</div>";
        } else {
          html += '<div class="grid">';
          for (var i = 0; i < ids.length; i++) {
            html += this._renderRoom(data.rooms[ids[i]], periodActive);
          }
          html += "</div>";
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
        } else if (act === "slider") {
          var label = node.parentNode.querySelector("[data-slider-label]");
          node.addEventListener("input", function () {
            if (label) {
              label.textContent = fmtTemp(node.value);
            }
          });
          node.addEventListener("change", function () {
            self._call("number", "set_value", {
              entity_id: node.getAttribute("data-ent"),
              value: num(node.value),
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
      } else if (act === "press") {
        this._call("button", "press", { entity_id: ent });
      } else if (act === "pair") {
        var self = this;
        this._call("heat_pilot", "pair_door_sensor", {}).then(function (ok) {
          if (!ok) {
            return;
          }
          self._pairing = true;
          self._render();
          setTimeout(function () {
            self._pairing = false;
            self._render();
          }, 120000);
        });
      } else if (act === "room") {
        var key = node.getAttribute("data-key");
        this._room = this._room === key ? null : key;
        this._render();
      } else if (act === "global") {
        this._globalOpen = !this._globalOpen;
        this._render();
      } else if (act === "dismiss") {
        this._clearError();
      } else if (act === "plan") {
        // For the schedule helper the dialog opens on its settings tab, which
        // holds the schedule editor (instead of the plain detail view).
        var view = node.getAttribute("data-view");
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: view ? { entityId: ent, view: view } : { entityId: ent },
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
        var pick = function (field) {
          var n = parseInt(d[field] !== undefined ? d[field] : a[field], 10);
          return isNaN(n) ? a[field] : n;
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

    _clearError() {
      if (this._errorTimer) {
        clearTimeout(this._errorTimer);
        this._errorTimer = null;
      }
      this._error = "";
      this._render();
    }

    /** Show a service error inside the card (window.alert blocks the companion app). */
    _showError(err) {
      var self = this;
      this._error = err && err.message ? err.message : String(err);
      if (this._errorTimer) {
        clearTimeout(this._errorTimer);
      }
      this._errorTimer = setTimeout(function () {
        self._errorTimer = null;
        self._error = "";
        self._render();
      }, 10000);
      this._render();
    }

    /** Calls a service; resolves to true on success, false after showing the error. */
    _call(domain, service, data) {
      var self = this;
      return this._hass.callService(domain, service, data).then(
        function () {
          return true;
        },
        function (err) {
          self._showError(err);
          return false;
        }
      );
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
    description: "Raumweise Heizungssteuerung: Raumkacheln (per Drag & Drop sortierbar) mit Temperaturen, Status, Schaltern und Zeitplan.",
  });
})();
