/* Pulpit "Szkoła" dla integracji vulcan_dom.
 *
 * Dwa tryby:
 *   DEMO  — bez żadnej konfiguracji, na danych z dane-demo.js. Tak strona
 *           zachowuje się po otwarciu pliku z dysku.
 *   ŻYWY  — gdy w adresie jest ?prefix=sensor.imie_nazwisko, strona czyta stany
 *           z API Home Assistanta. Wymaga tokenu (wpisywanego raz, patrz README).
 *
 * Nic poza tokenem i wyborem motywu nie jest zapisywane w przeglądarce.
 */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  // Po polsku separatorem dziesiętnym jest przecinek — "4,21", nie "4.21".
  const lb = (n, cyfry = 2) =>
    n == null || n === "" || Number.isNaN(Number(n))
      ? "—"
      : Number(n).toLocaleString("pl-PL", { maximumFractionDigits: cyfry });

  const el = (tag, klasa, tekst) => {
    const n = document.createElement(tag);
    if (klasa) n.className = klasa;
    if (tekst != null) n.textContent = tekst;
    return n;
  };

  // --- motyw -----------------------------------------------------------------

  const MOTYWY = ["auto", "jasny", "ciemny"];
  function ustawMotyw(m) {
    document.documentElement.dataset.motyw = m;
    try { localStorage.setItem("szkola_motyw", m); } catch { /* tryb prywatny */ }
  }
  try {
    const zapisany = localStorage.getItem("szkola_motyw");
    if (MOTYWY.includes(zapisany)) document.documentElement.dataset.motyw = zapisany;
  } catch { /* brak dostępu do localStorage — zostaje auto */ }
  $("#motyw").addEventListener("click", () => {
    const teraz = document.documentElement.dataset.motyw || "auto";
    ustawMotyw(MOTYWY[(MOTYWY.indexOf(teraz) + 1) % MOTYWY.length]);
  });

  // --- ukrywanie ocen --------------------------------------------------------

  let oceny_ukryte = false;
  try { oceny_ukryte = localStorage.getItem("szkola_oceny_ukryte") === "1"; } catch { /* nieistotne */ }

  // --- rysowanie -------------------------------------------------------------

  function karta(tytul, dodatki) {
    const k = el("section", "karta");
    const h = el("h2");
    h.append(el("span", null, tytul), el("span", "rozpychacz"));
    if (dodatki) dodatki.forEach((d) => h.append(d));
    k.append(h);
    return k;
  }

  function rysujDzis(d) {
    const k = karta("Dziś");
    if (d.pierwszaLekcjaDzis) {
      const g = el("div", "duza", d.pierwszaLekcjaDzis.godzina);
      const p = el("div", "pod", `${d.pierwszaLekcjaDzis.przedmiot} · sala ${d.pierwszaLekcjaDzis.sala}`);
      k.append(g, p);
    } else if (d.pierwszaLekcjaNastepna) {
      k.append(el("div", "duza", d.pierwszaLekcjaNastepna.godzina),
               el("div", "pod", `${d.pierwszaLekcjaNastepna.dzien}: ${d.pierwszaLekcjaNastepna.przedmiot}`));
    } else {
      k.append(el("div", "pusto", "Brak lekcji."));
    }
    if (d.plan && d.plan.length) {
      const lista = el("div", "wiersze");
      lista.style.marginTop = "12px";
      for (const l of d.plan) {
        const w = el("div", "wiersz");
        const odwolana = l.zmiana === "odwołana";
        const glowny = el("div", "glowny");
        const tytul = el("span", odwolana ? "tytul odwolana-tekst" : "tytul", l.przedmiot);
        glowny.append(tytul);
        if (l.sala) glowny.append(el("small", null, ` · ${l.sala}`));
        w.append(el("span", "nr", String(l.nr)), el("span", "godz", l.od), glowny);
        if (l.zmiana) {
          w.append(el("span", `znacznik ${odwolana ? "odwolana" : "zmiana"}`, l.zmiana));
        }
        lista.append(w);
      }
      k.append(lista);
    }
    return k;
  }

  function rysujOceny(d) {
    const przycisk = el("button", "oko");
    const OKO = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" '
      + 'stroke-width="1.8" stroke-linecap="round" aria-hidden="true">'
      + '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z"/>'
      + '<circle cx="12" cy="12" r="2.6"/></svg>';
    const OKO_PRZEKRESLONE = OKO.replace("</svg>", '<path d="M4 20 20 4"/></svg>');
    const odswiezPrzycisk = () => {
      przycisk.innerHTML = (oceny_ukryte ? OKO : OKO_PRZEKRESLONE)
        + `<span>${oceny_ukryte ? "pokaż" : "ukryj"}</span>`;
      przycisk.title = oceny_ukryte ? "Pokaż oceny" : "Ukryj oceny";
      przycisk.setAttribute("aria-pressed", String(oceny_ukryte));
    };
    const k = karta("Oceny", [przycisk]);
    if (oceny_ukryte) k.classList.add("ukryte");
    odswiezPrzycisk();
    przycisk.addEventListener("click", () => {
      oceny_ukryte = !oceny_ukryte;
      k.classList.toggle("ukryte", oceny_ukryte);
      odswiezPrzycisk();
      try { localStorage.setItem("szkola_oceny_ukryte", oceny_ukryte ? "1" : "0"); } catch { /* nieistotne */ }
    });

    k.append(el("div", "duza srednia", lb(d.srednia)),
             el("div", "pod", "średnia ważona ze wszystkich ocen"));

    if (d.przedmioty && d.przedmioty.length) {
      const lista = el("div");
      lista.style.marginTop = "12px";
      for (const p of d.przedmioty) {
        const w = el("div", "przedmiot");
        w.append(el("span", "nazwa", p.przedmiot));
        const oceny = el("span", "oceny");
        for (const o of (p.oceny || [])) {
          const bez = o.wartosc == null && !/^[1-6][+-]?$/.test(String(o.ocena).trim());
          const sp = el("span", bez ? "ocena bezwartosci" : "ocena", o.ocena);
          if (o.waga != null) sp.title = `waga ${o.waga}`;
          oceny.append(sp);
        }
        w.append(oceny, el("span", "sr", lb(p.srednia)));
        lista.append(w);
      }
      k.append(lista);
    } else {
      k.append(el("div", "pusto", "Brak ocen."));
    }
    return k;
  }

  function rysujListe(tytul, pozycje, pusteTekst, rysujWiersz) {
    const k = karta(tytul);
    if (!pozycje || !pozycje.length) {
      k.append(el("div", "pusto", pusteTekst));
      return k;
    }
    const lista = el("div", "wiersze");
    pozycje.forEach((p) => lista.append(rysujWiersz(p)));
    k.append(lista);
    return k;
  }

  function wierszZadania(z) {
    const w = el("div", "wiersz");
    const glowny = el("div", "glowny");
    glowny.append(el("span", "tytul", z.przedmiot));
    if (z.opis) glowny.append(el("small", null, ` · ${z.opis}`));
    w.append(el("span", "godz", (z.data || "").slice(5)), glowny);
    if (z.rodzaj) w.append(el("span", "znacznik zmiana", z.rodzaj));
    return w;
  }

  function rysujFrekwencje(d) {
    const k = karta("Frekwencja");
    k.append(el("div", "duza", d.frekwencja != null ? `${lb(d.frekwencja, 1)}%` : "—"),
             el("div", "pod", "obecności w ostatnich 30 dniach"));
    const czeka = d.doUsprawiedliwienia || [];
    if (czeka.length) {
      const lista = el("div", "wiersze");
      lista.style.marginTop = "12px";
      for (const a of czeka) {
        const w = el("div", "wiersz");
        const glowny = el("div", "glowny");
        glowny.append(el("span", "tytul", a.przedmiot));
        glowny.append(el("small", null, ` · lekcja ${a.lekcja}`));
        w.append(el("span", "godz", (a.data || "").slice(5)), glowny,
                 el("span", `znacznik ${a.spoznienie ? "spoznienie" : "odwolana"}`, a.rodzaj));
        lista.append(w);
      }
      k.append(el("div", "pod", `${czeka.length} do usprawiedliwienia`), lista);
    } else {
      const ok = el("div", "pod", "Nic nie czeka na usprawiedliwienie.");
      ok.style.marginTop = "10px";
      k.append(ok);
    }
    return k;
  }

  function rysujPoczte(d) {
    const k = karta("Poczta");
    k.append(el("div", "duza", String(d.nieprzeczytane ?? 0)),
             el("div", "pod", "nieprzeczytanych wiadomości"));
    if (d.wiadomosci && d.wiadomosci.length) {
      const lista = el("div", "wiersze");
      lista.style.marginTop = "12px";
      for (const m of d.wiadomosci) {
        const w = el("div", "wiersz");
        const glowny = el("div", "glowny");
        glowny.append(el("span", "tytul", m.temat));
        glowny.append(el("small", null, ` · ${m.od}`));
        w.append(glowny, el("span", "godz", m.kiedy || ""));
        lista.append(w);
      }
      k.append(lista);
    }
    return k;
  }

  function rysuj(d) {
    $("#uczen").textContent = d.uczen || "Szkoła";
    if (d.numerek != null) {
      const p = $("#numerek");
      p.hidden = false;
      p.querySelector("b").textContent = String(d.numerek);
    }
    $("#sync").textContent = d.synchronizacja ? `synchronizacja: ${d.synchronizacja}` : "";

    const s = $("#siatka");
    s.textContent = "";
    s.append(
      rysujDzis(d),
      rysujOceny(d),
      rysujListe("Sprawdziany", d.sprawdziany, "Brak zapowiedzianych sprawdzianów.", wierszZadania),
      rysujListe("Zadania", d.zadania, "Brak zadań.", wierszZadania),
      rysujFrekwencje(d),
      rysujPoczte(d),
    );
  }

  // --- tryb żywy -------------------------------------------------------------

  const params = new URLSearchParams(location.search);
  const prefix = params.get("prefix");

  function liczba(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : null;
  }

  function zStanow(stany, prefix) {
    const we = (nazwa) => stany[`${prefix}${nazwa}`];
    const atr = (nazwa, pole) => (we(nazwa)?.attributes || {})[pole];
    const godzina = (nazwa) => {
      const s = we(nazwa)?.state;
      if (!s || s === "unknown" || s === "unavailable") return null;
      const dt = new Date(s);
      return Number.isNaN(dt.getTime())
        ? null
        : dt.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    };

    const pierwszaDzis = godzina("pierwsza_lekcja_dzis");
    const pierwszaNast = godzina("pierwsza_lekcja_nastepnego_dnia_nauki");

    return {
      uczen: (we("oceny")?.attributes?.friendly_name || "").replace(/ Oceny$/, "") || "Szkoła",
      numerek: liczba(we("szczesliwy_numerek")?.state),
      synchronizacja: we("ostatnia_synchronizacja")?.state
        ? new Date(we("ostatnia_synchronizacja").state).toLocaleTimeString("pl-PL",
            { hour: "2-digit", minute: "2-digit" })
        : null,
      pierwszaLekcjaDzis: pierwszaDzis
        ? { godzina: pierwszaDzis, przedmiot: atr("pierwsza_lekcja_dzis", "przedmiot") || "",
            sala: atr("pierwsza_lekcja_dzis", "sala") || "" }
        : null,
      pierwszaLekcjaNastepna: pierwszaNast
        ? { dzien: "następny dzień nauki", godzina: pierwszaNast,
            przedmiot: atr("pierwsza_lekcja_nastepnego_dnia_nauki", "przedmiot") || "" }
        : null,
      plan: [],  // pełny plan dnia bierz z karty kalendarza HA — patrz README
      sprawdziany: (atr("najblizszy_sprawdzian", "wszystkie") || []).map((t) => {
        const m = String(t).match(/^(\S+)\s+(.*?)\s*(?:\((.*)\))?$/);
        return m ? { data: m[1], przedmiot: m[2], rodzaj: m[3] || "" } : { data: "", przedmiot: String(t) };
      }),
      zadania: [],
      srednia: liczba(we("oceny")?.state),
      przedmioty: (atr("oceny", "przedmioty") || []).map((p) => ({
        przedmiot: p.przedmiot, srednia: p.srednia,
        oceny: (p.oceny || []).map((o) => ({ ocena: o.ocena, waga: o.waga, wartosc: o.wartosc })),
      })),
      frekwencja: atr("do_usprawiedliwienia", "frekwencja_procent"),
      doUsprawiedliwienia: (atr("do_usprawiedliwienia", "do_usprawiedliwienia") || []).map((a) => ({
        data: a.data, lekcja: a.lekcja, przedmiot: a.przedmiot,
        rodzaj: a.rodzaj, spoznienie: a.spoznienie,
      })),
      nieprzeczytane: liczba(we("nieprzeczytane_wiadomosci")?.state) ?? 0,
      wiadomosci: (atr("nieprzeczytane_wiadomosci", "ostatnie") || []).map((t) => {
        const m = String(t).match(/^(\S+\s+\S+)\s+(.*?):\s*(.*)$/);
        return m ? { kiedy: m[1], od: m[2], temat: m[3] } : { kiedy: "", od: "", temat: String(t) };
      }),
      uwagi: { pozytywne: atr("uwagi", "pozytywne"), negatywne: atr("uwagi", "negatywne") },
    };
  }

  function pokazBanner(tekst) {
    const b = $("#banner");
    b.hidden = false;
    b.textContent = tekst;
  }

  async function zywy() {
    let token = null;
    try { token = localStorage.getItem("szkola_token"); } catch { /* brak dostępu */ }
    if (!token) {
      token = window.prompt(
        "Wklej długoterminowy token Home Assistanta.\n" +
        "Tworzysz go w HA: profil (na dole menu) → Bezpieczeństwo → Długoterminowe tokeny dostępu.\n" +
        "Token zostaje tylko w tej przeglądarce.");
      if (!token) throw new Error("bez tokenu nie da się pobrać danych");
      try { localStorage.setItem("szkola_token", token.trim()); } catch { /* nieistotne */ }
      token = token.trim();
    }
    const odp = await fetch(`${location.origin}/api/states`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (odp.status === 401) {
      try { localStorage.removeItem("szkola_token"); } catch { /* nieistotne */ }
      throw new Error("token odrzucony — odśwież stronę i wklej nowy");
    }
    if (!odp.ok) throw new Error(`Home Assistant odpowiedział ${odp.status}`);
    const lista = await odp.json();
    const stany = Object.fromEntries(lista.map((s) => [s.entity_id, s]));
    return zStanow(stany, prefix.endsWith("_") ? prefix : `${prefix}_`);
  }

  // --- start -----------------------------------------------------------------

  if (prefix) {
    $("#tryb").textContent = "Dane na żywo z Home Assistanta.";
    zywy()
      .then((d) => { rysuj(d); setInterval(() => zywy().then(rysuj).catch(() => {}), 120000); })
      .catch((err) => {
        pokazBanner(`Nie udało się pobrać danych: ${err.message}. Pokazuję dane pokazowe.`);
        $("#tryb").textContent = "Dane pokazowe.";
        rysuj(window.DANE_DEMO);
      });
  } else {
    $("#tryb").textContent = "Dane pokazowe — zmyślone, nie z dziennika.";
    pokazBanner("To są dane pokazowe. Jak podłączyć własne — patrz README obok tego pliku.");
    rysuj(window.DANE_DEMO);
  }
})();
