# vulcan — eduVULCAN dla Home Assistant

Nieoficjalny klient API mobilnego eduVULCAN (to samo API, którego używa aplikacja eduVULCAN) oraz — w przygotowaniu — integracja Home Assistant: plan lekcji z zastępstwami, sprawdziany, zadania, oceny, uwagi, frekwencja, wiadomości, a przy usłudze rozszerzonej także wysyłanie wiadomości i usprawiedliwień.

> **Uwaga.** To nie jest oprogramowanie firmy VULCAN. Korzystanie z nieoficjalnego klienta może naruszać regulamin eduVULCAN i skończyć się blokadą konta. Używasz na własne ryzyko.

## Stan

| Część | Stan |
|---|---|
| Klient (`vulcan_client`): rejestracja urządzenia, podpisywanie, odczyty, stronicowanie | gotowy, testy jednostkowe |
| Zapisy: wiadomość, usprawiedliwienie lekcji | gotowe w kodzie, **niesprawdzone na żywo** |
| CLI `vulcan` (w tym `schema` — kształt odpowiedzi bez treści) | gotowe |
| Integracja HA (`custom_components/vulcan_dom`) | kod i testy integracji gotowe, **nieuruchomiona w HA** |

## Jak to działa

1. Logujesz się raz na eduvulcan.pl. Strona `https://eduvulcan.pl/api/ap` zawiera tokeny JWT uczniów.
2. Klient generuje własną parę kluczy RSA i rejestruje się tymi tokenami jako kolejne urządzenie (`mobile/register/jwt`).
3. Każde następne żądanie jest podpisane kluczem urządzenia — bez hasła, bez przeglądarki, bez sesji do odnawiania.

Klucz prywatny urządzenia trzymasz u siebie (`~/.config/vulcan/credential.json`, prawa 0600). **Nie commituj go** — `.gitignore` i gitleaks w CI pilnują tego, ale to Twój sekret.

## CLI

```bash
pip install -e ".[dev]"

# 1. Rejestracja (tokeny nie trafiają na ekran ani do historii powłoki):
#    zaloguj się na https://eduvulcan.pl, otwórz https://eduvulcan.pl/api/ap,
#    w konsoli przeglądarki: copy(document.querySelector('#ap').value)
pbpaste | vulcan register -          # macOS; na Linuksie: xclip -o | vulcan register -

# 2. Kto jest na koncie i jakie ma uprawnienia
vulcan accounts

# 3. Surowe dane (JSON)
vulcan fetch schedule --pupil 0 --back 0 --ahead 7
vulcan fetch exams --pupil 0
vulcan fetch messages --pupil 0

# 3a. Sam kształt odpowiedzi — pola, typy, maski dat, bez ani jednej treści.
#     Do zgłaszania błędów i do sprawdzania, co serwer naprawdę przysyła.
vulcan schema schedule --pupil 0 --back 0 --ahead 7
vulcan schema lessons --pupil 0 --back 7 --ahead 0

# 3b. Rozkład wartości JEDNEJ, wskazanej ścieżki (to już pokazuje treść — świadomie):
vulcan schema lessons --pupil 0 --values '[].PresenceType.Name'

# 4. Zapisy — domyślnie tylko podgląd, wysyłka dopiero z --send
vulcan send-message --pupil 0 --to "Kowalska" --subject "Temat" --body "Treść"
vulcan justify --pupil 0 --day 2026-10-12 --reason "Choroba"
```

## Rozwój

```bash
# sam klient i CLI (bez Home Assistanta)
pip install -e ".[dev]"
pytest --noconftest tests/test_client.py -q

# z integracją HA (ciągnie homeassistant + harness testowy, ~1 GB)
pip install -e ".[dev,ha]"
pytest -q

pre-commit install   # gitleaks przed każdym commitem
```

Na macOS instalacja harnessu potrafi się wywrócić na `PyRIC` — wtedy:
`pip install --no-build-isolation pyric` i powtórz instalację.

CI ma trzy joby: `sekrety` (gitleaks), `klient` (dowodzi, że klient działa bez HA)
i `integracja` (pełny zestaw na pytest-homeassistant-custom-component).

Zasady:
- w repo tylko dane syntetyczne; żadnych prawdziwych odpowiedzi API, imion, tokenów, kluczy,
- zmiany przez PR na gałęzi; `main` zawsze zielony.

## Podziękowania i licencja

Licencja: **AGPL-3.0**. Schemat podpisu i endpointy odczytu przeniesione z [iris](https://github.com/bbrjpl1310b/iris) (AGPL-3.0). Kształt zapisów na podstawie [eduvulcan-clone](https://github.com/przemeklagod/eduvulcan-clone), [Vulcanova.Uonet](https://github.com/dolczykk/Vulcanova.Uonet) i [DzienniczekSzpontniczek](https://github.com/szponciciel04/DzienniczekSzpontniczek). Inspiracja integracją HA: [Vultron](https://github.com/htomasz/vultron), [vulcan-notify](https://github.com/kintecus/vulcan-notify).

## Integracja Home Assistant

Instalacja: HACS → trzy kropki → *Custom repositories* → `https://github.com/dampud/vulcan`, typ *Integration*. Potem *Dodaj integrację → eduVULCAN* i wklejenie zawartości `https://eduvulcan.pl/api/ap` (HA rejestruje się jako osobne urządzenie; wklejka nigdzie nie jest zapisywana).

Co powstaje — dla każdego ucznia osobne urządzenie, a na nim:

- sensory: pierwsza lekcja dziś / jutro / następnego dnia nauki, najbliższy sprawdzian, sprawdziany w 7 dni, zmiany w planie, ostatnia ocena, nieprzeczytane wiadomości, uwagi, szczęśliwy numerek, ostatnia synchronizacja,
- kalendarze: plan lekcji (z zastępstwami i odwołaniami) oraz sprawdziany i zadania,
- zdarzenie `vulcan_dom_event` przy każdej nowości: `new_grade`, `new_note`, `new_message`, `new_exam`, `new_homework`, `schedule_change`. Pierwsze pobranie buduje stan bazowy i nie wysyła zdarzeń,
- usługi: `vulcan_dom.recipients`, `vulcan_dom.send_message`, `vulcan_dom.justify_absence`, `vulcan_dom.refresh`.

Opcje (koło zębate przy integracji): częstotliwość odpytywania, cisza nocna, dobowy limit zapisów.

> Zdarzenie `vulcan_dom_event` niesie fragmenty treści wiadomości i uwag. Jeśli nie chcesz ich w bazie recordera, wyklucz je w `configuration.yaml`:
> ```yaml
> recorder:
>   exclude:
>     event_types:
>       - vulcan_dom_event
> ```

Wysyłka wiadomości i usprawiedliwień działa natychmiast i nie da się jej cofnąć — w automatyzacjach wołaj te usługi wyłącznie po potwierdzeniu (np. `notify` z akcją na telefonie).
