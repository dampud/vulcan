# eduVULCAN dla Home Assistant

Nieoficjalna integracja, która wciąga dziennik eduVULCAN do Home Assistanta: plan lekcji z zastępstwami, sprawdziany, zadania domowe, oceny ze średnimi, frekwencję, uwagi, wiadomości i szczęśliwy numerek. Przy koncie z usługą rozszerzoną pozwala też wysłać wiadomość i usprawiedliwić nieobecność.

Dzięki temu możesz na przykład ustawić budzik według pierwszej lekcji następnego dnia, dostać powiadomienie o zastępstwie albo zobaczyć na tablecie w kuchni, co dziecko ma jutro w szkole.

> **To nie jest oprogramowanie firmy VULCAN.** Korzystanie z nieoficjalnego klienta może naruszać regulamin eduVULCAN i w skrajnym przypadku skończyć się blokadą konta. Używasz na własne ryzyko.

---

## Zanim zaczniesz

Potrzebujesz trzech rzeczy:

1. **Konta rodzica w eduVULCAN** — tego samego, którym logujesz się na `eduvulcan.pl`.
2. **Działającego Home Assistanta** w wersji 2025.12 lub nowszej.
3. **HACS** — dodatku do Home Assistanta, który instaluje integracje spoza oficjalnej listy. Jeśli go nie masz, instrukcja jest na [hacs.xyz](https://hacs.xyz/docs/use/download/download/).

Całość zajmuje około 10 minut. Nie musisz nic programować, ale raz będziesz musiał skopiować długi tekst ze strony eduVULCAN — pokazuję niżej dokładnie jak.

---

## Krok 1: zainstaluj integrację przez HACS

1. W Home Assistancie otwórz **HACS** (w menu po lewej).
2. Kliknij **trzy kropki** w prawym górnym rogu → **Custom repositories** (Własne repozytoria).
3. W polu *Repository* wklej: `https://github.com/dampud/vulcan`
4. W polu *Type* wybierz **Integration**.
5. Kliknij **Add** (Dodaj), a potem zamknij okienko.
6. Na liście HACS znajdź **eduVULCAN (nieoficjalna)** i kliknij **Download** (Pobierz).
7. **Zrestartuj Home Assistanta**: Ustawienia → System → prawy górny róg → Uruchom ponownie.

Restart jest konieczny — bez niego Home Assistant nie zobaczy nowej integracji.

---

## Krok 2: pobierz dane logowania z eduVULCAN

Integracja nie prosi o Twoje hasło. Zamiast tego rejestruje się w eduVULCAN jako kolejne „urządzenie" — tak samo jak robi to aplikacja na telefonie. Żeby to zrobić, musi raz dostać specjalny tekst ze strony eduVULCAN.

Na komputerze (nie na telefonie — będzie potrzebna konsola przeglądarki):

1. Zaloguj się na **https://eduvulcan.pl** swoim kontem rodzica.
2. W tej samej karcie przeglądarki wejdź na **https://eduvulcan.pl/api/ap**  
   Zobaczysz stronę z długim ciągiem znaków. To jest to, czego potrzebujemy.
3. Naciśnij **F12** (na Macu: `Cmd` + `Option` + `I`). Otworzy się panel dla programistów.
4. Przejdź na zakładkę **Console** (Konsola).
5. Wklej tam dokładnie to i naciśnij Enter:

   ```
   copy(document.querySelector('#ap').value)
   ```

6. Gotowe — potrzebny tekst jest teraz w schowku. Konsolę możesz zamknąć.

> Jeśli zobaczysz komunikat, że wklejanie jest zablokowane, przeglądarka poprosi Cię o wpisanie słowa `allow pasting` (Chrome) albo `pozwól na wklejanie`. Wpisz je, naciśnij Enter i wklej polecenie ponownie.

Jeśli krok 5 nic nie skopiował, zaznacz całą zawartość strony myszką (`Ctrl`/`Cmd` + `A`) i skopiuj ją zwykłym `Ctrl`/`Cmd` + `C`.

> **Od tej chwili aż do końca kroku 3 nie kopiuj niczego innego.** Każde kolejne kopiowanie nadpisze schowek i trzeba będzie wrócić tutaj.

---

## Krok 3: dodaj integrację w Home Assistancie

1. Ustawienia → **Urządzenia i usługi**.
2. Prawy dolny róg: **Dodaj integrację**.
3. Wpisz **eduVULCAN** i wybierz z listy.
4. W jedyne pole formularza **wklej tekst ze schowka** (`Ctrl`/`Cmd` + `V`) i zatwierdź.

Po chwili zobaczysz nowe urządzenie — jedno na każde dziecko na koncie, podpisane jego imieniem i nazwiskiem.

Wklejony tekst nie jest nigdzie zapisywany. Home Assistant wymienia go na własny klucz urządzenia i od tej pory posługuje się wyłącznie nim.

---

## Co dostajesz

**Dla każdego dziecka osobne urządzenie**, a na nim:

| Encja | Co pokazuje |
|---|---|
| Pierwsza lekcja dziś / jutro / następnego dnia nauki | Godzinę rozpoczęcia, a w szczegółach przedmiot, salę i nauczyciela |
| Najbliższy sprawdzian | Datę, a w szczegółach przedmiot, rodzaj i listę kolejnych |
| Sprawdziany w 7 dni | Ile sprawdzianów w najbliższym tygodniu |
| Zmiany w planie (7 dni) | Liczbę zastępstw i odwołanych lekcji, z opisem w szczegółach |
| Oceny | Średnią ważoną, a w szczegółach średnie i oceny osobno dla każdego przedmiotu |
| Ostatnia ocena | Najświeższą ocenę z przedmiotem i wagą |
| Do usprawiedliwienia | Ile nieobecności i spóźnień czeka na usprawiedliwienie |
| Nieprzeczytane wiadomości | Licznik, a w szczegółach nadawcy i tematy |
| Uwagi | Liczbę uwag i pochwał |
| Szczęśliwy numerek | Dzisiejszy numerek, jeśli szkoła go losuje |
| Ostatnia synchronizacja | Kiedy integracja ostatnio pytała serwer |

**Dwa kalendarze**: plan lekcji (z zastępstwami i odwołaniami) oraz sprawdziany i zadania. Możesz je pokazać w standardowej karcie kalendarza.

**Zdarzenia** — przy każdej nowości integracja wysyła w Home Assistancie zdarzenie `vulcan_dom_event`. Na nim buduje się powiadomienia: nowa ocena, nowa uwaga, nowa wiadomość, nowy sprawdzian, nowe zadanie, zmiana w planie, nieobecność do usprawiedliwienia. Pierwsze pobranie danych niczego nie wysyła, więc po instalacji nie dostaniesz lawiny powiadomień o całej historii.

**Usługi** (Narzędzia deweloperskie → Akcje):

- `vulcan_dom.read_messages` — pokazuje treść wiadomości ze skrzynki.
- `vulcan_dom.send_message` — wysyła wiadomość (wymaga usługi rozszerzonej).
- `vulcan_dom.justify_absence` — usprawiedliwia nieobecność (wymaga usługi rozszerzonej).
- `vulcan_dom.recipients` — listę osób, do których można napisać.
- `vulcan_dom.refresh` — pobiera dane natychmiast, nie czekając na kolejne odpytanie.

> **Uwaga.** Wysłanie wiadomości i usprawiedliwienie działają od razu w prawdziwym dzienniku i nie da się ich cofnąć. W automatyzacjach wołaj je wyłącznie po potwierdzeniu — na przykład powiadomieniem z przyciskiem na telefonie.

---

## Gotowy pulpit „Szkoła"

W katalogu [`przyklady/dashboard-szkola/`](przyklady/dashboard-szkola/) leży gotowa strona pokazująca wszystko naraz: plan dnia z zastępstwami, oceny ze średnimi i przyciskiem ukrywania, sprawdziany, zadania, frekwencję i pocztę. Jasny i ciemny motyw, działa na telefonie i na tablecie.

Pobierz ten katalog i otwórz `index.html` — zobaczysz pulpit wypełniony danymi pokazowymi, bez łączenia się z czymkolwiek. Jeśli układ ci odpowiada, skopiuj pliki do `config/www/szkola/` i otwórz pod adresem `/local/szkola/index.html?prefix=sensor.imie_nazwisko`. Instrukcja krok po kroku, razem z dodaniem pulpitu jako zakładki w Home Assistancie, jest w [README tego katalogu](przyklady/dashboard-szkola/README.md).

---

## Ustawienia

Ustawienia → Urządzenia i usługi → przy eduVULCAN kliknij **Konfiguruj**:

- **Odpytywanie co (min)** — jak często integracja pyta serwer o nowości. Domyślnie 30 minut. Częściej niż co 15 minut nie ma sensu i niepotrzebnie obciąża szkolny serwer.
- **Cisza nocna od / do godziny** — w tych godzinach integracja nie pyta serwera w ogóle. Wpisujesz pełną godzinę doby: `22` znaczy 22:00, `6` znaczy 6:00. Ustawienie obu pól na tę samą wartość wyłącza ciszę nocną.
- **Limit wysyłek na dobę** — ile najwyżej wiadomości i usprawiedliwień można wysłać w ciągu doby. Bezpiecznik na wypadek błędu w automatyzacji.

---

## Prywatność

- Hasło do eduVULCAN nigdzie nie jest zapisywane — integracja go nie zna.
- Klucz urządzenia zostaje w Home Assistancie; przy korzystaniu z CLI leży w `~/.config/vulcan/credential.json` z prawami tylko dla właściciela.
- Treść wiadomości jest dostępna przez usługę `read_messages`, a nie jako atrybut encji — dzięki temu korespondencja ze szkołą nie odkłada się w bazie historii Home Assistanta.
- Zdarzenie `vulcan_dom_event` niesie fragmenty treści wiadomości i uwag. Jeśli nie chcesz ich w bazie, dopisz w `configuration.yaml`:

  ```yaml
  recorder:
    exclude:
      event_types:
        - vulcan_dom_event
  ```

---

## Kiedy coś nie działa

**Nie widzę integracji po dodaniu w HACS.** Nie było restartu Home Assistanta albo restart się nie udał. Zrestartuj i spróbuj ponownie.

**„To nie są poprawne dane z eduvulcan.pl/api/ap".** Skopiowany tekst jest niepełny albo pochodzi z niezalogowanej sesji. Zaloguj się ponownie na eduvulcan.pl i powtórz krok 2. Zdarza się też, że na koncie nie są zaakceptowane wymagane zgody — sprawdź to w ustawieniach eduVULCAN.

**Encje pokazują „niedostępne".** Zajrzyj do sensora *Ostatnia synchronizacja* — w jego szczegółach jest informacja, czy ostatnia próba się powiodła i co poszło nie tak.

**Home Assistant prosi o ponowne dodanie danych.** eduVULCAN unieważnił klucz urządzenia, na przykład po zmianie hasła. Powtórz krok 2 i wklej świeży tekst.

**Wysyłka wiadomości nie działa.** Ta funkcja wymaga na koncie usługi rozszerzonej (płatnej). Bez niej odczyt działa normalnie, a zapis zwraca błąd.

---

## Wersje

Wydania są numerowane według [semantycznego wersjonowania](https://semver.org/lang/pl/): `X.Y.Z`. Numer w `manifest.json`, w `pyproject.toml` i w tagu git jest ten sam — pilnuje tego osobny krok w CI. Aktualizacje pojawiają się w HACS jako zwykłe wersje.

---

## Dla programistów

Klient API (`vulcan_client`) działa samodzielnie, bez Home Assistanta, i ma własne CLI.

```bash
pip install -e ".[dev]"
```

**Rejestracja.** Token idzie przez schowek, żeby nie trafił na ekran ani do historii powłoki. Kolejność jest tu istotna: polecenie przygotowujesz *przed* skopiowaniem tokenu, bo skopiowanie samego polecenia nadpisałoby schowek.

1. W terminalu wpisz poniższe polecenie, ale **nie naciskaj jeszcze Enter**:

   ```bash
   pbpaste | vulcan register -          # macOS; na Linuksie: xclip -o | vulcan register -
   ```

2. Przejdź do przeglądarki zalogowanej na eduvulcan.pl, otwórz `https://eduvulcan.pl/api/ap`, w konsoli (F12 → Console) wykonaj:

   ```js
   copy(document.querySelector('#ap').value)
   ```

3. Wróć do terminala i dopiero teraz naciśnij **Enter**.

Jeśli wolisz nie żonglować oknami, uruchom `vulcan register -` bez potoku i wklej token wprost do terminala, kończąc `Enter` i `Ctrl` + `D`. Token będzie wtedy widoczny na ekranie.

```bash
vulcan accounts                       # kto jest na koncie i jakie ma uprawnienia
vulcan fetch schedule --pupil 0 --back 0 --ahead 7
vulcan fetch exams --pupil 0

# Sam kształt odpowiedzi — pola, typy, maski dat, bez ani jednej treści
vulcan schema schedule --pupil 0 --back 0 --ahead 7
vulcan schema lessons --pupil 0 --back 7 --ahead 0

# Rozkład wartości jednej wskazanej ścieżki (to już pokazuje treść — świadomie)
vulcan schema lessons --pupil 0 --values '[].PresenceType.Name'

# Konkretne dni zamiast liczenia od dziś (działa też w fetch, parse, fixture)
vulcan schema lessons --pupil 0 --from 2026-10-05 --to 2026-10-06

# Ile z tych rekordów rozpoznaje parser integracji — bez restartu Home Assistanta
vulcan parse lessons --pupil 0 --from 2026-10-05 --to 2026-10-06
vulcan parse lessons --pupil 0 --back 14 --ahead 0 --pola

# Zamaskowane rekordy do testów regresji (nazwiska, oceny i uwagi nie wychodzą)
vulcan fixture lessons --pupil 0 --back 14 --ahead 0 --limit 20 > /tmp/lessons.json

# Zapisy — domyślnie podgląd, wysyłka dopiero z --send
vulcan send-message --pupil 0 --to "Kowalska" --subject "Temat" --body "Treść"
vulcan justify --pupil 0 --day 2026-10-12 --reason "Choroba"
```

### Jak to działa pod spodem

1. Strona `https://eduvulcan.pl/api/ap` zawiera tokeny JWT uczniów zalogowanego konta.
2. Klient generuje własną parę kluczy RSA i rejestruje się tymi tokenami jako kolejne urządzenie (`mobile/register/jwt`).
3. Każde następne żądanie jest podpisane kluczem urządzenia — bez hasła, bez przeglądarki, bez sesji do odnawiania.

### Testy

```bash
pytest --noconftest tests/test_client.py -q   # sam klient, bez HA
pip install -e ".[dev,ha]" && pytest -q       # z integracją (~1 GB zależności)
pre-commit install                            # gitleaks przed każdym commitem
```

Na macOS instalacja harnessu testowego potrafi się wywrócić na `PyRIC`; wtedy `pip install --no-build-isolation pyric` i powtórz instalację.

CI ma cztery kroki: `sekrety` (gitleaks), `wersja` (spójność numerów), `klient` (dowodzi, że klient działa bez HA) i `integracja` (pełny zestaw testów).

Zasady: w repo wyłącznie dane syntetyczne — żadnych prawdziwych odpowiedzi API, imion, tokenów ani kluczy. Zmiany przez PR na gałęzi, `main` zawsze zielony.

---

## Podziękowania i licencja

Licencja: **AGPL-3.0**.

Schemat podpisu i endpointy odczytu przeniesione z [iris](https://github.com/bbrjpl1310b/iris) (AGPL-3.0). Kształt zapisów na podstawie [eduvulcan-clone](https://github.com/przemeklagod/eduvulcan-clone), [Vulcanova.Uonet](https://github.com/dolczykk/Vulcanova.Uonet) i [DzienniczekSzpontniczek](https://github.com/szponciciel04/DzienniczekSzpontniczek). Inspiracja integracją HA: [Vultron](https://github.com/htomasz/vultron), [vulcan-notify](https://github.com/kintecus/vulcan-notify).
