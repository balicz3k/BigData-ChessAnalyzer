# Dane i definicje analiz

Te definicje są obowiązujące. Implementacja ma je odwzorować, a nie zastąpić „podobną” statystyką.

## Źródło główne

- Katalog i licencja CC0: https://database.lichess.org/
- Plik: https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst
- Wrzesień 2026: 29,2 GB spakowane, 89 616 462 partie. Lichess podaje, że po rozpakowaniu plik jest około 7,1 raza większy oraz że niepełne archiwum `.zst` nadal da się rozpakować.
- Do projektu bierzemy wycinek. Tryb deweloperski kończy się na 50 MB nieskompresowanego PGN. Tryb pełny wymaga co najmniej 5 500 000 000 bajtów i ucina na granicy partii, nie w połowie nagłówka.
- Ścieżka HDFS: `/user/chess/raw/lichess_2026-09.pgn`

Od kwietnia 2017 partie mają zegar co do sekundy w komentarzu `[%clk]` przy półruchu. Około 6% partii standard ma ocenę Stockfisha `[%eval …]`, zawsze z perspektywy białych. Oceny mate (`#4`, `#-4`) pomijamy przy dokładności i liczymy osobno.

Przykład zapisu:

```text
1. e4 { [%eval 0.17] [%clk 0:00:30] } 1... c5 { [%eval 0.19] [%clk 0:00:30] }
```

`[%eval 0.17]` oznacza 17 centypionów (wartość w pionkach razy 100).

## Źródło scrapowane

- Indeks: https://ratings.fide.com/
- Potwierdzone strony: https://ratings.fide.com/a_top.php?list=open oraz https://ratings.fide.com/a_top.php?list=men_blitz
- Rapid i listy kobiet bierzemy z linków znalezionych na stronie głównej. Kodu listy nie zgadujemy, jeśli linku nie ma.
- Między żądaniami jest przerwa. Zapisujemy nazwisko, federację, ranking, rok urodzenia, miejsce, nazwę listy, okres i adres strony.
- To inne osoby niż nicki z Lichess. W sprawozdaniu nie ma łączenia tych zbiorów po nazwisku.

## Czyszczenie

Partia odpada ze wszystkich jobów, gdy:

- `Result` nie jest `1-0`, `0-1` ani `1/2-1/2`,
- brakuje `WhiteElo` albo `BlackElo`, albo wartość nie jest liczbą całkowitą,
- `TimeControl` jest puste albo równe `-`.

Dodatkowo:

- job zegara odrzuca partię bez ani jednego `[%clk]`,
- job dokładności bierze tylko partię z co najmniej dziesięcioma ocenami liczbowymi `[%eval]` (mate się do tej dziesiątki nie wlicza).

Powód odrzucenia w MapReduce idzie licznikiem `reporter:counter` na stderr. Z logu jobu ma dać się przepisać tabelę do sprawozdania.

## Tempo

Szacowany czas partii, tak jak na Lichess: sekundy na zegarze plus 40 razy inkrement. `180+2` daje `180 + 80 = 260` sekund. Brak inkrementu traktujemy jako 0.

| Szacunek w sekundach | Klasa |
|---|---|
| poniżej 30 | `ultrabullet` |
| poniżej 180 | `bullet` |
| poniżej 480 | `blitz` |
| poniżej 1500 | `rapid` |
| 1500 i więcej | `classical` |

## Kubełki Elo

Dla długości partii kubełek liczymy ze średniej `WhiteElo` i `BlackElo`. Dla dokładności kubełek liczymy z Elo gracza, który wykonał ruch.

| Elo | Klucz |
|---|---|
| poniżej 1200 | `u1200` |
| 1200–1599 | `1200` |
| 1600–1999 | `1600` |
| 2000–2399 | `2000` |
| 2400 i więcej | `2400` |

## Job `ply_by_tc_elo`

Pytanie: czy krótsze tempo daje krótszą partię i czy zależy to od rankingu.

Półruch to token SAN (`e4`, `Nf3`, `O-O`, `exd5`, `e8=Q+`). Nie liczymy numerów ruchów (`1.`, `1...`), komentarzy w klamrach ani wyniku na końcu.

Klucz: `{tempo}|{kubełek średniego Elo}`.

Z mappera, jeden rekord na partię: `n=1` oraz `sum_plies`. Reducer sumuje. Średnia długość to `sum_plies / n`.

