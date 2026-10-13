# Pulpit „Szkoła"

Gotowa strona pokazująca dane z integracji: plan dnia z zastępstwami, oceny ze średnimi (z przyciskiem ukrywania), sprawdziany, zadania, frekwencję i pocztę. Działa na telefonie, tablecie i komputerze, ma motyw jasny i ciemny.

Strona nie jest częścią integracji — to przykład do skopiowania i przerobienia po swojemu.

## Zobacz, zanim cokolwiek wgrasz

Pobierz ten katalog i otwórz `index.html` w przeglądarce, zwykłym podwójnym kliknięciem. Zobaczysz pulpit wypełniony danymi pokazowymi: zmyślone dziecko, zmyślona szkoła, zmyśleni nauczyciele. Nic się nigdzie nie łączy.

Tak wygląda sam układ — jeśli ci odpowiada, przejdź dalej.

## Podłączenie własnych danych

### Krok 1: skopiuj pliki do Home Assistanta

Trzy pliki — `index.html`, `styl.css`, `dashboard.js` — wgraj do katalogu `config/www/szkola/`. Katalog `www` zwykle trzeba utworzyć samemu; w Home Assistancie najłatwiej dodatkiem **File editor** albo przez **Samba share**.

Plik `dane-demo.js` też skopiuj — strona go wczytuje i bez niego pokaże pustkę, gdyby pobieranie danych się nie udało.

Po wgraniu strona jest pod adresem:

```
https://TWÓJ-ADRES-HA/local/szkola/index.html
```

`config/www/` jest widoczne pod `/local/`, bez logowania. Pamiętaj o tym: **każdy, kto zna adres, otworzy tę stronę**. Same dane dziennika są chronione tokenem (patrz niżej), ale sam układ strony jest publiczny.

### Krok 2: ustal nazwę swoich encji

Integracja nazywa encje od imienia i nazwiska dziecka. Wejdź w **Narzędzia deweloperskie → Stany** i wpisz `oceny` — znajdziesz coś w rodzaju:

```
sensor.jan_kowalski_oceny
```

Twój przedrostek to wszystko przed `_oceny`, czyli `sensor.jan_kowalski`.

### Krok 3: otwórz stronę z przedrostkiem

```
https://TWÓJ-ADRES-HA/local/szkola/index.html?prefix=sensor.jan_kowalski
```

Przy pierwszym otwarciu strona poprosi o **długoterminowy token**. Tworzysz go w Home Assistancie: kliknij swoje inicjały na dole menu po lewej → zakładka **Bezpieczeństwo** → na samym dole **Długoterminowe tokeny dostępu** → **Utwórz token**. Skopiuj go i wklej w okienku.

Token zostaje wyłącznie w tej przeglądarce (w `localStorage`) i nie jest nigdzie wysyłany poza twój Home Assistant. Jeśli korzystasz ze wspólnego komputera albo tablet wisi w miejscu dostępnym dla gości, miej świadomość, że token daje pełny dostęp do twojego HA — rozważ wtedy osobne konto w HA z ograniczeniami i token wystawiony na nie.

Dane odświeżają się co dwie minuty.

### Krok 4 (opcjonalnie): dodaj jako zakładkę w Home Assistancie

Żeby pulpit był w menu obok innych widoków:

1. Otwórz dowolny pulpit → prawy górny róg → **Edytuj pulpit**.
2. Trzy kropki → **Nieprzetworzony edytor konfiguracji**.
3. Dopisz nowy widok:

```yaml
views:
  - title: Szkoła
    path: szkola
    panel: true
    cards:
      - type: iframe
        url: /local/szkola/index.html?prefix=sensor.jan_kowalski
        aspect_ratio: 100%
```

`panel: true` sprawia, że strona zajmuje całą szerokość.

## Gdy coś nie działa

**Widzę dane pokazowe mimo podania `?prefix=`.** U góry strony pojawi się pasek z powodem. Najczęściej: zły przedrostek (sprawdź w Narzędziach deweloperskich) albo odrzucony token.

**„Token odrzucony".** Token został usunięty w HA albo wklejony z literówką. Odśwież stronę — poprosi o nowy.

**Strona się nie otwiera pod `/local/`.** Home Assistant czyta katalog `www` przy starcie. Po utworzeniu go zrestartuj HA.

**Pusty plan dnia.** Strona pokazuje w planie tylko pierwszą lekcję z sensorów. Pełny plan weź z karty kalendarza HA — integracja wystawia kalendarz `calendar.<uczeń>_plan_lekcji`.

## Co można zmienić

Wszystko. Kolory i odstępy siedzą w zmiennych na początku `styl.css`, układ kart w funkcji `rysuj()` w `dashboard.js` — kolejność kart to kolejność argumentów `s.append(...)`. Kartę, której nie potrzebujesz, po prostu usuń z tej listy.

Dane pokazowe w `dane-demo.js` mają ten sam kształt co dane z HA, więc wygodnie pracuje się na nich offline: otwórz `index.html` bez `?prefix=` i układ rysuje się natychmiast, bez czekania na serwer szkoły.
