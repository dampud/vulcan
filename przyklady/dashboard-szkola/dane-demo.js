// Dane pokazowe — zmyślone dziecko, zmyślona szkoła, zmyśleni nauczyciele.
// Kształt pól jest taki sam jak w encjach integracji, więc strona wygląda
// dokładnie tak, jak będzie wyglądać na prawdziwych danych.
window.DANE_DEMO = {
  uczen: "Ola Przykładowa",
  numerek: 17,
  synchronizacja: "przed chwilą",
  pierwszaLekcjaDzis: { godzina: "08:00", przedmiot: "Matematyka", sala: "12", nauczyciel: "Jan Kowalski" },
  pierwszaLekcjaNastepna: { dzien: "jutro", godzina: "08:55", przedmiot: "Biologia", sala: "7", nauczyciel: "Ewa Nowak" },
  plan: [
    { nr: 1, od: "08:00", przedmiot: "Matematyka", sala: "12", zmiana: null },
    { nr: 2, od: "08:55", przedmiot: "Chemia", sala: "21", zmiana: "zastępstwo za Biologię" },
    { nr: 3, od: "09:50", przedmiot: "Historia", sala: "3", zmiana: "odwołana" },
    { nr: 4, od: "10:45", przedmiot: "Język polski", sala: "1", zmiana: null },
    { nr: 5, od: "11:40", przedmiot: "WF", sala: "sala gimn.", zmiana: null },
  ],
  sprawdziany: [
    { data: "2026-10-15", przedmiot: "Matematyka", rodzaj: "sprawdzian", opis: "Funkcje liniowe" },
    { data: "2026-10-17", przedmiot: "Historia", rodzaj: "kartkówka", opis: "Dwudziestolecie" },
  ],
  zadania: [
    { data: "2026-10-14", przedmiot: "Język polski", opis: "Wypracowanie, 200 słów" },
    { data: "2026-10-16", przedmiot: "Chemia", opis: "Zadania 4–7 ze strony 58" },
  ],
  srednia: 4.21,
  przedmioty: [
    { przedmiot: "Biologia", srednia: 4.5, oceny: [{ ocena: "5", waga: 1 }, { ocena: "4", waga: 2 }] },
    { przedmiot: "Chemia", srednia: 3.75, oceny: [{ ocena: "3+", waga: 2 }, { ocena: "4", waga: 1 }] },
    { przedmiot: "Historia", srednia: 5.0, oceny: [{ ocena: "5", waga: 3 }] },
    { przedmiot: "Język polski", srednia: 4.0, oceny: [{ ocena: "4", waga: 1 }, { ocena: "4", waga: 2 }] },
    { przedmiot: "Matematyka", srednia: 3.9, oceny: [{ ocena: "4", waga: 3 }, { ocena: "3+", waga: 2 }, { ocena: "np", waga: 0 }] },
  ],
  frekwencja: 96.4,
  doUsprawiedliwienia: [
    { data: "2026-10-09", lekcja: 1, przedmiot: "Matematyka", rodzaj: "Nieobecność", spoznienie: false },
    { data: "2026-10-10", lekcja: 3, przedmiot: "Historia", rodzaj: "Spóźnienie", spoznienie: true },
  ],
  nieprzeczytane: 2,
  wiadomosci: [
    { od: "Anna Wychowawczyni", temat: "Zebranie 21.10", kiedy: "wczoraj" },
    { od: "Sekretariat", temat: "Ubezpieczenie — przypomnienie", kiedy: "3 dni temu" },
  ],
  uwagi: { pozytywne: 2, negatywne: 0 },
};
