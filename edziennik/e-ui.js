/* e-ui.js — budowanie DOM, ikony (inline SVG, kreska jak w prototypie), małe klocki interfejsu. */
(function () {
  "use strict";
  var E = window.E;

  /* h("div", {class:…, text:…, tap:fn}, child, [children]) */
  function h(tag, attrs) {
    var el = document.createElement(tag), i, k;
    if (attrs) for (k in attrs) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "text") { el.textContent = v; continue; }
      if (k === "tap") { el.addEventListener("click", v); continue; }
      if (k === "html") { el.innerHTML = v; continue; }
      el.setAttribute(k, v === true ? "" : v);
    }
    for (i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) return c.forEach(function (x) { add(el, x); });
    el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  E.h = h;
  E.set = function (el, text) { if (el.textContent !== String(text)) el.textContent = String(text); };
  E.setAttr = function (el, k, v) {
    if (v == null || v === false) el.removeAttribute(k);
    else el.setAttribute(k, v === true ? "" : v);
  };

  /* ---------- ikony ---------- */
  var IC = {
    today: '<path d="M4 7h16M4 12h16M4 17h10"/>',
    star: '<path d="M12 4l2.4 5 5.6.8-4 3.9 1 5.5-5-2.7-5 2.7 1-5.5-4-3.9 5.6-.8z"/>',
    tasks: '<path d="M6 4h12v16H6z"/><path d="M9 9h6M9 13h6M9 17h3"/>',
    mail: '<path d="M3 6h18v12H3z"/><path d="M3 7l9 6 9-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',
    alarm: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M5.5 4.5L3 7M18.5 4.5L21 7"/>',
    cog: '<circle cx="12" cy="12" r="3.2"/><path d="M12 3v2.4M12 18.6V21M21 12h-2.4M5.4 12H3M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3L5.6 5.6"/>',
    sync: '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v4h-4"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.5 1.5M17.6 17.6l1.5 1.5M19.1 4.9l-1.5 1.5M6.4 17.6l-1.5 1.5"/>',
    auto: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor" stroke="none"/>',
    eye: '<path d="M2 12s3.8-6.5 10-6.5S22 12 22 12s-3.8 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.8"/>',
    eyeOff: '<path d="M2 12s3.8-6.5 10-6.5c2 0 3.7.7 5.1 1.6M22 12s-1.4 2.4-4 4.3c-1.6 1.2-3.6 2.2-6 2.2-1.3 0-2.5-.3-3.6-.7"/><path d="M4 3l16 18"/><path d="M9.6 9.8a2.8 2.8 0 0 0 3.8 4"/>',
    warn: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 8v.01M12 11v5"/>',
    dot: '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    check: '<path d="M5 12l5 5L20 7"/>',
    swap: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
    off: '<circle cx="12" cy="12" r="9"/><path d="M8 16L16 8"/>',
    note: '<path d="M5 5h14v10l-4 4H5z"/><path d="M8 9h8M8 13h5"/>',
    pin: '<path d="M12 21s7-6.6 7-11.4A7 7 0 0 0 5 9.6C5 14.4 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.4"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/>'
  };
  E.ICONS = IC;
  function mi(name) {
    return h("span", { class: "e-i", html: '<svg viewBox="0 0 24 24" aria-hidden="true">' + (IC[name] || "") + "</svg>" });
  }
  E.mi = mi;
  E.setMi = function (el, name) {
    el.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (IC[name] || "") + "</svg>";
  };

  /* ---------- klocki ---------- */
  E.card = function (title, right) {
    var body = h("div", { class: "e-list" });
    var card = h("div", { class: "e-card" },
      title ? h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: title }), right || null) : null,
      body);
    card._body = body;
    return card;
  };
  E.tag = function (text, tone) {
    return h("span", { class: "e-tag", "data-tone": tone || null, text: text });
  };
  E.row = function (title, sub, value, opts) {
    opts = opts || {};
    return h("div", { class: "e-row", "data-new": opts.fresh || null },
      opts.icon ? mi(opts.icon) : null,
      h("span", { class: "e-row__l" },
        h("span", { class: "e-row__t", text: title, "data-sec": opts.secret || null }),
        sub ? h("span", { class: "e-row__s", text: sub, "data-sec": opts.secret || null }) : null),
      value == null ? null : (typeof value === "string"
        ? h("span", { class: "e-row__v", text: value })
        : value));
  };
  E.empty = function (text) { return h("p", { class: "e-empty", text: text }); };
  E.banner = function (text, tone, icon) {
    return h("div", { class: "e-banner", "data-tone": tone || null },
      mi(icon || (tone === "alert" ? "warn" : "info")),
      h("span", { class: "e-banner__t", text: text }));
  };

  /* przełącznik (lokalny, zapis w ustawieniach urządzenia) */
  E.toggle = function (scope, o) {
    var btn = h("button", { class: "e-tg", role: "switch", "aria-label": o.label });
    btn.addEventListener("click", function () { o.set(!o.get()); });
    scope.bind(["@set"].concat(o.ids || []), function () {
      var on = !!o.get();
      E.setAttr(btn, "data-on", on);
      btn.setAttribute("aria-checked", on ? "true" : "false");
    });
    return h("div", { class: "e-tgrow" },
      h("span", { class: "e-tgrow__l" },
        h("b", { style: "font-weight:500", text: o.label }),
        o.note ? h("span", { class: "e-row__s", text: o.note }) : null),
      btn);
  };
  /* wiersz z wartością tylko do odczytu */
  E.infoRow = function (label, note, value) {
    return h("div", { class: "e-tgrow" },
      h("span", { class: "e-tgrow__l" },
        h("b", { style: "font-weight:500", text: label }),
        note ? h("span", { class: "e-row__s", text: note }) : null),
      typeof value === "string" ? E.tag(value) : value);
  };
  /* segmentowany wybór */
  E.seg = function (scope, o) {
    var opts = o.opts.map(function (x) {
      var b = h("button", { class: "e-seg__o", type: "button" },
        x.icon ? mi(x.icon) : null, h("span", { text: x.label }));
      b.addEventListener("click", function () { o.set(x.v); });
      b._v = x.v;
      return b;
    });
    var box = h("div", { class: "e-seg", role: "group", "aria-label": o.label }, opts);
    scope.bind(["@set"].concat(o.ids || []), function () {
      var v = o.get();
      opts.forEach(function (b) { b.setAttribute("aria-pressed", b._v === v ? "true" : "false"); });
    });
    return box;
  };
  /* +/- stepper */
  E.step = function (scope, o) {
    var out = h("span", { class: "e-step__v" });
    var minus = h("button", { class: "e-rb", type: "button", "aria-label": "Mniej" }, mi("minus"));
    var plus = h("button", { class: "e-rb", type: "button", "aria-label": "Więcej" }, mi("plus"));
    minus.addEventListener("click", function () { o.set(Math.max(o.min, o.get() - o.stepBy)); });
    plus.addEventListener("click", function () { o.set(Math.min(o.max, o.get() + o.stepBy)); });
    scope.bind(["@set"].concat(o.ids || []), function () {
      var v = o.get();
      E.set(out, o.text(v));
      minus.disabled = v <= o.min; plus.disabled = v >= o.max;
    });
    return h("div", { class: "e-step" }, minus, out, plus);
  };
  /* leniwe wczytanie (obietnica → treść) */
  E.lazy = function (scope, promise, render, placeholder) {
    var box = h("div", null, E.empty(placeholder || "Wczytywanie…"));
    promise.then(function (data) {
      if (scope.dead) return;
      box.textContent = "";
      add(box, render(data));
    }).catch(function () {
      if (scope.dead) return;
      box.textContent = "";
      box.appendChild(E.empty("Nie udało się pobrać danych z Home Assistanta."));
    });
    return box;
  };
})();
