# Dowody spełnienia wymagań

Zebrano 16.11.2026 (przebieg od zera 19:21–19:27, czas lokalny; HDFS podaje czasy w UTC, o godzinę wcześniej) na PC (Kubuntu, 16 rdzeni, 32 GB RAM), katalog `~/Documents/master-studies/BigData/ChessAnalyzer/`, kontenery `partie-hadoop` i `partie-mongo` w stanie healthy. Pełny przebieg od zera: `./run_all.sh --od-zera`, log w repozytorium: `wyniki/logi/run_all_full.log`. Hasła i adresy baz nie są nigdzie wypisywane.

## Tabela wymagań

Wymagania z `Zasady_zaliczenia_projekt1.pdf`; wyższy próg obejmuje niższe. Numer w ostatniej kolumnie odsyła do sekcji niżej.

| Próg | Wymaganie | Jak spełnione | Dowód |
|---|---|---|---|
| 3.0 | Problem i udokumentowane źródło danych | Lichess Open Database, wrzesień 2026, CC0; trzy pytania w README | 1 |
| 3.0 | Min. 5 GB danych po wypakowaniu | 5 500 001 981 B PGN, 2 362 417 partii | 1 |
| 3.0 | Aplikacja importująca dane do lokalnej MongoDB | `load_aggregates.py` (agregaty), `hdfs_io.py` / `split_pgn.py` (metadane importu) | 6 |
| 3.0 | Sprawdzanie i czyszczenie danych | odrzucenia z licznikami Hadoopa (wynik, Elo, tempo, brak ocen) | 4 |
| 3.0 | Co najmniej trzy sensowne analizy statystyczne | `blunder_in_trouble`, `comeback_by_tc`, `think_vs_cpl` | 4, 9 |
| 3.0 | Wizualizacja / zestawienia | `plots/*.png`, tabele w sprawozdaniu | 9 |
| 3.0 | Kod, dane lub instrukcja pobrania, sprawozdanie na Delcie | `do_oddania/` | 10 |
| 4.0 | Dwie bazy: lokalna + darmowa chmura MongoDB | MongoDB 7 w Dockerze + Atlas M0, w obu `aggregates` | 6 |
| 4.0 | Ponowny import bez niekontrolowanego powielania | upsert po unikalnym `(analysis, key)`; 0 → 126 → 126 | 6 |
| 4.0 | Dane do min. jednej bazy z web scrapingu | dodatek: ranking FIDE → lokalne `fide_top` | 7 |
| 4.0 | Prezentacja, przepływ danych i wyniki | `prezentacja/prezentacja.pdf` | 10 |
| 5.0 | Główny zbiór w HDFS | `/user/chess/raw/lichess_2026-09/` (8 części, 5,1 GiB) | 2 |
| 5.0 | Hadoop MapReduce / Streaming do analizy | 3 joby Streaming, 8 mapperów + 1 reducer | 3, 4 |
| 5.0 | Wyniki / agregaty / metadane w MongoDB | `aggregates` (obie bazy), `import_runs` (lokalnie) | 6 |
| 5.0 | Szyfrowane połączenie i uwierzytelnienie | TLS z własnym CA + SCRAM lokalnie, `mongodb+srv` w Atlasie | 5 |
| 5.0 | Prosta wizualizacja statystyk | `src/charts.py` → `plots/` | 9 |
| 5.0 | Prezentacja działania, Hadoopa i wyników | slajdy 4–5 (HDFS, Streaming, czasy), demo `run_all.sh --probka` | 10 |
| – | Poprawność obliczeń | sumy Hadoop = lokalny parser (próbka); 1 mapper = 8 mapperów (pełne dane) | 8 |

---

## 1. Dane (3.0)

```
$ ls -l data/lichess_2026-09.pgn
-rw-rw-r-- 1 balicz3k balicz3k 5500001981 Nov  3 22:54 data/lichess_2026-09.pgn
```

5 500 001 981 B (5,12 GiB) nieskompresowanego PGN, źródło `https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst` (CC0). Liczba partii z licznika Hadoopa `games`: **2 362 417**, linii (`Map input records`): 47 269 027. Ponowne uruchomienie nie pobiera pliku drugi raz (krok 3 w `run_all.sh`):

```
pomijam pobieranie, lichess_2026-09.pgn ma 5500001981 bajtów (próg FULL_MIN_BYTES = 5500000000)
```

SHA-256 pliku jest w lokalnej kolekcji `import_runs` (pipeline `hdfs_pgn`): `3d3a647a…71c47`.

## 2. HDFS (5.0)

