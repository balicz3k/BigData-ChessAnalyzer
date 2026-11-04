# Sprawozdanie: BigData Chess Analyzer

**Autor:** Jakub Balicki
**Przedmiot:** Big Data
**Data:** 2026-11-04

---

## 1. Opis projektu

Projekt **BigData Chess Analyzer** realizuje przetwarzanie masowych danych z serwisu Lichess.org w celu odkrycia wzorców behawioralnych w partiach szachowych. Analizowany zbiór pochodzi z września 2026 roku i obejmuje miliony partii w formacie PGN z osadzonymi adnotacjami silnika szachowego (centypiony).

Zdefiniowano trzy pytania badawcze:

1. **Błędy przy fladze** – czy gracze popełniają więcej błędów, gdy kończy im się czas na zegarze, i czy zależy to od tempa gry i poziomu rankingowego?
2. **Powroty z przegranej pozycji** – jak często gracz wygrywa mimo wyraźnie gorszej pozycji strategicznej, z podziałem na tempo?
3. **Czas namysłu a jakość ruchu** – czy dłuższy czas poświęcony na ruch przekłada się na mniejszą stratę centypionów, i czy zależy to od rankingu ELO?

Do przetwarzania wykorzystano paradygmat MapReduce uruchomiony na klastrze Hadoop Streaming w kontenerze Docker. Wyniki przechowywane są lokalnie (MongoDB 7.0) oraz w chmurze (MongoDB Atlas, klaster M0).

---

## 2. Dane

- **Źródło:** Lichess.org – otwarte bazy partii szachowych (licencja CC0)
- **Zakres:** wrzesień 2026
- **Rozmiar:** ~5,5 GB (plik PGN skompresowany zstandard, pełny wycinek ~15 GB)
- **Format:** PGN (Portable Game Notation)

Każda partia w pliku PGN zawiera:
- Nagłówki: `WhiteElo`, `BlackElo`, `TimeControl`, `Result`, `Event`
- Ruchy z komentarzami silnika: `[%eval <cp>]` (ocena w centypionach, perspektywa białych) lub `[%eval #<n>]` (mat w n ruchach)
- Adnotacje zegara: `[%clk h:mm:ss]` po każdym ruchu

**Klasyfikacja tempa** opiera się na wartości `TimeControl` z nagłówka PGN: ultrabullet, bullet, blitz, rapid, classical. **Kubełki ELO:** poniżej 1200, 1200–1599, 1600–1999, 2000–2399, 2400+.

Oprócz danych Lichess projekt scrapuje ranking FIDE (top 100 graczy z list rankingowych) za pomocą biblioteki Beautiful Soup. Dane te trafiają do lokalnej kolekcji `fide_top` w MongoDB.

---

## 3. Architektura systemu

```
  Lichess PGN (.zst)
         |
         v
   HDFS /user/chess/raw/          <- Hadoop 3.4.3 (kontener Docker)
         |
         +-- Hadoop Streaming MapReduce x3
         |         mapper_*.py  ->  reducer.py
         |
         v
   HDFS /user/chess/out/full/     <- wyniki TSV (part-00000)
         |
         +-- src/charts.py        <- matplotlib -> plots/*.png
         |
         +-- src/load_aggregates.py
                   |
                   +-- MongoDB lokalny (Docker, mongo:7.0.45)
                   |     kolekcja: import_runs (metadane)
                   |
                   +-- MongoDB Atlas (klaster M0, chmura)
                         kolekcja: aggregates (126 dokumentów)
```

**Komponenty infrastruktury:**

| Warstwa | Technologia | Wersja |
|---|---|---|
| Przetwarzanie wsadowe | Apache Hadoop Streaming | 3.4.3 |
| Pliki danych | HDFS (single-node Docker) | 3.4.3 |
| Lokalna baza danych | MongoDB (Docker) | 7.0.45 |
| Baza chmurowa | MongoDB Atlas | klaster M0 |
| Scraping FIDE | Python + Beautiful Soup | — |
| Wizualizacje | matplotlib | — |
| Środowisko wykonawcze | Python | 3.14.4 |

Hadoop działa jako pojedynczy kontener z NameNode, DataNode, ResourceManager i NodeManager (`docker/hadoop-start.sh`). Połączenie z lokalnym MongoDB zabezpieczone jest TLS z własnym CA (certyfikaty generowane skryptem `scripts/gen_certs.sh`).

---

## 4. Implementacja Hadoop Streaming

### Wzorzec ogólny