## Job `time_trouble_by_tc`

Pytanie: czy zejście zegara do 10 sekund wiąże się z porażką.

Kolejność komentarzy `[%clk]` odpowiada kolejności półruchów: nieparzysty w kolejności gry to białe, parzysty to czarne. Format `H:MM:SS` albo `M:SS`. Gracz ma czasówkę, gdy którykolwiek jego zegar jest mniejszy lub równy 10 sekund.

Klucz: `{tempo}|{white albo black}`.

Jeden rekord na stronę w partii:

- `n = 1`
- `trouble` = 1 albo 0
- `trouble_loss` = 1, gdy `trouble` = 1 i ta strona przegrała
- `ok_loss` = 1, gdy `trouble` = 0 i ta strona przegrała

Remis nie jest porażką żadnej strony. W bullecie próg 10 sekund jest blisko całego budżetu czasu. W sprawozdaniu i na wykresie bullet nie jest zlepiany z klasykiem w jedną liczbę.

## Job `accuracy_by_elo`

Pytanie: czy wyżej notowani grają dokładniej względem oceny już zapisanej przy ruchu.

Dotyczy tylko partii z co najmniej dziesięcioma liczbowymi `[%eval]`. Para ocen do ruchu to ocena sprzed ruchu i ocena po ruchu, obie z perspektywy białych w pliku. Jeśli któraś jest matem, ruch pomijamy.

Przed wzorem zamieniamy ocenę na perspektywę gracza, który wykonał ruch. Dla czarnych zmieniamy znak centypionów.

Szansa wygranej, wzór opisany na https://lichess.org/page/accuracy :

```text
Win% = 50 + 50 * (2 / (1 + exp(-0.00368208 * centypiony)) - 1)
```

Dokładność ruchu:

```text
gdy Win% po ruchu >= Win% przed ruchem: 100
w przeciwnym razie:
Dokładność% = 103.1668 * exp(-0.04354 * (Win% przed - Win% po)) - 3.1669
```

Wynik obcinamy do przedziału 0–100. To uproszczenie względem kodu Lichess (tam jest jeszcze dopłata za niepewność analizy oraz średnia harmoniczna całej partii). W sprawozdaniu piszemy, że podajemy średnią dokładności ruchów, nie znaczek dokładności partii z serwisu.

Strata centypionów ruchu, z perspektywy gracza: `max(0, centypiony przed - centypiony po)`.

Klucz: kubełek Elo gracza, który wykonał ruch.

Jeden rekord na stronę, jeśli ta strona ma choć jeden policzony ruch:

- `n_moves`
- `sum_accuracy_millis` = suma dokładności ruchów pomnożona przez 1000 i zaokrąglona do całkowitej
- `sum_cpl` = suma strat centypionów

Średnia dokładność = `sum_accuracy_millis / n_moves / 1000`. Średnia strata = `sum_cpl / n_moves`.

Podzbiór z oceną nie jest losowy. To partie, przy których ocena już była w dumpie.

## Format linii MapReduce

Mapper wypisuje tekst UTF-8:

```text
klucz\tliczba,liczba,...
```

Kolejność liczb jest stała w danym jobie i opisana wyżej. Reducer rozdziela po przecinku, sumuje pola jako `int` i wypisuje ten sam układ. Klucze z polami pustymi nie występują.

## MongoDB

Kolekcja `aggregates` w Atlasie. Unikalny indeks `(analysis, key)`. Upsert. Pola: `analysis`, `key`, liczniki jobu, `source_month` = `2026-09`, `updated_at`.

Kolekcja `fide_top` lokalnie. Unikalny indeks `(list, period, rank)`.

Kolekcja `import_runs` lokalnie. Jeden dokument na pipeline (`hdfs_pgn`, `fide_scrape`, `aggregates`). Przy ponownym imporcie dokument jest zastępowany. Trzyma adres źródła, liczbę bajtów, SHA-256 pliku PGN, ścieżkę HDFS i czas zakończenia.

Gdy SHA-256 pliku lokalnego jest zgodny z ostatnim `import_runs` i rozmiar w HDFS jest ten sam, ponowny import pliku nic nie dopisuje.

Połączenie lokalne: `tls=True` i plik CA. Bez `tlsAllowInvalidCertificates`. Atlas: URI `mongodb+srv`. Hasła tylko w `.env`, nigdy w kodzie.
