/* e-core.js — połączenie z Home Assistantem, magazyn stanów, ustawienia per urządzenie, motyw.
   Wzorowane na www/perla/core.js: WebSocket /api/websocket, subscribe_entities, token z sesji HA
   (hassTokens) albo z localStorage, odnawianie przez /auth/token. Panel jest tylko-czytający:
   nie woła żadnej usługi HA. */
(function () {
  "use strict";
  var E = window.E = { states: {}, ready: false, live: false };

  /* ---------- encje ---------- */
  var P = "sensor.emilia_pudlo_";
  E.ENT = {
    dzis: P + "pierwsza_lekcja_dzis",
    jutro: P + "pierwsza_lekcja_jutro",
    nast: P + "pierwsza_lekcja_nastepnego_dnia_nauki",
    sprawdzian: P + "najblizszy_sprawdzian",
    spr7: P + "sprawdziany_w_7_dni",
    zmiany7: P + "zmiany_w_planie_7_dni",
    ocena: P + "ostatnia_ocena",
    oceny: P + "oceny",
    poczta: P + "nieprzeczytane_wiadomosci",
    uwagi: P + "uwagi",
    numerek: P + "szczesliwy_numerek",
    sync: P + "ostatnia_synchronizacja"
  };
  E.CAL = {
    plan: "calendar.emilia_pudlo_plan_lekcji",
    zadania: "calendar.emilia_pudlo_sprawdziany_i_zadania"
  };
  E.ALL = Object.keys(E.ENT).map(function (k) { return E.ENT[k]; })
    .concat(Object.keys(E.CAL).map(function (k) { return E.CAL[k]; }));

  /* ---------- ustawienia per urządzenie ---------- */
  var SKEY = "edz_set";
  var DEF = {
    theme: "auto",          // day | night | auto
    hideGrades: false,      // ukrycie ocen (ikona przekreślonego oka)
    wake: 85,               // minut przed pierwszą lekcją
    wakeFloor: "6:00",      // nie wcześniej niż
    wakeOn: true,
    grid: "dzis"            // sekcja startowa
  };
  var set = null;
  E.cfg = function () {
    if (set) return set;
    var s = {};
    try { s = JSON.parse(localStorage.getItem(SKEY) || "{}") || {}; } catch (e) { s = {}; }
    set = {};
    Object.keys(DEF).forEach(function (k) { set[k] = (k in s) ? s[k] : DEF[k]; });
    return set;
  };
  E.put = function (k, v) {
    var s = E.cfg(); s[k] = v;
    try { localStorage.setItem(SKEY, JSON.stringify(s)); } catch (e) {}
    E.mark("@set");
  };
  E.defaults = DEF;

  /* ---------- odświeżanie widoków ---------- */
  var binds = new Map(), dirty = new Set(), raf = 0;
  E.mark = function (id) { dirty.add(id); if (!raf) raf = requestAnimationFrame(flush); };
  function flush() {
    raf = 0;
    var fns = new Set();
    dirty.forEach(function (id) { var s = binds.get(id); if (s) s.forEach(function (f) { fns.add(f); }); });
    dirty.clear();
    fns.forEach(function (f) { try { f(); } catch (e) { console.error("[edz] bind", e); } });
  }
  function Scope() { this.off = []; }
  Scope.prototype.bind = function (ids, fn) {
    var off = this.off;
    [].concat(ids).forEach(function (id) {
      var s = binds.get(id); if (!s) binds.set(id, s = new Set());
      s.add(fn); off.push(function () { s.delete(fn); });
    });
    try { fn(); } catch (e) { console.error("[edz] bind init", e); }
    return this;
  };
  Scope.prototype.every = function (ms, fn) {
    var t = setInterval(fn, ms); this.off.push(function () { clearInterval(t); });
  };
  Scope.prototype.add = function (fn) { this.off.push(fn); };
  Scope.prototype.dispose = function () {
    this.off.forEach(function (f) { try { f(); } catch (e) {} }); this.off = [];
  };
  E.Scope = Scope;

  /* ---------- dostęp do stanów ---------- */
  var S = E.states;
  E.st = function (id) { return S[id]; };
  E.val = function (id) { return S[id] ? S[id].s : undefined; };
  E.attr = function (id, k) { var x = S[id]; return x && x.a ? x.a[k] : undefined; };
  E.ok = function (id) {
    var v = E.val(id);
    return v != null && v !== "unavailable" && v !== "unknown" && v !== "";
  };
  E.has = function (id) { return !!S[id]; };
  E.num = function (id) {
    if (!E.ok(id)) return null;
    var v = E.val(id), n = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
    return isNaN(n) ? null : n;
  };

  /* ---------- formatowanie ---------- */
  E.DAYS = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
  E.DAYS3 = ["nd", "pon", "wt", "śr", "czw", "pt", "sob"];
  E.MON = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"];
  E.MON3 = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
  E.pad = function (n) { return String(n).padStart(2, "0"); };
  E.hm = function (d) { d = new Date(d); return isNaN(d) ? "—" : d.getHours() + ":" + E.pad(d.getMinutes()); };
  E.dm = function (d) { d = new Date(d); return isNaN(d) ? "—" : d.getDate() + " " + E.MON3[d.getMonth()]; };
  E.dmShort = function (d) { d = new Date(d); return isNaN(d) ? "—" : d.getDate() + "." + E.pad(d.getMonth() + 1); };
  E.dow = function (d) { d = new Date(d); return isNaN(d) ? "" : E.DAYS3[d.getDay()]; };
  E.num2 = function (n) { return n == null || isNaN(n) ? "—" : Number(n).toFixed(2).replace(".", ","); };
  E.sameDay = function (a, b) {
    a = new Date(a); b = new Date(b);
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  };
  E.midnight = function (d, add) {
    d = d ? new Date(d) : new Date();
    d.setHours(0, 0, 0, 0);
    if (add) d.setDate(d.getDate() + add);
    return d;
  };
  /* "pt 17.10" albo "dziś"/"jutro" */
  E.whenLabel = function (d) {
    d = new Date(d); if (isNaN(d)) return "—";
    var t = E.midnight(), dd = E.midnight(d);
    var diff = Math.round((dd - t) / 864e5);
    if (diff === 0) return "dziś";
    if (diff === 1) return "jutro";
    if (diff === -1) return "wczoraj";
    return E.dow(d) + " " + E.dmShort(d);
  };
  /* odmiana: 1 lekcja, 2-4 lekcje, 5+ lekcji */
  E.plural = function (n, one, few, many) {
    n = Math.abs(n);
    if (n === 1) return one;
    var t = n % 10, h = n % 100;
    if (t >= 2 && t <= 4 && (h < 12 || h > 14)) return few;
    return many;
  };

  /* ---------- motyw ---------- */
  var night = null;
  function wantNight() {
    var t = E.cfg().theme;
    if (t === "night") return true;
    if (t === "day") return false;
    var h = new Date().getHours();
    return h >= 20 || h < 6;
  }
  function paint(n) {
    var r = document.documentElement;
    if (n) r.setAttribute("data-theme", "night"); else r.removeAttribute("data-theme");
    r.style.backgroundColor = n ? "#22262b" : "#e7ebf0";
    var cs = document.querySelector('meta[name="color-scheme"]'), tc = document.querySelector('meta[name="theme-color"]');
    if (cs) cs.setAttribute("content", n ? "dark" : "only light");
    if (tc) tc.setAttribute("content", n ? "#22262b" : "#e7ebf0");
    try { localStorage.setItem("edz_night", n ? "1" : "0"); } catch (e) {}
  }
  E.isNight = function () { return !!night; };
  E.applyTheme = function () {
    var n = wantNight();
    if (night === n) return;
    night = n; paint(n); E.mark("@theme");
  };
  E.setTheme = function (t) { E.put("theme", t); E.applyTheme(); E.mark("@theme"); };

  /* ---------- toast ---------- */
  var toastBox = null;
  E.setToastBox = function (el) { toastBox = el; };
  E.toast = function (text, tone) {
    if (!toastBox) return;
    var el = document.createElement("div");
    el.className = "e-toast"; if (tone) el.setAttribute("data-tone", tone);
    el.textContent = text; toastBox.appendChild(el);
    setTimeout(function () { el.remove(); }, 4200);
  };

  /* ---------- WebSocket ---------- */
  var ws = null, seq = 0, pend = new Map(), subs = new Set(), live = new Map();
  var tok = null, tokKey = null, tries = 0, retry = 0, waiters = [];
  S["@conn"] = { s: "connecting", a: {} };

  function conn(v) { S["@conn"] = { s: v, a: {} }; E.live = v === "on"; E.mark("@conn"); }

  async function token() {
    tokKey = null;
    try {
      var keys = ["edz_token", "perla_token", "gf_token", "k3_token"];
      for (var i = 0; i < keys.length; i++) {
        var v = localStorage.getItem(keys[i]);
        if (v) { tokKey = keys[i]; return v; }
      }
    } catch (e) {}
    var ht = null;
    try { ht = JSON.parse(localStorage.getItem("hassTokens") || "null"); } catch (e) {}
    if (!ht) return null;
    if (tok && tok.expires > Date.now() + 3e4) return tok.access_token;
    if (ht.expires && ht.expires > Date.now() + 3e4) return ht.access_token;
    if (!ht.refresh_token) return null;
    var r = await fetch("/auth/token", {
      method: "POST",
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: ht.refresh_token,
        client_id: ht.clientId || location.origin + "/"
      })
    });
    if (!r.ok) return null;
    var j = await r.json();
    tok = { access_token: j.access_token, expires: Date.now() + j.expires_in * 1e3 };
    return tok.access_token;
  }

  E.send = function (msg) {
    return new Promise(function (res, rej) {
      if (!ws || ws.readyState !== 1 || !E.live) return rej(new Error("offline"));
      var id = ++seq; pend.set(id, { res: res, rej: rej });
      ws.send(JSON.stringify(Object.assign({ id: id }, msg)));
    });
  };
  E.whenLive = function () {
    return E.live ? Promise.resolve() : new Promise(function (r) { waiters.push(r); });
  };

  function subStart(s) {
    s.id = ++seq;
    pend.set(s.id, { res: function () {}, rej: function () {}, sub: s });
    ws.send(JSON.stringify(Object.assign({ id: s.id }, s.msg)));
  }
  E.subscribe = function (msg, cb) {
    var s = { msg: msg, cb: cb, id: 0, dead: false };
    subs.add(s);
    if (E.live) subStart(s);
    return function () { s.dead = true; subs.delete(s); live.delete(s.id); };
  };

  /* subscribe_entities — kompaktowy format a/c/r */
  function onEntities(ev) {
    var k;
    if (ev.a) {
      for (k in ev.a) { var n = ev.a[k]; if (!n.a) n.a = {}; S[k] = n; E.mark(k); }
      if (!E.ready) { E.ready = true; E.mark("@data"); }
    }
    if (ev.c) {
      for (k in ev.c) {
        var ch = ev.c[k], plus = ch["+"], cur = S[k] || { s: "unknown", a: {} };
        var next = { s: cur.s, a: cur.a, lc: cur.lc, lu: cur.lu };
        if (plus) {
          if (plus.s !== undefined) next.s = plus.s;
          if (plus.a) next.a = Object.assign({}, next.a, plus.a);
          if (plus.lc !== undefined) next.lc = plus.lc; else if (plus.lu !== undefined) next.lc = plus.lu;
          if (plus.lu !== undefined) next.lu = plus.lu;
        }
        if (ch["-"] && ch["-"].a) {
          next.a = Object.assign({}, next.a);
          ch["-"].a.forEach(function (x) { delete next.a[x]; });
        }
        S[k] = next; E.mark(k);
      }
    }
    if (ev.r) ev.r.forEach(function (k) { delete S[k]; E.mark(k); });
  }

  function drop() { pend.forEach(function (p) { if (!p.sub) p.rej(new Error("offline")); }); pend.clear(); }
  function noauth() { conn("noauth"); }
  function fail() { tries++; conn("off"); clearTimeout(retry); retry = setTimeout(open, Math.min(15e3, 1e3 * tries + 1e3)); }

  function open() {
    clearTimeout(retry);
    if (ws) { var old = ws; ws = null; old.onmessage = old.onclose = null; try { old.close(); } catch (e) {} drop(); }
    conn(tries ? "off" : "connecting");
    var s;
    try {
      s = ws = new WebSocket((location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + "/api/websocket");
    } catch (e) { ws = null; return fail(); }
    s.onmessage = async function (m) {
      if (s !== ws) return;
      var d = JSON.parse(m.data);
      if (d.type === "auth_required") {
        var t;
        try { t = await token(); } catch (e) { if (s === ws) s.close(); return; }
        if (s !== ws) return;
        if (!t) return noauth();
        s.send(JSON.stringify({ type: "auth", access_token: t }));
      } else if (d.type === "auth_invalid") {
        tok = null;
        var cleared = false;
        try { if (tokKey) { cleared = true; localStorage.removeItem(tokKey); } } catch (e) {}
        if (!cleared) noauth();
      } else if (d.type === "auth_ok") {
        tries = 0; E.live = true; live.clear();
        subs.forEach(subStart); conn("on");
        waiters.splice(0).forEach(function (f) { f(); });
      } else if (d.type === "result") {
        var p = pend.get(d.id); if (!p) return;
        pend.delete(d.id);
        if (p.sub) { if (d.success) live.set(d.id, p.sub); return; }
        if (d.success) p.res(d.result); else p.rej(d.error || new Error("error"));
      } else if (d.type === "event") {
        var sb = live.get(d.id) || (pend.get(d.id) || {}).sub;
        if (sb && !sb.dead) { try { sb.cb(d.event); } catch (e) { console.error("[edz] event", e); } }
      }
    };
    s.onclose = function () {
      if (s !== ws) return;
      ws = null; drop();
      if (S["@conn"].s !== "noauth") fail();
    };
  }

  E.setToken = function (t) {
    try { localStorage.setItem("edz_token", t); } catch (e) {}
    tries = 0; open();
  };
  E.start = function () {
    E.subscribe({ type: "subscribe_entities", entity_ids: E.ALL }, onEntities);
    open();
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && (!ws || ws.readyState > 1) && S["@conn"].s !== "noauth") { tries = 0; open(); }
    });
  };

  /* ---------- kalendarz (plan lekcji, zadania) ---------- */
  var cache = new Map();
  function cached(key, ttl, make) {
    var c = cache.get(key);
    if (c && Date.now() - c.at < ttl) return c.p;
    var p = E.whenLive().then(make);
    cache.set(key, { at: Date.now(), p: p });
    p.catch(function () { cache.delete(key); });
    return p;
  }
  E.events = function (ids, from, to) {
    ids = [].concat(ids);
    return cached("c|" + ids.join() + "|" + from.getTime() + "|" + to.getTime(), 3e5, function () {
      return E.send({
        type: "call_service", domain: "calendar", service: "get_events",
        target: { entity_id: ids },
        service_data: { start_date_time: local(from), end_date_time: local(to) },
        return_response: true
      }).then(function (r) {
        var out = [], resp = (r && r.response) || {};
        Object.keys(resp).forEach(function (cal) {
          (resp[cal].events || []).forEach(function (ev) {
            var allDay = String(ev.start).length <= 10;
            out.push({
              cal: cal,
              title: ev.summary || "(bez tytułu)",
              allDay: allDay,
              where: ev.location || "",
              note: ev.description || "",
              s: new Date(allDay ? ev.start + "T00:00:00" : ev.start),
              e: new Date(allDay ? ev.end + "T00:00:00" : ev.end)
            });
          });
        });
        out.sort(function (a, b) { return a.s - b.s; });
        return out;
      });
    });
  };
  E.dropCache = function () { cache.clear(); };
  function local(d) {
    return d.getFullYear() + "-" + E.pad(d.getMonth() + 1) + "-" + E.pad(d.getDate()) +
      "T" + E.pad(d.getHours()) + ":" + E.pad(d.getMinutes()) + ":" + E.pad(d.getSeconds());
  }
  E.localStamp = local;
})();
