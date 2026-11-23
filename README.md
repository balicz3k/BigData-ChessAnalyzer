# BigData Chess Analyzer

Projekt 1 z przedmiotu Big Data (Jakub Balicki). Analiza 5,5 GB partii szachowych z Lichess (wrzesień 2026, licencja CC0) w Hadoop Streaming, z wynikami w dwóch bazach MongoDB.

**Główny przepływ:** Lichess PGN → HDFS → trzy joby Hadoop Streaming (Python) → agregaty w MongoDB (lokalna z TLS i hasłem + Atlas w chmurze) → wykresy.
**Dodatek:** web scraping rankingu FIDE (ratings.fide.com) do lokalnej MongoDB.

Trzy analizy (definicje w `docs/DANE-I-ANALIZY.md`):

| Job | Pytanie |
|---|---|
| `blunder_in_trouble` | Czy pod presją czasu (≤ 10 s na zegarze) robi się więcej błędów (strata ≥ 100 centypionów)? |
| `comeback_by_tc` | Jak często wygrywa gracz, który był gorszy o co najmniej 2 piony (dwa warianty definicji)? |
| `think_vs_cpl` | Czy dłuższy namysł daje mniejszą stratę centypionów? |

Dowody spełnienia wymagań (polecenie + wynik): `docs/DOWODY.md`.

## Uruchomienie jednym poleceniem

```bash
./run_all.sh              # pełne dane 5,5 GB, 8 mapperów (ok. 15 min)
./run_all.sh --probka     # próbka 50 MB, ok. 2 min, z kontrolą sum lokalnym parserem
./run_all.sh --od-zera    # najpierw czyści wyniki w HDFS i kolekcje aggregates w obu bazach
```

Skrypt po kolei: tworzy `.venv` (jeśli go nie ma), podnosi kontenery, uruchamia testy, sprawdza połączenie TLS z lokalną bazą, pobiera dane (pomija, gdy są), dzieli PGN na 8 części i wysyła do HDFS, uruchamia trzy joby, kopiuje wyniki do `wyniki/`, importuje agregaty dwa razy do obu baz (liczba dokumentów nie może wzrosnąć), uruchamia scraper FIDE, rysuje wykresy w `plots/` i wypisuje stan baz. Log: `wyniki/logi/run_all_<tryb>.log`.

## Pierwsze przygotowanie (raz)

Wymagania: Linux (sprawdzone na Kubuntu), Docker z Compose, `openssl`, Python 3.11+, ok. 16 GB RAM i 25 GB wolnego dysku (PGN 5,5 GB + części 5,5 GB + HDFS 5,5 GB + obrazy Dockera). Darmowy klaster MongoDB Atlas (M0) z użytkownikiem i adresem IP komputera na liście dozwolonych.

```bash
cp .env.example .env          # uzupełnij: MONGO_ROOT_PASSWORD, LOCAL_MONGO_URI, LOCAL_MONGO_CA, ATLAS_URI
scripts/gen_certs.sh          # własne CA i certyfikat serwera Mongo w certs/ (poza gitem)
docker compose up -d          # partie-mongo i partie-hadoop, po ok. minucie "healthy"
```

Przykładowy `LOCAL_MONGO_URI`: `mongodb://admin:HASLO@localhost:27017/?authSource=admin` (TLS włącza klient), `LOCAL_MONGO_CA=certs/ca.pem`. Hasła wpisuje się tylko do `.env`.

## Dane – jak je pobrać

Danych nie ma w repozytorium (5,5 GB). Źródło: Lichess Open Database, https://database.lichess.org/ , plik `lichess_db_standard_rated_2026-09.pgn.zst` (licencja CC0).

```bash
.venv/bin/python -m src.download --full   # strumieniowo: rozpakowuje .zst w locie i kończy
                                          # po pierwszej pełnej partii za progiem 5,5 GB
.venv/bin/python -m src.download          # próbka 50 MB do szybkich testów
```

Nie trzeba ściągać całego miesiąca (29 GB spakowane, ok. 200 GB po rozpakowaniu): pobieranie przerywa się po progu. `run_all.sh` robi to samo automatycznie.

## Środowisko

| Usługa | Obraz / wersja | Uwagi |
|---|---|---|
| MongoDB lokalna | `mongo:7.0.45` | `--auth`, `--tlsMode requireTLS`, własne CA, port tylko na 127.0.0.1 |
| MongoDB w chmurze | Atlas M0 | `mongodb+srv://`, TLS domyślnie |
| Hadoop | `apache/hadoop:3.4.3` | jeden kontener: NameNode, DataNode, ResourceManager, NodeManager; YARN 10 GB / 10 rdzeni |
| Python na PC | 3.14 | pakiety w `requirements.txt` (przypięte wersje) |
| Python w kontenerze Hadoop | 3.10 | mappery i reducer używają tylko biblioteki standardowej |

Dane HDFS są w wolumenie `hadoop-data`, dane Mongo w `mongo-data` – przeżywają restart. Panele: NameNode `http://localhost:9870`, YARN `http://localhost:8088`.

## Struktura

```text
run_all.sh          cały przepływ jednym poleceniem
src/pgn.py          parser PGN, czyszczenie nagłówków, tempo, kubełki Elo
src/analyses.py     trzy analizy (blunder_job, comeback_job, think_job)
src/streaming.py    wejście/wyjście Hadoop Streaming: map_games, reduce_lines, liczniki
src/download.py     pobranie i ucięcie archiwum .zst do PGN
src/split_pgn.py    podział PGN na 8 części po granicach partii + wysyłka do HDFS
src/hdfs_io.py      polecenia hdfs dfs w kontenerze, pomijanie ponownej wysyłki
src/mongo_io.py     połączenia z bazami (TLS + CA lokalnie, mongodb+srv w Atlasie)
src/load_aggregates.py   upsert agregatów do obu baz
src/verify_idempotent.py dwa importy pod rząd, liczba dokumentów bez zmian
src/scrape_fide.py  dodatek: scraper rankingu FIDE do lokalnej bazy
src/charts.py       trzy wykresy (matplotlib)
src/aggregate.py, compare_sums.py, summary.py   sumy lokalne, kontrola zgodności, stan baz
mr/mapper.py        jeden mapper dla trzech jobów (nazwa analizy w argumencie)
mr/reducer.py       wspólny reducer sumujący
mr/run_jobs.sh      trzy joby hadoop-streaming z pomiarem czasu
scripts/            gen_certs.sh, check_mongo_tls.py
docker/             konfiguracja i start Hadoopa
tests/              testy pytest i małe pliki PGN
wyniki/             wyniki jobów (TSV), czasy i logi z pełnego przebiegu
plots/              wykresy
docs/               definicje analiz, dowody, scenariusz pokazu, opis architektury
sprawozdanie_latex/ sprawozdanie (LaTeX) i generator tabel/rysunków z wyniki/
prezentacja/        slajdy (Beamer)
```

Testy: `.venv/bin/python -m pytest -q`.

## Czego nie commitować

`.env`, certyfikaty i klucze, pliki PGN i `.zst` (poza fixturami w `tests/fixtures`), zawartość `data/`. Pilnuje tego `.gitignore` i `tests/test_szkielet.py`.