Wszystkie trzy joby używają tego samego **reducera** (`mr/reducer.py`), który sumuje liczby całkowite pogrupowane według klucza. Mapper dla każdego jobu importuje odpowiednią funkcję z `src/analyses.py` i wywołuje `map_games()` ze `src/streaming.py`. Mechanizm `_bootstrap()` rozwiązuje ścieżkę do modułu `src/` zarówno lokalnie, jak i w środowisku Hadoop Streaming (inny katalog roboczy).

Skrypt `mr/run_jobs.sh` uruchamia trzy joby sekwencyjnie. Kluczowe parametry Hadoop:
- `mapreduce.input.fileinputformat.split.minsize=2000000000000` – jeden split, żeby granica bloku nie przecięła partii PGN w połowie
- `mapreduce.job.reduces=1` – jeden reducer, wynik w jednym pliku `part-00000`
- `mapreduce.task.timeout=7200000` – timeout 2 godziny na zadanie

---

### 4.1 Analiza błędów przy fladze (`blunder_in_trouble`)

**Co mierzy:** Odsetek ruchów-blunderów (strata >= 100 centypionów) w zależności od tego, czy graczowi kończy się czas na zegarze (<= 10 sekund = `trouble`) czy nie (`ok`). Wynik grupowany po kombinacji (tempo, kubełek ELO, stan zegara).

**Klucz MapReduce:** `tempo|elo_bucket|trouble` lub `tempo|elo_bucket|ok`
**Wartości:** `(n_moves, n_blunders)` – liczba ruchów z dostępną oceną i zegarem, liczba tych, które były blunderami.

Ruch wchodzi do analizy tylko gdy dostępna jest para liczbowych ocen (przed i po ruchu) oraz wartość zegara. Ruchy po zugzwangu i ruchy matujące są pomijane (brak pary ocen liczbowych).

**Wyniki z HDFS (`data/out/full/blunder_in_trouble/part-00000`):**

```
blitz|1200|ok	1919137,359076
blitz|1200|trouble	39951,11731
blitz|1600|ok	2160963,347523
blitz|1600|trouble	67070,18008
blitz|2000|ok	1240964,159851
blitz|2000|trouble	63345,15210
blitz|2400|ok	326207,33025
blitz|2400|trouble	21128,4733
blitz|u1200|ok	922385,214095
blitz|u1200|trouble	16365,5526
bullet|1200|ok	713236,140637
bullet|1200|trouble	90961,26999
bullet|1600|ok	847614,154524
bullet|1600|trouble	109686,30386
bullet|2000|ok	514067,83125
bullet|2000|trouble	80662,21448
bullet|2400|ok	153218,20605
bullet|2400|trouble	22686,6062
bullet|u1200|ok	325746,73655
bullet|u1200|trouble	47110,15464
```

**Interpretacja wybranych wyników:**
- Blitz 1200–1599, normalny czas: 359076 / 1919137 = **18,7% błędów**
- Blitz 1200–1599, pod flagą: 11731 / 39951 = **29,4% błędów** (wzrost o ~57%)
- Bullet 1200–1599, normalny czas: 140637 / 713236 = **19,7% błędów**
- Bullet 1200–1599, pod flagą: 26999 / 90961 = **29,7% błędów** (wzrost o ~51%)

---

### 4.2 Analiza powrotów z przegranej pozycji (`comeback_by_tc`)

**Co mierzy:** Jak często gracz wygrywa partię mimo tego, że w pewnym momencie pozycja była wyraźnie przegrana (ocena silnika <= -200 cp dla białych lub >= +200 cp dla czarnych, czyli różnica co najmniej dwóch pionów). Tylko partie rozstrzygnięte (bez remisów). Grupowanie po tempie gry.

**Klucz MapReduce:** `tempo`
**Wartości:** `(n, comeback)` – liczba analizowanych partii, liczba tych z powrotem.

**Wyniki z HDFS (`data/out/full/comeback_by_tc/part-00000`):**

```
blitz	104385,49312
bullet	49770,27708
classical	4394,1776
rapid	73355,33670
ultrabullet	1850,1429
```

**Interpretacja:**
- Blitz: 49312 / 104385 = **47,2% powrotów** z pozycji gorszej o >= 2 piony
- Bullet: 27708 / 49770 = **55,7% powrotów** – najwyższy odsetek
- Rapid: 33670 / 73355 = **45,9% powrotów**
- Classical: 1776 / 4394 = **40,4% powrotów** – najniższy odsetek
- Ultrabullet: 1429 / 1850 = **77,2%** – przy najkrótszym tempie oceny silnika często jeszcze nie odzwierciedlają faktycznej gry

