# Dane i definicje analiz

Te definicje są obowiązujące. Implementacja ma je odwzorować, a nie zastąpić „podobną” statystyką.

Wzory żyją tylko w `src/`. Mapper Hadoop importuje te funkcje i nie liczy ich drugi raz. Silnika szachowego nie uruchamiamy.

## Źródło główne

- Katalog i licencja CC0: https://database.lichess.org/
- Plik: https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst
- Wrzesień 2026: 29,2 GB spakowane, 89 616 462 partie. Lichess podaje, że po rozpakowaniu plik jest około 7,1 raza większy oraz że niepełne archiwum `.zst` nadal da się rozpakować.
- Do projektu bierzemy wycinek. Tryb deweloperski kończy się na 50 MB nieskompresowanego PGN. Tryb pełny wymaga co najmniej 5 500 000 000 bajtów i ucina na granicy partii, nie w połowie nagłówka.
- Ścieżka HDFS: `/user/chess/raw/lichess_2026-09.pgn`

Od kwietnia 2017 partie mają zegar co do sekundy w komentarzu `[%clk]` przy półruchu. Około 6% partii standard ma ocenę Stockfisha `[%eval …]`, zawsze z perspektywy białych. Oceny mate (`#4`, `#-4`) pomijamy tam, gdzie potrzebna jest liczba centypionów.

Przykład zapisu:

```text
1. e4 { [%eval 0.17] [%clk 0:00:30] } 1... c5 { [%eval 0.19] [%clk 0:00:30] }
```

`[%eval 0.17]` oznacza 17 centypionów (wartość w pionkach razy 100).

## Źródło scrapowane

- Indeks: https://ratings.fide.com/
- Listy bierzemy z linków na stronie głównej (`list=` w adresie). Kodu listy nie zgadujemy, jeśli linku nie ma.
- Strona listy dociąga tabelę z adresu podanego w jej źródle (dziś `a_top.php?list=…`). Tego adresu też nie wymyślamy: musi wystąpić w pobranym HTML.
- Między żądaniami jest przerwa. Zapisujemy nazwisko, federację, ranking, rok urodzenia, miejsce, nazwę listy, okres i adres strony.
- To inne osoby niż nicki z Lichess. W sprawozdaniu nie ma łączenia tych zbiorów po nazwisku.

## Czyszczenie

Partia odpada ze wszystkich jobów, gdy:

- `Result` nie jest `1-0`, `0-1` ani `1/2-1/2`,
- brakuje `WhiteElo` albo `BlackElo`, albo wartość nie jest liczbą całkowitą,
- `TimeControl` jest puste albo równe `-`.

Dodatkowo, osobno dla każdego jobu:

- `blunder_in_trouble` pomija ruch bez pary liczbowych `[%eval]` albo bez zegara gracza, który ten ruch wykonał. Partia bez żadnego takiego ruchu odpada z powodem `no_qualifying`.
- `comeback_by_tc` bierze tylko partie rozstrzygnięte (`1-0` albo `0-1`) z co najmniej jedną liczbową oceną. Remis odpada z powodem `not_decisive`. Brak oceny liczbowej (sam mat się nie liczy) odpada z powodem `no_eval`.
- `think_vs_cpl` odrzuca ruch o ujemnym czasie namysłu (licznik `negative_think`) i pomija ruch bez policzalnej straty. Partia bez żadnego policzonego ruchu odpada z powodem `no_qualifying`.

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

Bullet nie jest uśredniany z klasykiem. Tempo jest częścią klucza albo osobnym panelem wykresu.

## Kubełki Elo

Kubełek liczymy z Elo gracza, który wykonał ruch (`blunder_in_trouble`, `think_vs_cpl`). Job powrotu nie dzieli po Elo: klucz to samo tempo.

| Elo | Klucz |
|---|---|
| poniżej 1200 | `u1200` |
| 1200–1599 | `1200` |
| 1600–1999 | `1600` |
| 2000–2399 | `2000` |
| 2400 i więcej | `2400` |

## Job `blunder_in_trouble`

Pytanie: czy zejście zegara do 10 sekund psuje jakość ruchu i czy słabiej notowani oraz bullet tracą więcej.

Ruch wchodzi, gdy jest para liczbowych `[%eval]` i zegar gracza przy tym ruchu. Para to ocena po poprzednim półruchu i ocena po tym ruchu, obie z pliku (perspektywa białych). Pierwszy półruch partii nie ma oceny przed sobą, więc odpada. Mat po którejkolwiek stronie pary pomija ruch. Brak `[%clk]` przy ruchu też go pomija.

Przed stratą zamieniamy ocenę na perspektywę gracza, który wykonał ruch. Dla czarnych zmieniamy znak centypionów. Strata to `centipawn_loss`: `max(0, centypiony przed − centypiony po)`.

Błąd to strata co najmniej 100 centypionów. Zegar 10 sekund i mniej to `trouble` (pod flagą). Zegar powyżej 10 sekund to `ok` (z czasem). Próg zegara i próg straty są niezależne: ruch przy 11 sekundach z dużą stratą jest błędem w kubełku `ok`, a nie ruchem pod flagą.

Klucz: `{tempo}|{kubełek Elo gracza}|{trouble albo ok}`.

Z mappera, jeden rekord na klucz w partii: `n_moves`, `n_blunders`. Reducer sumuje. Odsetek błędów to `n_blunders / n_moves`.

