# Dowody spełnienia wymagań (stan żywy po restarcie PC)

Zebrano: 2026-11-04, godz. 19:14–19:25 (czas lokalny PC; logi Dockera w UTC, czyli o godzinę wcześniej). PC po restarcie (uptime ok. 2 min na początku), `partie-mongo` i `partie-hadoop` w stanie healthy. Katalog projektu: `~/Documents/master-studies/BigData/ChessAnalyzer/`. Sekrety (hasła, URI) nie są nigdzie wypisane; w poleceniach poniżej URI-e są czytane z `.env` wewnątrz skryptów.

Podsumowanie: wszystkie 9 punktów OK, z jedną uwagą przy punkcie 9 (patrz niżej).

---

## 1. Dane (plik PGN)

Polecenia (2026-11-04 19:14):

```
ls -l data/lichess_2026-09.pgn
du -h data/lichess_2026-09.pgn
```

Wynik:

```
-rw-rw-r-- 1 balicz3k balicz3k 5500001981 Nov  3 22:54 data/lichess_2026-09.pgn
5,2G	data/lichess_2026-09.pgn
```

5 500 001 981 B (5,12 GiB, `du -h` zaokrągla w górę do 5,2G). Liczba partii nie była liczona od nowa. Bierzemy ją z licznika `chess.games` z historii jobów Hadoop (punkt 3): **2 362 417 partii**, 47 269 027 linii wejścia (`Map input records`). Źródło: Lichess Open Database, wrzesień 2026, CC0; SHA-256 pliku jest w lokalnej kolekcji `import_runs` (pipeline `hdfs_pgn`).

## 2. HDFS po restarcie

Polecenia (2026-11-04 19:14):

```
docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw /user/chess/out /user/chess/out/full
docker exec partie-hadoop hdfs fsck /user/chess/raw/lichess_2026-09.pgn
```

Wynik (skrót): dane **przetrwały restart**.

```
-rw-r--r--  1 root supergroup  5.1 G  2026-11-03 22:43 /user/chess/raw/lichess_2026-09.pgn
-rw-r--r--  1 root supergroup 47.7 M  2026-11-03 21:39 /user/chess/raw/lichess_2026-09.sample.pgn
-rw-r--r--  1 root supergroup  1.2 K  2026-10-29 02:54 /user/chess/raw/smoke.pgn
drwxr-xr-x  /user/chess/out/{debug2,full,sample,smoke,test_debug}
drwxr-xr-x  /user/chess/out/full/blunder_in_trouble   (22:53, _SUCCESS, part-00000 1.4 K)
drwxr-xr-x  /user/chess/out/full/comeback_by_tc       (23:03, _SUCCESS, part-00000 98 B)
drwxr-xr-x  /user/chess/out/full/think_vs_cpl         (23:14, _SUCCESS, part-00000 2.2 K)
hdfs dfs -du -h /user/chess  ->  5.2 G  /user/chess/raw
fsck: The filesystem under path '/user/chess/raw/lichess_2026-09.pgn' is HEALTHY
```

Dodatkowo: sumy kontrolne MD5 plików `part-00000` w HDFS i w `data/out/full/*/` są identyczne (blunder 5cffa327, comeback 851de058, think 139ba268).

## 3. Joby Hadoop (pełne dane 5,5 GB): mappery, reducery, splity

Źródło: historia jobów zapisana w HDFS (`/tmp/hadoop-yarn/staging/history/done_intermediate/root/*.jhist`), odczyt przez `mapred job -history all <plik.jhist>` (2026-11-04 19:19). Uwaga: po restarcie `yarn application -list -appStates ALL` jest puste (stan ResourceManagera jest w pamięci), więc ślad jobów istnieje tylko w historii w HDFS.

| Job | ID | Mapperów | Reducerów | Splitów | Czas (Submitted → Finished) | Reduce output |
|---|---|---|---|---|---|---|
| blunder_in_trouble | job_1793727633376_0008 | 1 | 1 | 1 | 22:43:25 → 22:53:41 = **10 min 13 s** | 49 wierszy |
| comeback_by_tc | job_1793727633376_0009 | 1 | 1 | 1 | 22:53:46 → 23:03:20 = **9 min 29 s** | 5 wierszy |
| think_vs_cpl | job_1793727633376_0010 | 1 | 1 | 1 | 23:03:25 → 23:14:06 = **10 min 35 s** | 72 wierszy |

Razem ok. **30 min 17 s** (od 22:43:25 do 23:14:06), 126 wierszy wyniku (49 + 5 + 72) = 126 dokumentów w Atlasie. Liczba splitów wynika z `mapreduce.input.fileinputformat.split.minsize=2000000000000` w `mr/run_jobs.sh` oraz liczników: `Launched map tasks = 1`, `Input split bytes = 105`, `Data-local map tasks = 1`; `HDFS: bytes read` = 5 500 002 086.

Liczniki (każdy job): `games` = 2 362 417; `result` = 220; `timecontrol` = 2 260. Specyficzne: blunder `no_qualifying` = 2 118 187; comeback `no_eval` = 2 036 761, `not_decisive` = 89 422; think `no_qualifying` = 2 118 187, `negative_think` = 53 315. Map output records: blunder 345 571.

Dla porównania, przebieg na próbce 47,7 MB (21 248 partii, 425 265 linii): po ok. 12–13 s na job (jobs 0005–0007), 1 mapper + 1 reducer.

## 4. Lokalna MongoDB: TLS + SCRAM

Polecenia (2026-11-04 19:20): `.venv/bin/python scripts/check_mongo_tls.py` oraz skrypt pomocniczy w `/tmp` (poza repozytorium) używający `src.mongo_io.local_client()`.