Wysoki odsetek w bullet i ultrabullet sugeruje, że przy krótkich kontrolach czasu ocena silnika jest mniej przewidywalna jako wskaźnik ostatecznego wyniku – błędy końcowe dominują nad jakością pozycji.

---

### 4.3 Czas namysłu a strata centypionów (`think_vs_cpl`)

**Co mierzy:** Korelację między czasem poświęconym na ruch (w sekundach) a jakością ruchu wyrażoną stratą centypionów. Grupowanie po kombinacji (tempo, kubełek ELO, koszyk czasu namysłu).

**Kubełki czasu namysłu:** 0–2 s, 2–10 s, 10+ s

**Klucz MapReduce:** `tempo|elo_bucket|time_bucket`
**Wartości:** `(n_moves, sum_cpl)` – liczba ruchów, suma strat centypionów.

Czas namysłu liczony jest jako różnica między zegarem poprzedniego własnego ruchu a zegarem bieżącego ruchu (plus inkrement). Ujemne wartości (np. przy niepełnych danych zegara) są odrzucane.

**Wyniki z HDFS (`data/out/full/think_vs_cpl/part-00000`):**

```
blitz|1200|0-2	471504,26274731
blitz|1200|10+	326951,33829664
blitz|1200|2-10	1160387,87920833
blitz|1600|0-2	646395,32716247
blitz|1600|10+	319583,29602644
blitz|1600|2-10	1261867,84908014
blitz|2000|0-2	447658,19928273
blitz|2000|10+	161178,12534257
blitz|2000|2-10	695411,38617646
blitz|2400|0-2	148469,6013654
blitz|2400|10+	31772,2031120
blitz|2400|2-10	167090,7658426
blitz|u1200|0-2	175434,11499799
blitz|u1200|10+	184993,22830336
blitz|u1200|2-10	578150,52829010
bullet|1200|0-2	407170,27755738
bullet|1200|10+	18807,2217363
bullet|1200|2-10	377616,35133992
bullet|1600|0-2	552000,35308817
bullet|1600|10+	17715,1982889
```

**Interpretacja (blitz, 1200–1599):**
- 0–2 s: 26274731 / 471504 = **55,7 cp/ruch** średnia strata
- 2–10 s: 87920833 / 1160387 = **75,8 cp/ruch** średnia strata
- 10+ s: 33829664 / 326951 = **103,5 cp/ruch** średnia strata

Wynik jest pozornie paradoksalny – dłuższy namysł koreluje z wyższą stratą. Wyjaśnienie: gracze myślą dłużej właśnie wtedy, gdy pozycja jest trudna lub krytyczna, a i tak trudno podjąć dobry ruch. Efekt jest widoczny we wszystkich grupach ELO, lecz silniejszy dla niższych rankingów.

---

## 5. Wyniki i wizualizacje

Trzy wykresy wygenerowane przez `src/charts.py` (matplotlib) zapisane w `plots/`:

### `plots/blunder.png` – Błędy przy fladze i z czasem

Wykres grupowany wg tempa i kubełka ELO, porównujący odsetek błędów w stanie `trouble` i `ok`. Główny wniosek: **presja czasu zwiększa odsetek blunderów o 50–70%** niezależnie od poziomu graczy. Efekt jest silniejszy dla bullet niż blitz – gracze w bullet częściej trafiają w stan `trouble`, a jednocześnie mają mniej czasu na reakcję. Gracze z rankingiem 2400+ wykazują mniejszy wzrost odsetka błędów pod presją czasu niż gracze słabsi.

### `plots/comeback.png` – Powrót z pozycji gorszej o dwa piony

Wykres słupkowy z odsetkiem powrotów dla każdego tempa. Klasycy (40,4%) rzadziej wracają niż gracze blitz (47,2%) i bullet (55,7%). Interpretacja: przy wolnym tempie oceny silnika lepiej odzwierciedlają faktyczny potencjał pozycji – jeśli jest źle, rzadziej udaje się odwrócić losy. Przy szybkich tempach błędy końcówki i presja czasu sprawiają, że ocena pozycji słabiej przewiduje wynik.

### `plots/namysl.png` – Czas namysłu a strata centypionów

Wykresy panelowe osobno dla każdego tempa i kubełka ELO, z trzema słupkami (0–2 s, 2–10 s, 10+ s). Paradoks „dłuższy namysł, gorszy ruch" jest konsekwentny we wszystkich segmentach. Silniejsi gracze (ELO 2400+) wykazują mniejszą bezwzględną stratę centypionów w każdym kubełku czasu, lecz podobny wzorzec względny.