```
$ docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw/lichess_2026-09
Found 8 items
-rw-r--r--   1 root supergroup    655.7 M 2026-11-16 17:36 /user/chess/raw/lichess_2026-09/part-000.pgn
...
-rw-r--r--   1 root supergroup    655.6 M 2026-11-16 17:37 /user/chess/raw/lichess_2026-09/part-007.pgn

$ docker exec partie-hadoop hdfs dfs -du -s -h /user/chess/raw/lichess_2026-09
5.1 G  5.1 G  /user/chess/raw/lichess_2026-09

$ docker exec partie-hadoop hdfs fsck /user/chess/raw/lichess_2026-09
 Total size:    5500001981 B
 Total files:   8
 Total blocks (validated):  48 (avg. block size 114583374 B)
The filesystem under path '/user/chess/raw/lichess_2026-09' is HEALTHY
```

Części powstały w `src/split_pgn.py` (cięcie tylko przed `[Event "`); suma rozmiarów równa się dokładnie rozmiarowi pliku źródłowego. Drugie uruchomienie niczego nie wysyła:

```
części już są: 8 plików w .../data/parts
HDFS bez zmian: /user/chess/raw/lichess_2026-09 ma 8 części, rozmiary zgodne
```

## 3. Hadoop Streaming: mappery, reducery, czasy (5.0)

Polecenie (krok 5 w `run_all.sh`): `docker exec partie-hadoop bash /opt/projekt/mr/run_jobs.sh /user/chess/raw/lichess_2026-09 /user/chess/out/full`. Fragmenty z `wyniki/logi/run_all_full.log`:

```
Start jobu blunder_in_trouble
        HDFS: Number of bytes read=5500002893
        Launched map tasks=8
        Launched reduce tasks=1
        Map input records=47269027
        Reduce output records=49
Koniec jobu blunder_in_trouble -> /user/chess/out/full/blunder_in_trouble (105 s)
Koniec jobu comeback_by_tc -> /user/chess/out/full/comeback_by_tc (103 s)      [Reduce output records=5]
Koniec jobu think_vs_cpl -> /user/chess/out/full/think_vs_cpl (116 s)          [Reduce output records=72]
```

Porównanie z jednym mapperem (ten sam kod, wejście = jeden plik `/user/chess/raw/lichess_2026-09.pgn`, logi `wyniki/logi/pomiar_1_mapper.log` i `pomiar_8_mapperow.log`):

| Job | 1 plik, 1 mapper | 8 części, 8 mapperów |
|---|---|---|
| `blunder_in_trouble` | 647 s | 105 s |
| `comeback_by_tc` | 598 s | 103 s |
| `think_vs_cpl` | 658 s | 116 s |
| razem | 31 min 43 s | 5 min 24 s (ok. 5,9×) |

Źródło: `wyniki/jeden_mapper/czasy.tsv` i `wyniki/full/czasy.tsv`. Na PC w tym czasie działał też trening sieci (UM), więc czasy są orientacyjne.

## 4. Czyszczenie danych i trzy analizy (3.0)

Liczniki Hadoopa z tego samego logu (grupa `chess`):

| Licznik | `blunder_in_trouble` | `comeback_by_tc` | `think_vs_cpl` |
|---|---|---|---|
| `games` (wszystkie partie) | 2 362 417 | 2 362 417 | 2 362 417 |
| `result` (zły wynik) | 220 | 220 | 220 |
| `timecontrol` (brak tempa) | 2 260 | 2 260 | 2 260 |
| `no_qualifying` (brak ruchu z oceną i zegarem) | 2 118 187 | – | 2 118 187 |
| `no_eval` (partia bez oceny) | – | 2 036 761 | – |
| `not_decisive` (remis) | – | 89 422 | – |
| `negative_think` (ruchy z ujemnym czasem) | – | – | 53 315 |

Wyniki (126 wierszy) są w `wyniki/full/*.tsv`, np. `comeback_by_tc.tsv` (`n, comeback, comeback_held`):

```
blitz	104385,49312,22491
bullet	49770,27708,14687
classical	4394,1776,778
rapid	73355,33670,15209
ultrabullet	1850,1429,909
```

## 5. Szyfrowanie i uwierzytelnienie (5.0)

```
$ .venv/bin/python scripts/check_mongo_tls.py
OK: TLS z weryfikacją certyfikatu (CA: ca.pem), uwierzytelniony jako: admin

$ .venv/bin/python scripts/proby_tls.py
1. bez TLS                   ODMOWA: ServerSelectionTimeoutError: localhost:27017: connection closed
2. TLS bez naszego CA        ODMOWA: ServerSelectionTimeoutError: localhost:27017: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1081)
3. TLS + CA, bez hasła       ODMOWA: OperationFailure: Command aggregate requires authentication
4. TLS + CA + hasło (SCRAM)  OK, aggregates: 126 dokumentów

$ docker inspect partie-mongo --format '{{json .Args}}'
["mongod","--auth","--bind_ip_all","--tlsMode","requireTLS","--tlsCertificateKeyFile","/certs/server.pem","--tlsCAFile","/certs/ca.pem","--tlsAllowConnectionsWithoutCertificates"]
```

