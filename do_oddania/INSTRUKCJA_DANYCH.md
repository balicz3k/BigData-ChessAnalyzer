# Dane do projektu – jak je pobrać

Danych nie załączam (5,5 GB). Są publiczne i pobiera je skrypt z projektu.

- Źródło: Lichess Open Database, https://database.lichess.org/ (licencja CC0).
- Plik: `https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst`
  (partie rankingowe z września 2026, 29,2 GB po kompresji zstd).
- Projekt używa początku tego pliku: 5 500 001 981 B po rozpakowaniu, 2 362 417 partii.

## Pobranie

W katalogu projektu (po `python3 -m venv .venv` i `.venv/bin/pip install -r requirements.txt`):

```bash
.venv/bin/python -m src.download --full   # 5,5 GB -> data/lichess_2026-09.pgn
.venv/bin/python -m src.download          # próbka 50 MB -> data/lichess_2026-09.sample.pgn
```

Skrypt czyta archiwum strumieniowo, rozpakowuje je w locie i przerywa po pierwszej
pełnej partii za progiem 5 500 000 000 B, więc nie trzeba ściągać całego miesiąca.
Ręcznie można to samo zrobić tak (wynik może się różnić o końcówkę ostatniej partii):

```bash
curl -s https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst \
  | zstd -dc | head -c 5500002000 > data/lichess_2026-09.pgn
```

Potem cały przepływ (HDFS, Hadoop, MongoDB, wykresy): `./run_all.sh` – opis w README.md.

## Dane z web scrapingu (dodatek)

Ranking FIDE pobiera `python -m src.scrape_fide` ze strony https://ratings.fide.com/
(12 list Top) do lokalnej bazy MongoDB, kolekcja `fide_top`.

## Wyniki w paczce

Wyniki jobów Hadoop z pełnych danych (126 wierszy) są w zipie z kodem w katalogu
`wyniki/full/` (pliki TSV), razem z czasami i logiem pełnego przebiegu (`wyniki/logi/`).