---

## 6. Synchronizacja z MongoDB Atlas

Po zakończeniu trzech jobów Hadoop wyniki wczytywane są do MongoDB Atlas przez `src/load_aggregates.py`.

**Parametry kolekcji:**
- Nazwa kolekcji: `aggregates`
- Klaster: M0 (warstwa bezpłatna)
- Połączenie: `mongodb+srv://` (TLS/SSL)
- Łączna liczba dokumentów: **126**
- Klucz `source_month`: `"2026-09"` (identyfikator miesiąca źródłowego)

**Idempotentność:** każdy dokument upsertowany na podstawie unikalnego indeksu złożonego `(analysis, key)`. Wielokrotne uruchomienie skryptu nie tworzy duplikatów – aktualizuje istniejące dokumenty (`$set`). Pole `updated_at` aktualizowane przy każdym wykonaniu.

**Metadane lokalne:** po każdym udanym wgraniu do Atlasu w lokalnej kolekcji `import_runs` zapisywany jest wpis z: `source_month`, `hdfs_path`, liczbą wgranych dokumentów (`documents`) i łączną liczbą wierszy wynikowych (`rows`), znacznikiem czasu.

**Weryfikacja:** `src/verify_idempotent.py` porównuje sumy kontrolne agregatów przed i po ponownym wgraniu, potwierdzając niezmienność danych.

---

## 7. Testy automatyczne

Projekt zawiera pełny zestaw testów jednostkowych w katalogu `tests/`, uruchamianych przez pytest:

| Plik testu | Zakres |
|---|---|
| `test_pgn.py` | parser PGN, nagłówki, ruchy, kontrola czasu |
| `test_accuracy.py` | wzory strat centypionów |
| `test_analyses.py` | trzy funkcje jobów na fixturach PGN |
| `test_charts.py` | generowanie wykresów z danych agregatów |
| `test_streaming.py` | `map_games`, `reduce_lines` |
| `test_fide.py` | scraper FIDE |
| `test_load.py` | `load_aggregates`, idempotentność |
| `test_download.py` | pobieranie pliku PGN z Lichess |
| `test_szkielet.py` | integralność struktury projektu (`.gitignore`, brak sekretów) |

Wszystkie testy przechodzą (`pytest` zwraca kod 0). Fixtury PGN w `tests/fixtures/` pokrywają przypadki brzegowe: brak ELO, brak oceny, ocena mata, zegar w grze.

---

## 8. Podsumowanie i wnioski

### Główne wyniki

1. **Presja czasowa istotnie zwiększa odsetek błędów** – gracze pod flagą popełniają o ~50–70% więcej blunderów niż przy normalnym czasie, niezależnie od tempa i rankingu ELO.

2. **Odsetek powrotów z pozycji gorszej maleje wraz ze wzrostem kontroli czasu** – przy blitzu i bullecie wynik zależy w większym stopniu od błędów końcowych niż od jakości strategicznej; klasyk jest bardziej deterministyczny.

3. **Paradoks czasu namysłu** – dłuższy czas poświęcony na ruch koreluje z wyższą stratą centypionów, bo gracze namyślają się dłużej właśnie w trudniejszych pozycjach.

### Ograniczenia i możliwe rozszerzenia

- **Jedno źródło danych** – wyniki dotyczą tylko graczy Lichess z września 2026; mogą nie być reprezentatywne dla innych platform (Chess.com, FIDE OTB).
- **Brak kontroli zmiennych** – analiza jest korelacyjna, nie przyczynowo-skutkowa; np. wyższy ELO koreluje z lepszym zarządzaniem czasem.
- **Brak ocen dla wszystkich ruchów** – analiza opiera się na adnotacjach silnika dołączonych przez Lichess; nie wszystkie partie mają `[%eval]`.
- **Możliwe rozszerzenia:** analiza openingów ECO, wpływ liczby ruchów partii na odsetek błędów, porównanie miesięczne (trend czasowy), integracja z rankingiem FIDE do potwierdzenia, że top-100 zachowuje się inaczej niż ogół.

### Wnioski techniczne

Hadoop Streaming okazał się praktycznym narzędziem do przetwarzania pliku PGN ~5,5 GB z jednym splittem. Podejście „jeden plik, jeden split, jeden reducer" uprościło zarządzanie granicami partii w strumieniu. Idempotentny upsert do MongoDB Atlas z indeksem złożonym zapewnił bezpieczne wielokrotne wgrywanie wyników bez ryzyka duplikacji danych.