`--tlsAllowConnectionsWithoutCertificates` oznacza tylko, że klient nie musi mieć własnego certyfikatu; klient zawsze weryfikuje certyfikat serwera plikiem CA, a adres z `tlsAllowInvalidCertificates` jest odrzucany w `src/mongo_io.py`. Port 27017 jest wystawiony tylko na `127.0.0.1`. Atlas: adres `mongodb+srv://` (TLS domyślnie), lista dozwolonych IP.

## 6. Dwie bazy, import i brak powielania (3.0, 4.0, 5.0)

Krok 7 w `run_all.sh --od-zera` (`src/verify_idempotent.py`): usuwa kolekcję, importuje dwa razy, liczy dokumenty.

```
usunięto kolekcje aggregates w obu bazach
aggregates przed importem:  {'lokalna': 0, 'atlas': 0}
aggregates po 1. imporcie:  {'lokalna': 126, 'atlas': 126}
aggregates po 2. imporcie:  {'lokalna': 126, 'atlas': 126}
OK: drugi import nie zwiększył liczby dokumentów
```

Stan baz po przebiegu (`.venv/bin/python -m src.summary`, skrót):

```
MongoDB lokalna (TLS + SCRAM): baza chess
  aggregates: 126 dokumentów          (blunder_in_trouble 49, comeback_by_tc 5, think_vs_cpl 72)
  aggregates_probka: 106 dokumentów   (wyniki z run_all.sh --probka)
  fide_top: 1202 dokumentów
  import_runs: 6 dokumentów
MongoDB Atlas (mongodb+srv): baza chess
  aggregates: 126 dokumentów          (49 / 5 / 72)
  aggregates_probka: 106 dokumentów
import_runs (metadane importów, lokalnie):
  aggregates: documents_local 126, documents_atlas 126, hdfs_path /user/chess/raw/lichess_2026-09
  hdfs_pgn_parts: bytes 5500001981, files 8, hdfs_path /user/chess/raw/lichess_2026-09
  hdfs_pgn: bytes 5500001981, sha256 3d3a647a…, hdfs_path /user/chess/raw/lichess_2026-09.pgn
  fide_scrape: count 1202, 12 list
```

Mechanizm: unikalny indeks `analysis_key` na `(analysis, key)` i `update_one(..., {"$set": ...}, upsert=True)`. Próbka idzie do osobnej kolekcji `aggregates_probka`, więc nie nadpisuje wyników z pełnych danych (tam też 0 → 106 → 106).

## 7. Web scraping – dodatek (4.0)

Krok 8 w `run_all.sh` (`python -m src.scrape_fide`, ratings.fide.com, 12 list Top, BeautifulSoup, upsert po `(list, period, rank)`):

```
fide_top count=1202
```

Liczba dokumentów przed i po przebiegu jest ta sama (1202), bo zapis jest upsertem. Dane FIDE trafiają tylko do lokalnej bazy i nie są łączone z partiami Lichess.

## 8. Poprawność obliczeń

- Próbka 50 MB, krok 6a w `run_all.sh --probka` (`wyniki/logi/run_all_probka.log`):
  ```
  sumy jobu blunder_in_trouble są zgodne z lokalnym parserem
  sumy jobu comeback_by_tc są zgodne z lokalnym parserem
  sumy jobu think_vs_cpl są zgodne z lokalnym parserem
  ```
- Pełne dane: wyniki z 1 mappera (`wyniki/jeden_mapper/`) i z 8 mapperów (`wyniki/full/`) są identyczne bajt w bajt (`cmp` dla trzech plików TSV) – podział na części nie zgubił ani nie zdublował żadnej partii.
- Testy: `181 passed` (krok 1 w obu przebiegach).

## 9. Wizualizacja (3.0, 5.0)

Krok 9: `python -m src.charts --out plots ...` → `plots/blunder.png`, `plots/comeback.png`, `plots/namysl.png`. Te same rysunki w PDF i tabele w sprawozdaniu generuje `sprawozdanie_latex/generuj.py` z plików w `wyniki/`.

## 10. Materiały do oddania i prezentacja (3.0, 4.0, 5.0)

- `do_oddania/`: zip z kodem (z `git archive`; skrypt `scripts/paczka_do_oddania.sh` sprawdza, że nie ma w nim `.env`, kluczy, certyfikatów ani danych PGN poza małymi fixturami testów), sprawozdanie PDF, prezentacja PDF, `INSTRUKCJA_DANYCH.md`.
- Prezentacja: `prezentacja/prezentacja.pdf` (12 slajdów).

## 11. Sekrety w repozytorium

```
$ git ls-files | grep -i -E "env|pem|key|pgn|zst"
.env.example            (szablon z pustymi wartościami)
docker/hadoop.env       (konfiguracja Hadoopa, bez haseł)
src/pgn.py, src/split_pgn.py, tests/test_pgn.py
tests/fixtures/*.pgn    (5 małych partii testowych)

$ git grep -n -I -E 'mongodb\+srv://[^"[:space:]]*:[^@"[:space:]]+@'
(brak trafień, kod wyjścia 1)
```

Prawdziwy `.env` i `certs/` są poza gitem.
