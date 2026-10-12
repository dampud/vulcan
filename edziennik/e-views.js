/* e-views.js — sekcje panelu: Dziś, Oceny, Zadania, Poczta, Budziki, Ustawienia.
   Panel jest tylko-czytający: żadna sekcja nie woła usługi HA poza calendar.get_events. */
(function () {
  "use strict";
  var E = window.E, h = E.h, mi = E.mi, V = E.views = {};

  /* ===================== pomocnicze: plan lekcji ===================== */

  /* "1 Zajęcia kształtujące…" → {nr:1, name:"Zajęcia kształtujące…"} */
  function lesson(ev) {
    var m = /^\s*(\d{1,2})[.\s)]+(.*)$/.exec(ev.title || "");
    return {
      nr: m ? parseInt(m[1], 10) : null,
      name: (m ? m[2] : ev.title || "").trim(),
      room: ev.where || "",
      who: String(ev.note || "").replace(/^\s*Nauczyciel:\s*/i, "").trim(),
      s: ev.s, e: ev.e
    };
  }

  /* Zmiany w planie: lista tekstów z integracji; format nie jest ustalony, więc
     dopasowanie jest ostrożne — szukamy daty (dd.mm, d.m, YYYY-MM-DD) i numeru lekcji. */
  function changes() {
    var list = E.attr(E.ENT.zmiany7, "zmiany");
    return Array.isArray(list) ? list.map(String) : [];
  }
  function kindOf(text) {
    var t = text.toLowerCase();
    if (/odwoł|odwol|nie ma|wolne/.test(t)) return "off";
    if (/zast[ęe]p|przeniesio|zmiana sal|zmieniono/.test(t)) return "sub";
    return "sub";
  }
  function changeFor(day, nr) {
    var d = new Date(day), iso = d.getFullYear() + "-" + E.pad(d.getMonth() + 1) + "-" + E.pad(d.getDate());
    var dm = d.getDate() + "." + E.pad(d.getMonth() + 1), dm2 = E.pad(d.getDate()) + "." + E.pad(d.getMonth() + 1);
    var hit = null;
    changes().forEach(function (t) {
      if (hit) return;
      if (t.indexOf(iso) < 0 && t.indexOf(dm) < 0 && t.indexOf(dm2) < 0) return;
      if (nr != null && !new RegExp("(^|[^0-9])" + nr + "([^0-9]|$)").test(t)) return;
      hit = { text: t, kind: kindOf(t) };
    });
    return hit;
  }

  function lessonRow(l, now) {
    var ch = changeFor(l.s, l.nr);
    var st = ch ? ch.kind : (now >= l.s && now < l.e ? "now" : (l.e < now ? "done" : null));
    var sub = [l.room ? "s. " + l.room : null, l.who || null].filter(Boolean).join(" · ");
    return h("div", { class: "e-les", "data-st": st },
      h("span", { class: "e-les__t" }, h("b", { text: E.hm(l.s) }), E.hm(l.e)),
      h("span", { class: "e-les__k" }),
      h("span", { style: "min-width:0" },
        h("span", { class: "e-les__n", text: (l.nr != null ? l.nr + ". " : "") + l.name }),
        h("span", { class: "e-les__s", text: sub || "—" })),
      ch ? E.tag(ch.kind === "off" ? "odwołana" : "zmiana", ch.kind)
        : (st === "now" ? E.tag("teraz", "amber") : h("span")));
  }

  /* ===================== Dziś ===================== */

  V.dzis = {
    icon: "today", label: "Dziś",
    build: function (sc) {
      var out = [];

      /* pasek zmian w planie */
      var band = h("div");
      sc.bind([E.ENT.zmiany7], function () {
        band.textContent = "";
        var n = E.num(E.ENT.zmiany7) || 0, list = changes();
        if (!n && !list.length) return;
        var txt = n + " " + E.plural(n, "zmiana", "zmiany", "zmian") + " w planie na najbliższe 7 dni";
        band.appendChild(E.banner(list.length ? list[0] : txt, "warn", "swap"));
      });
      out.push(band);

      /* plan na dziś z kalendarza */
      var planBody = h("div", { class: "e-list" });
      var planTag = E.tag("—");
      var planCard = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "Plan na dziś" }), planTag),
        planBody);

      function loadPlan() {
        var from = E.midnight(), to = E.midnight(null, 1);
        planBody.textContent = "";
        planBody.appendChild(E.lazy(sc, E.events(E.CAL.plan, from, to), function (evs) {
          var ls = evs.filter(function (x) { return !x.allDay; }).map(lesson);
          if (!ls.length) {
            E.set(planTag, "brak lekcji");
            return E.empty("Dziś nie ma lekcji w planie.");
          }
          var now = new Date();
          E.set(planTag, ls.length + " " + E.plural(ls.length, "lekcja", "lekcje", "lekcji") +
            " · koniec " + E.hm(ls[ls.length - 1].e));
          return ls.map(function (l) { return lessonRow(l, now); });
        }));
      }
      sc.bind(["@data", "@refresh", E.ENT.zmiany7], loadPlan);
      sc.every(3e5, function () { E.dropCache(); loadPlan(); });

      /* następny dzień nauki + sugerowana pobudka */
      var nextBig = h("div", { class: "e-big", text: "—" });
      var nextNote = h("div", { class: "e-note", text: "—" });
      var nextTag = E.tag("—");
      var wakeRow = h("div", { class: "e-list" });
      var nextCard = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "Następny dzień nauki" }), nextTag),
        h("div", null, nextBig, nextNote),
        wakeRow);

      sc.bind(["@data", "@set", "@min", E.ENT.nast, E.ENT.jutro], function () {
        var id = E.ok(E.ENT.nast) ? E.ENT.nast : E.ENT.jutro;
        wakeRow.textContent = "";
        if (!E.ok(id)) {
          E.set(nextBig, "—"); E.set(nextNote, "Brak danych o pierwszej lekcji."); E.set(nextTag, "—");
          return;
        }
        var t = new Date(E.val(id));
        E.set(nextBig, E.hm(t));
        var przedmiot = E.attr(id, "przedmiot") || "—", sala = E.attr(id, "sala"), nr = E.attr(id, "lekcja");
        E.set(nextNote, (nr != null ? nr + ". lekcja — " : "") + przedmiot + (sala ? ", s. " + sala : ""));
        E.set(nextTag, E.whenLabel(t));
        var s = E.cfg();
        var w = wake(t, s);
        wakeRow.appendChild(E.infoRow(
          s.wakeOn ? "Pobudka " + E.hm(w.at) : "Pobudka wyłączona",
          s.wakeOn
            ? s.wake + " min przed lekcją" + (w.floored ? " · podniesiona do granicy " + s.wakeFloor : "")
            : "Włącz w sekcji Budziki",
          s.wakeOn ? E.tag(E.hm(w.at), "amber") : E.tag("—")));
        if (E.attr(id, "zmiana")) wakeRow.appendChild(E.row("Zmiana w tym dniu", String(E.attr(id, "uwagi") || "zgłoszona przez dziennik"), null, { icon: "swap" }));
      });

      /* najbliższe sprawdziany */
      var sprCard = E.card("Najbliższe sprawdziany", E.tag("—"));
      var sprTag = sprCard.querySelector(".e-tag");
      sc.bind(["@data", E.ENT.sprawdzian, E.ENT.spr7], function () {
        var body = sprCard._body; body.textContent = "";
        var n = E.num(E.ENT.spr7);
        E.set(sprTag, n == null ? "—" : n + " w 7 dni");
        var all = E.attr(E.ENT.sprawdzian, "wszystkie");
        var items = (Array.isArray(all) ? all : []).map(parseExam).filter(Boolean);
        if (!items.length) {
          if (E.ok(E.ENT.sprawdzian)) {
            body.appendChild(E.row(
              String(E.attr(E.ENT.sprawdzian, "przedmiot") || "Sprawdzian"),
              String(E.attr(E.ENT.sprawdzian, "rodzaj") || ""),
              E.whenLabel(E.val(E.ENT.sprawdzian))));
          } else body.appendChild(E.empty("Brak zapowiedzianych sprawdzianów."));
          return;
        }
        var today = E.midnight();
        items.filter(function (x) { return x.d >= today; }).slice(0, 6).forEach(function (x) {
          body.appendChild(E.row(x.subject, x.kind, E.whenLabel(x.d)));
        });
      });

      /* uwagi */
      var uwCard = E.card("Uwagi", E.tag("—"));
      var uwTag = uwCard.querySelector(".e-tag");
      sc.bind(["@data", E.ENT.uwagi], function () {
        var body = uwCard._body; body.textContent = "";
        var pos = Number(E.attr(E.ENT.uwagi, "pozytywne") || 0), neg = Number(E.attr(E.ENT.uwagi, "negatywne") || 0);
        E.set(uwTag, pos + " / " + neg);
        uwTag.setAttribute("data-tone", neg > 0 ? "off" : "ok");
        body.appendChild(E.row("Pochwały", "wpisy pozytywne", String(pos), { icon: "check" }));
        body.appendChild(E.row("Uwagi", "wpisy negatywne", String(neg), { icon: "warn" }));
      });

      out.push(h("div", { class: "e-cols" },
        h("div", { class: "e-stack" }, planCard),
        h("div", { class: "e-stack" }, nextCard, sprCard, uwCard)));
      return out;
    }
  };

  /* "2026-10-13 Matematyka (Sprawdzian)" */
  function parseExam(t) {
    var m = /^(\d{4}-\d{2}-\d{2})\s+(.*?)\s*(?:\(([^)]*)\))?\s*$/.exec(String(t));
    if (!m) return null;
    return { d: new Date(m[1] + "T00:00:00"), subject: m[2], kind: m[3] || "" };
  }

  function wake(lessonAt, s) {
    var at = new Date(new Date(lessonAt).getTime() - s.wake * 6e4);
    var fm = /^(\d{1,2}):(\d{2})$/.exec(s.wakeFloor || "");
    var floored = false;
    if (fm) {
      var floor = new Date(at);
      floor.setHours(parseInt(fm[1], 10), parseInt(fm[2], 10), 0, 0);
      if (at < floor) { at = floor; floored = true; }
    }
    return { at: at, floored: floored };
  }
  E.wakeAt = wake;

  /* ===================== Oceny ===================== */

  V.oceny = {
    icon: "star", label: "Oceny",
    build: function (sc) {
      var eyeIc = mi("eye"), eyeTx = h("span", { text: "Ukryj" });
      var eye = h("button", { class: "e-btn e-btn--sm", type: "button", "aria-pressed": "false" }, eyeIc, eyeTx);
      eye.addEventListener("click", function () { E.put("hideGrades", !E.cfg().hideGrades); });

      var avgTag = h("span", { class: "e-tag", "data-sec": "", text: "—" });
      var subjects = h("div", { class: "e-list" });
      var main = h("div", { class: "e-card" },
        h("div", { class: "e-chead" },
          h("h2", { class: "e-cap", text: "Oceny — średnia ważona" }),
          h("div", { class: "e-btnrow" }, avgTag, eye)),
        subjects);

      var last = E.card("Ostatnia ocena");
      var side = h("div", { class: "e-grid2" }, last);

      function render() {
        var s = E.cfg(), hide = !!s.hideGrades;
        [main, last].forEach(function (c) { c.classList.toggle("e-hide", hide); });
        eye.setAttribute("aria-pressed", hide ? "true" : "false");
        E.setMi(eyeIc, hide ? "eyeOff" : "eye");
        E.set(eyeTx, hide ? "Pokaż" : "Ukryj");
      }

      sc.bind(["@set"], render);

      sc.bind(["@data", E.ENT.oceny], function () {
        subjects.textContent = "";
        if (!E.has(E.ENT.oceny)) {
          E.set(avgTag, "—");
          subjects.appendChild(E.empty("Encja z ocenami pojawi się po restarcie Home Assistanta."));
          return;
        }
        var avg = E.num(E.ENT.oceny);
        var cnt = E.attr(E.ENT.oceny, "liczba_ocen"), bez = E.attr(E.ENT.oceny, "bez_wartosci");
        E.set(avgTag, (avg == null ? "—" : "średnia " + E.num2(avg)) +
          (cnt != null ? " · " + cnt + " " + E.plural(cnt, "ocena", "oceny", "ocen") : "") +
          (bez ? " · " + bez + " bez wartości" : ""));
        var list = E.attr(E.ENT.oceny, "przedmioty");
        if (!Array.isArray(list) || !list.length) {
          subjects.appendChild(E.empty("Brak ocen w tym okresie."));
          return;
        }
        list.slice().sort(function (a, b) {
          return String(a.przedmiot || "").localeCompare(String(b.przedmiot || ""), "pl");
        }).forEach(function (p) {
          var sr = typeof p.srednia === "number" ? p.srednia : parseFloat(String(p.srednia).replace(",", "."));
          var marks = Array.isArray(p.oceny) ? p.oceny : [];
          subjects.appendChild(h("div", { class: "e-subj" },
            h("span", { class: "e-subj__n", text: String(p.przedmiot || "—") },
              p.liczba != null ? h("span", { class: "e-subj__c", text: " · " + p.liczba }) : null),
            h("span", {
              class: "e-subj__avg",
              text: isNaN(sr) ? "—" : E.num2(sr),
              "data-good": !isNaN(sr) && sr >= 4.5 ? "" : null,
              "data-bad": !isNaN(sr) && sr < 3.5 ? "" : null
            }),
            h("span", { class: "e-marks" }, marks.map(function (m) {
              var flat = m.wartosc == null || m.wartosc === "" || Number(m.waga) === 0;
              return h("span", {
                class: "e-mark", "data-flat": flat ? "" : null,
                title: [m.kolumna, m.data ? E.dmShort(m.data) : null, m.waga != null ? "waga " + m.waga : null]
                  .filter(Boolean).join(" · ")
              }, String(m.ocena == null ? "—" : m.ocena),
                m.waga ? h("small", { text: String(m.waga) }) : null);
            }))));
        });
      });

      sc.bind(["@data", E.ENT.ocena], function () {
        var body = last._body; body.textContent = "";
        if (!E.ok(E.ENT.ocena)) { body.appendChild(E.empty("Brak danych o ostatniej ocenie.")); return; }
        var d = E.attr(E.ENT.ocena, "data");
        body.appendChild(E.row(
          String(E.val(E.ENT.ocena)) + " — " + String(E.attr(E.ENT.ocena, "przedmiot") || "—"),
          [E.attr(E.ENT.ocena, "kolumna"), E.attr(E.ENT.ocena, "waga") != null ? "waga " + E.attr(E.ENT.ocena, "waga") : null]
            .filter(Boolean).join(" · "),
          d ? E.whenLabel(d) : null, { secret: true, fresh: true, icon: "star" }));
      });

      render();
      return [main, side];
    }
  };

  /* ===================== Zadania ===================== */

  V.zadania = {
    icon: "tasks", label: "Zadania",
    build: function (sc) {
      var listBody = h("div", { class: "e-list" });
      var listTag = E.tag("—");
      var card = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "Sprawdziany i zadania — 21 dni" }), listTag),
        listBody);

      function load() {
        var from = E.midnight(), to = E.midnight(null, 21);
        listBody.textContent = "";
        listBody.appendChild(E.lazy(sc, E.events(E.CAL.zadania, from, to), function (evs) {
          if (!evs.length) { E.set(listTag, "brak"); return E.empty("Nic nie jest zapowiedziane na najbliższe 3 tygodnie."); }
          E.set(listTag, evs.length + " " + E.plural(evs.length, "pozycja", "pozycje", "pozycji"));
          return evs.map(function (ev) {
            var when = E.whenLabel(ev.s);
            var soon = E.midnight(ev.s) <= E.midnight(null, 1);
            return E.row(ev.title, ev.note || "", h("span", { class: "e-row__v" },
              soon ? E.tag(when, "off") : document.createTextNode(when)));
          });
        }));
      }
      sc.bind(["@data", "@refresh"], load);

      /* zmiany w planie */
      var chCard = E.card("Zmiany w planie — 7 dni", E.tag("—"));
      var chTag = chCard.querySelector(".e-tag");
      sc.bind(["@data", E.ENT.zmiany7], function () {
        var body = chCard._body; body.textContent = "";
        var n = E.num(E.ENT.zmiany7) || 0, list = changes();
        E.set(chTag, n + " " + E.plural(n, "zmiana", "zmiany", "zmian"));
        chTag.setAttribute("data-tone", n ? "sub" : "ok");
        if (!list.length) { body.appendChild(E.empty(n ? "Dziennik zgłasza zmiany, ale nie podał szczegółów." : "Brak zastępstw i odwołanych lekcji.")); return; }
        list.forEach(function (t) {
          var k = kindOf(t);
          body.appendChild(E.row(t, null, E.tag(k === "off" ? "odwołana" : "zastępstwo", k), { icon: "swap" }));
        });
      });

      return [h("div", { class: "e-grid2" }, card, chCard)];
    }
  };

  /* ===================== Poczta ===================== */

  /* "20.05 16:21 Nazwisko Imię [XX] - P - (ZSP18): Temat" */
  function parseMail(t) {
    t = String(t);
    var m = /^(\d{1,2}\.\d{1,2})(?:\s+(\d{1,2}:\d{2}))?\s+(.*)$/.exec(t);
    var head = m ? m[3] : t, when = m ? m[1] + (m[2] ? " " + m[2] : "") : "";
    var i = head.indexOf(":");
    var from = i > 0 ? head.slice(0, i) : head, subj = i > 0 ? head.slice(i + 1).trim() : "";
    from = from.replace(/\s*\[[^\]]*\]\s*/g, " ").replace(/\s*-\s*[A-Z]\s*-\s*/g, " · ").replace(/\s+/g, " ").trim();
    return { when: when, from: from, subject: subj || from };
  }

  V.poczta = {
    icon: "mail", label: "Poczta",
    badge: function () { return E.num(E.ENT.poczta) || 0; },
    build: function (sc) {
      var card = E.card("Nieprzeczytane wiadomości", E.tag("—"));
      var tag = card.querySelector(".e-tag");
      sc.bind(["@data", E.ENT.poczta], function () {
        var body = card._body; body.textContent = "";
        var n = E.num(E.ENT.poczta);
        E.set(tag, n == null ? "—" : n + " " + E.plural(n, "nieprzeczytana", "nieprzeczytane", "nieprzeczytanych"));
        tag.setAttribute("data-tone", n ? "amber" : "ok");
        var list = E.attr(E.ENT.poczta, "ostatnie");
        if (!Array.isArray(list) || !list.length) {
          body.appendChild(E.empty(n ? "Dziennik nie podał listy wiadomości." : "Brak nieprzeczytanych wiadomości."));
          return;
        }
        list.map(parseMail).forEach(function (m) {
          body.appendChild(E.row(m.subject, m.from, m.when, { icon: "dot", fresh: true }));
        });
      });

      var note = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "O tej liście" })),
        h("p", { class: "e-note", text: "Panel tylko pokazuje to, co udostępnia integracja: licznik i ostatnie tytuły. Nie da się tu wiadomości otworzyć, oznaczyć jako przeczytanej ani odpisać — to robi się w eduVULCAN." }));

      return [h("div", { class: "e-cols" }, card, note)];
    }
  };

  /* ===================== Budziki ===================== */

  V.budziki = {
    icon: "alarm", label: "Budziki",
    build: function (sc) {
      var s = E.cfg();

      var card = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "Pobudka od planu" })),
        h("p", { class: "e-note", text: "Liczona od pierwszej lekcji najbliższego dnia nauki. Ustawienia zapisują się na tym urządzeniu — panel niczego nie zmienia w Home Assistancie." }));

      card.appendChild(h("div", { class: "e-list" },
        E.toggle(sc, {
          label: "Pokazuj pobudkę", note: "wyliczona godzina na ekranie Dziś",
          get: function () { return E.cfg().wakeOn; },
          set: function (v) { E.put("wakeOn", v); }
        })));

      card.appendChild(E.step(sc, {
        min: 30, max: 180, stepBy: 5,
        get: function () { return E.cfg().wake; },
        set: function (v) { E.put("wake", v); },
        text: function (v) { return v + " min"; }
      }));

      var floors = ["5:30", "6:00", "6:30", "7:00"];
      card.appendChild(h("div", null,
        h("p", { class: "e-cap", text: "Nie wcześniej niż", style: "margin:4px 2px" }),
        E.seg(sc, {
          label: "Najwcześniejsza pobudka",
          opts: floors.map(function (f) { return { v: f, label: f }; }),
          get: function () { return E.cfg().wakeFloor; },
          set: function (v) { E.put("wakeFloor", v); }
        })));

      /* najbliższe pobudki z kalendarza */
      var nextCard = E.card("Najbliższe pobudki", E.tag("7 dni"));
      function load() {
        var body = nextCard._body; body.textContent = "";
        body.appendChild(E.lazy(sc, E.events(E.CAL.plan, E.midnight(), E.midnight(null, 8)), function (evs) {
          var byDay = {};
          evs.filter(function (x) { return !x.allDay; }).forEach(function (ev) {
            var k = E.midnight(ev.s).getTime();
            if (!byDay[k] || ev.s < byDay[k].s) byDay[k] = ev;
          });
          var days = Object.keys(byDay).map(Number).sort();
          var now = Date.now();
          var rows = days.filter(function (k) { return byDay[k].s.getTime() > now; }).slice(0, 7).map(function (k) {
            var ev = byDay[k], st = E.cfg(), w = E.wakeAt(ev.s, st);
            return E.row(
              E.DAYS[new Date(k).getDay()] + " " + E.dmShort(k),
              "pierwsza lekcja " + E.hm(ev.s) + (w.floored ? " · ograniczone do " + st.wakeFloor : ""),
              st.wakeOn ? E.hm(w.at) : "—");
          });
          return rows.length ? rows : E.empty("W najbliższych 7 dniach nie ma lekcji w kalendarzu.");
        }));
      }
      sc.bind(["@data", "@set", "@refresh"], load);

      return [h("div", { class: "e-grid2" }, card, nextCard)];
    }
  };

  /* ===================== Ustawienia ===================== */

  V.ustawienia = {
    icon: "cog", label: "Ustawienia",
    build: function (sc) {
      var look = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "Wygląd" })),
        E.seg(sc, {
          label: "Motyw", ids: ["@theme"],
          opts: [
            { v: "day", icon: "sun", label: "Jasny" },
            { v: "night", icon: "moon", label: "Nocny" },
            { v: "auto", icon: "auto", label: "Auto" }
          ],
          get: function () { return E.cfg().theme; },
          set: function (v) { E.setTheme(v); }
        }),
        h("p", { class: "e-note", text: "„Auto” przechodzi w tryb nocny między 20:00 a 6:00. Wybór zapisuje się na tym urządzeniu." }),
        h("div", { class: "e-list" },
          E.toggle(sc, {
            label: "Oceny ukryte na starcie", note: "panel startuje z zasłoniętymi ocenami",
            get: function () { return E.cfg().hideGrades; },
            set: function (v) { E.put("hideGrades", v); }
          })),
        h("p", { class: "e-cap", text: "Sekcja na starcie", style: "margin:6px 2px" }),
        E.seg(sc, {
          label: "Sekcja startowa",
          opts: [
            { v: "dzis", label: "Dziś" },
            { v: "oceny", label: "Oceny" },
            { v: "zadania", label: "Zadania" }
          ],
          get: function () { return E.cfg().grid; },
          set: function (v) { E.put("grid", v); }
        }));

      var diag = E.card("Dane i połączenie", h("button", {
        class: "e-btn e-btn--sm", type: "button",
        tap: function () { E.dropCache(); E.mark("@refresh"); E.toast("Odświeżono kalendarze."); }
      }, mi("sync"), h("span", { text: "Odśwież" })));

      sc.bind(["@conn", "@data", E.ENT.sync, E.ENT.oceny, E.ENT.numerek], function () {
        var body = diag._body; body.textContent = "";
        var c = E.val("@conn");
        var conn = c === "on" ? "połączono" : c === "noauth" ? "brak autoryzacji" : c === "off" ? "rozłączono" : "łączenie…";
        body.appendChild(E.row("Home Assistant", "WebSocket " + location.host, conn, { icon: "link" }));
        var ok = E.attr(E.ENT.sync, "ok"), err = E.attr(E.ENT.sync, "błąd") || E.attr(E.ENT.sync, "blad");
        body.appendChild(E.row("Ostatnia synchronizacja dziennika",
          err ? String(err) : (ok === false ? "ostatnia próba nieudana" : "integracja vulcan_dom"),
          E.ok(E.ENT.sync) ? E.whenLabel(E.val(E.ENT.sync)) + ", " + E.hm(E.val(E.ENT.sync)) : "—",
          { icon: "sync" }));
        body.appendChild(E.row("Encja z ocenami",
          E.has(E.ENT.oceny) ? E.ENT.oceny : "pojawi się po restarcie Home Assistanta",
          E.has(E.ENT.oceny) ? "dostępna" : "brak", { icon: "star" }));
        body.appendChild(E.row("Szczęśliwy numerek", "na dziś",
          E.ok(E.ENT.numerek) ? String(E.val(E.ENT.numerek)) : "—", { icon: "star" }));
      });

      var reset = h("div", { class: "e-card" },
        h("div", { class: "e-chead" }, h("h2", { class: "e-cap", text: "To urządzenie" })),
        h("p", { class: "e-note", text: "Panel nie zapisuje niczego w Home Assistancie. Wszystkie ustawienia (motyw, ukrycie ocen, pobudka, sekcja startowa) żyją w pamięci tej przeglądarki." }),
        h("div", { class: "e-btnrow" },
          h("button", {
            class: "e-btn", type: "button",
            tap: function () {
              try { localStorage.removeItem("edz_set"); } catch (e) {}
              location.reload();
            }
          }, mi("swap"), h("span", { text: "Przywróć domyślne" }))));

      return [h("div", { class: "e-grid2" }, look, diag), reset];
    }
  };
})();