Wykres: odsetek błędów, słupek „pod flagą” obok „z czasem”. Każde tempo na osobnym panelu, więc bullet nie miesza się z klasykiem.

## Job `comeback_by_tc`

Pytanie: w którym tempie częściej wygrywa się z pozycji gorszej o co najmniej 2 piony.

Tylko partie rozstrzygnięte, które mają choć jedną liczbową ocenę. Oceny mate nie spełniają tego warunku.

Białe wracają, gdy wygrały (`1-0`) i kiedykolwiek w partii liczba centypionów z pliku jest `<= -200`. Czarne wracają, gdy wygrały (`0-1`) i kiedykolwiek ocena jest `>= 200`. Próg 200 centypionów to 2 piony. Ocena `-199` albo `199` nie jest powrotem. Nie odwracamy znaku: w pliku ocena jest z perspektywy białych, a warunek czarnych jest zapisany już po ich stronie (`>= 200` znaczy, że białe były do przodu o 2 piony).

Klucz: tempo.

Jeden rekord na partię: `n=1`, `comeback` równe 0 albo 1. Odsetek powrotów to `comeback / n`.

Wykres: odsetek powrotów według tempa, każde tempo osobno.

W sprawozdaniu wprost: dotyczy około 6% partii, tych z gotowym `[%eval]`. To nie jest losowy wycinek wszystkich partii września.

## Job `think_vs_cpl`

Pytanie: czy dodatkowe sekundy zmniejszają stratę centypionów i czy u wysokiego Elo krzywa się wypłaszcza.

Czas namysłu liczymy z własnego zegara gracza i z inkrementu w `TimeControl`:

- pierwszy ruch gracza: czas początkowy (pierwsza liczba z `TimeControl`) minus zegar po ruchu,
- każdy kolejny ruch gracza: poprzedni własny zegar minus zegar po ruchu, plus inkrement.

Inkrementu nie dodajemy przy pierwszym ruchu. Brak inkrementu to 0. Jeśli poprzedni własny półruch nie ma zegara, różnicy nie liczymy. Ujemny czas (zegar urósł bardziej niż inkrement) odrzucamy i zwiększamy licznik `negative_think`. Zero sekund zostaje.

Koszyki czasu namysłu (sekundy, przedział z lewej domknięty):

| Czas namysłu `t` | Koszyk |
|---|---|
| `0 <= t < 2` | `0-2` |
| `2 <= t < 10` | `2-10` |
| `t >= 10` | `10+` |

Strata centypionów jest ta sama co w `blunder_in_trouble` (znak czarnych odwrócony, mat i brak pary pomijają ruch). Ruch bez straty liczbowej nie wchodzi, nawet gdy czas namysłu jest znany.

Klucz: `{tempo}|{kubełek Elo gracza}|{koszyk}`. Tempo zostaje w kluczu, żeby bullet nie został uśredniony z klasykiem.

Z mappera, jeden rekord na klucz w partii: `n_moves`, `sum_cpl`. Reducer sumuje. Średnia strata to `sum_cpl / n_moves`.

Wykres: średnia strata, linia na kubełek Elo, osobny panel na tempo.

## Format linii MapReduce

Mapper wypisuje tekst UTF-8:

```text
klucz\tliczba,liczba,...
```

Kolejność liczb jest stała w danym jobie:

| Job | Liczby |
|---|---|
| `blunder_in_trouble` | `n_moves,n_blunders` |
| `comeback_by_tc` | `n,comeback` |
| `think_vs_cpl` | `n_moves,sum_cpl` |

Reducer rozdziela po przecinku, sumuje pola jako `int` i wypisuje ten sam układ. Klucze z polami pustymi nie występują.

## MongoDB

Kolekcja `aggregates` w Atlasie. Unikalny indeks `(analysis, key)`. Upsert. Pola: `analysis` (`blunder_in_trouble`, `comeback_by_tc` albo `think_vs_cpl`), `key`, liczniki jobu, `source_month` = `2026-09`, `updated_at`. Agregaty nie trafiają do lokalnego Mongo. Puste `ATLAS_URI` kończy loader błędem, który nazywa brakujące `ATLAS_URI`, i nic nie zapisuje w innym miejscu.

Kolekcja `fide_top` lokalnie. Unikalny indeks `(list, period, rank)`. Drugi zapis tego samego wiersza nie zwiększa `count`.

Kolekcja `import_runs` lokalnie. Jeden dokument na pipeline (`hdfs_pgn`, `fide_scrape`, `aggregates`). Przy ponownym imporcie dokument jest zastępowany. Trzyma adres źródła, liczbę bajtów, SHA-256 pliku PGN, ścieżkę HDFS i czas zakończenia.

Gdy SHA-256 pliku lokalnego jest zgodny z ostatnim `import_runs` i rozmiar w HDFS jest ten sam, ponowny import pliku nic nie dopisuje.

Połączenie lokalne: `tls=True` i plik CA. Bez `tlsAllowInvalidCertificates`. Atlas: URI `mongodb+srv`. Hasła tylko w `.env`, nigdy w kodzie.

## Kod poprzednich jobów

Funkcje `ply_job`, `clock_job` (`src/pgn.py`) i `accuracy_job` (`src/accuracy.py`) zostają w repozytorium, bo testy etapu 1 na nich stoją. Obowiązujące analizy MapReduce są trzy i są opisane wyżej. Ich wzory są w `src/analyses.py` i wołają wspólne `centipawn_loss`, tempo i kubełki, zamiast kopiować je do mapperów.