```
OK: TLS z weryfikacją certyfikatu (CA: ca.pem), uwierzytelniony jako: admin
baza: chess, kolekcje: ['fide_top', 'import_runs']
  fide_top: 1202        (indeksy: _id_, list_period_rank - unikalny)
  import_runs: 3        (pipeline: hdfs_pgn, fide_scrape, aggregates)
```

Dowody szyfrowania i uwierzytelnienia (ten sam URI, różne parametry klienta):

| Próba | Wynik |
|---|---|
| Bez TLS (`tls=False`) | NIE POŁĄCZONO: `ServerSelectionTimeoutError: localhost:27017: connection closed` |
| TLS, ale bez pliku CA (store systemowy) | NIE POŁĄCZONO: `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain` |
| TLS + CA, bez hasła | POŁĄCZENIE jest, odczyt odrzucony: `OperationFailure: Command aggregate requires authentication (code 13, Unauthorized)` |
| TLS + CA + SCRAM (URI z `.env`) | OK, `ping` = 1 (mechanizm negocjowany, `DEFAULT`, dla Mongo 7 to SCRAM-SHA-256) |

Walidacja CA włączona: `LOCAL_MONGO_URI` nie zawiera `tlsAllowInvalidCertificates` (sprawdzone programowo: False), `src/mongo_io.py` odrzuca taki URI (`_reject_insecure`), klient zawsze dostaje `tls=True, tlsCAFile=certs/ca.pem`. Serwer: `docker inspect partie-mongo` pokazuje argumenty `--auth --tlsMode requireTLS --tlsCertificateKeyFile ... --tlsCAFile ... --tlsAllowConnectionsWithoutCertificates` (ta ostatnia flaga dotyczy braku certyfikatu klienta, nie wyłącza weryfikacji certyfikatu serwera przez klienta). Port 27017 wystawiony tylko na `127.0.0.1`.

## 5. Atlas

Polecenie (2026-11-04 19:20): skrypt pomocniczy z `src.mongo_io.atlas_client()`; w wyniku tylko liczby.

```
ping: {'ok': 1}
baza: chess, kolekcje: ['aggregates']
  aggregates: 126      (blunder_in_trouble 49, comeback_by_tc 5, think_vs_cpl 72)
indeksy: _id_, analysis_key (unikalny na (analysis, key))
URI: schemat mongodb+srv, TLS włączony po stronie klienta, brak tlsAllowInvalidCertificates
```

Atlas ma tylko kolekcję `aggregates`; metadane importu (`import_runs`) i ranking FIDE są lokalnie, zgodnie z projektem.

## 6. Scraping FIDE (idempotencja)

Polecenie (2026-11-04 19:20:46): `.venv/bin/python -m src.scrape_fide` (źródło: https://ratings.fide.com/, 12 list Top: open, women, juniors, girls oraz ich blitz/rapid; upsert po `(list, period, rank)`).

```
przed:  fide_top = 1202, import_runs = 3
uruchomienie: "fide_top count=1202", czas 15 s
po:     fide_top = 1202, import_runs = 3
```

Liczba dokumentów bez zmian: 1202 przed i po. Scraper w tym przebiegu pobrał dane na żywo (strona dostępna).

## 7. Powtarzalny import agregatów

Polecenie (2026-11-04 19:21), dwa kolejne przebiegi:

```
.venv/bin/python -m src.load_aggregates \
  --blunder data/out/full/blunder_in_trouble/part-00000 \
  --comeback data/out/full/comeback_by_tc/part-00000 \
  --think data/out/full/think_vs_cpl/part-00000
```

| Moment | Atlas `aggregates` | Lokalnie `fide_top` | Lokalnie `import_runs` |
|---|---|---|---|
| przed | 126 | 1202 | 3 |
| po przebiegu 1 | 126 | 1202 | 3 |
| po przebiegu 2 | 126 | 1202 | 3 |

Wyjście obu przebiegów: `aggregates count=126 (source_month=2026-09)`. Zapis to wyłącznie upsert (`update_one(..., upsert=True)` po unikalnym `(analysis, key)`), nic nie usuwano. Skutek uboczny z założenia: odświeża się pole `updated_at` w 126 dokumentach oraz `finished_at` w dokumencie `import_runs` (pipeline `aggregates`).

## 8. Testy

Polecenie (2026-11-04 19:21): `.venv/bin/python -m pytest -q`

```
217 passed in 1.03s
```

## 9. Sekrety w repozytorium

Polecenia (2026-11-04 19:22):

```
git ls-files | grep -i env
git grep -n -I -E 'mongodb\+srv://[^"\s]*:[^@"\s]+@'
```

- `git ls-files | grep -i env` zwraca `.env.example` (szablon bez wartości) i `docker/hadoop.env` (konfiguracja Hadoopa; w pliku brak słów pass/secret/token). Prawdziwy `.env` NIE jest śledzony (`.gitignore:2`), `certs/ca.key` i `certs/*` poza gitem, `REVIEW.md` zignorowany.
- `git grep` na URI z hasłem: **brak trafień** (kod wyjścia 1).
- Dodatkowo cała historia (`git log --all -p -G...`): brak dodanych linii z URI z hasłem; w historii nie ma plików `.env`, `.pem`, `.key`, `.pgn` poza fixturami `tests/fixtures/*.pgn` (małe pliki testowe).
- Uwaga (niekrytyczna): `git status` pokazuje niezacommitowane zmiany w `README.md` i `sprawozdanie.md`. Nie commitowano niczego.

Brak znalezisk KRYTYCZNYCH.
