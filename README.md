# vulcan — eduVULCAN dla Home Assistant

Nieoficjalny klient API mobilnego eduVULCAN (to samo API, którego używa aplikacja eduVULCAN) oraz — w przygotowaniu — integracja Home Assistant: plan lekcji z zastępstwami, sprawdziany, zadania, oceny, uwagi, frekwencja, wiadomości, a przy usłudze rozszerzonej także wysyłanie wiadomości i usprawiedliwień.

> **Uwaga.** To nie jest oprogramowanie firmy VULCAN. Korzystanie z nieoficjalnego klienta może naruszać regulamin eduVULCAN i skończyć się blokadą konta. Używasz na własne ryzyko.

## Stan

| Część | Stan |
|---|---|
| Klient (`vulcan_client`): rejestracja urządzenia, podpisywanie, odczyty | gotowy, testy jednostkowe |
| Zapisy: wiadomość, usprawiedliwienie lekcji | gotowe w kodzie, niesprawdzone na żywo |
| CLI `vulcan` | gotowe |
| Integracja HA (`custom_components/`) | następny etap |

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

# 4. Zapisy — domyślnie tylko podgląd, wysyłka dopiero z --send
vulcan send-message --pupil 0 --to "Kowalska" --subject "Temat" --body "Treść"
vulcan justify --pupil 0 --day 2026-10-12 --reason "Choroba"
```

## Rozwój

```bash
pip install -e ".[dev]"
pytest -q
pre-commit install   # gitleaks przed każdym commitem
```

Zasady:
- w repo tylko dane syntetyczne; żadnych prawdziwych odpowiedzi API, imion, tokenów, kluczy,
- zmiany przez PR na gałęzi; `main` zawsze zielony.

## Podziękowania i licencja

Licencja: **AGPL-3.0**. Schemat podpisu i endpointy odczytu przeniesione z [iris](https://github.com/bbrjpl1310b/iris) (AGPL-3.0). Kształt zapisów na podstawie [eduvulcan-clone](https://github.com/przemeklagod/eduvulcan-clone), [Vulcanova.Uonet](https://github.com/dolczykk/Vulcanova.Uonet) i [DzienniczekSzpontniczek](https://github.com/szponciciel04/DzienniczekSzpontniczek). Inspiracja integracją HA: [Vultron](https://github.com/htomasz/vultron), [vulcan-notify](https://github.com/kintecus/vulcan-notify).
