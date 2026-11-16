# Scenariusz pokazu (ok. 14 minut)

Projekt: BigData Chess Analyzer (Lichess wrzesień 2026, HDFS + Hadoop Streaming + MongoDB lokalnie i w Atlasie). Polecenia uruchamiane w katalogu projektu na PC: `cd ~/Documents/master-studies/BigData/ChessAnalyzer`. Slajdy: `prezentacja/prezentacja.pdf` (ta sama kolejność). Twarde liczby: `docs/DOWODY.md`.

## Zasady prowadzenia pokazu

- Pełne trzy joby na 5,5 GB trwają u nas 5 min 24 s (8 mapperów). Na żywo puszczamy cały przepływ na próbce 50 MB: `./run_all.sh --probka` (ok. 2–3 min). Wyniki z pełnych danych pokazujemy z `wyniki/full/`, z baz i z logu `wyniki/logi/run_all_full.log`.
- Hasła nie pojawiają się na ekranie: nigdy `cat .env`, `echo $ATLAS_URI`, `env`. Hasło lokalnego Mongo wpisujesz po prompcie. Terminal z dużym fontem (min. 16 pt).
- Okna przed zajęciami: 1) terminal w katalogu projektu, 2) drugi terminal z `mongosh` do lokalnej bazy, 3) przeglądarka z `localhost:9870` (NameNode) i `localhost:8088` (YARN), 4) slajdy PDF, 5) `docs/DOWODY.md` jako ściąga.

## Plan czasowy

| # | Krok (slajd) | Czas |
|---|---|---|
| 1 | Problem i dane (2) | 1:30 |
| 2 | Architektura, start `run_all.sh --probka` w tle (3) | 1:30 |
| 3 | HDFS i 8 części (4) | 1:00 |
| 4 | Hadoop Streaming: map, sortowanie, reduce, czasy (5) | 2:30 |
| 5 | Dwie bazy i ponowny import (6) | 2:00 |
| 6 | TLS i uwierzytelnienie (7) | 1:30 |
| 7 | Wyniki trzech analiz (8–10) | 2:30 |
| 8 | Wnioski, dodatek FIDE, pytania (11–12) | 1:30 |
| | Razem | 14:00 |

Gdy brakuje czasu: krok 6 tylko tabela ze slajdu, krok 3 bez przeglądarki.

---

## Krok 1. Problem i dane (1:30)

Powiedz: „Trzy pytania o szachy online: czy pod presją czasu robi się więcej błędów, jak często wygrywa ten, kto przegrywał, i czy dłuższy namysł daje lepszy ruch. Dane: Lichess Open Database, wrzesień 2026, CC0, 5,5 GB tekstu PGN, 2,36 mln partii. Odpowiedzi biorę z adnotacji w pliku: zegar po każdym ruchu i ocena silnika w ok. 10% partii.”

```
ls -l data/lichess_2026-09.pgn
```

Oczekiwane: `5500001981 ... lichess_2026-09.pgn`.

## Krok 2. Architektura i start demo (1:30)

Najpierw uruchom w terminalu 1 (będzie liczyć, gdy mówisz):

```
./run_all.sh --probka
```

Powiedz (slajd z diagramem): „Pobieramy archiwum, dzielimy na 8 części, wkładamy do HDFS. Trzy joby Hadoop Streaming liczą statystyki. Wyniki, 126 wierszy, idą do dwóch baz MongoDB: lokalnej w Dockerze i Atlasa w chmurze. Z nich rysujemy wykresy. Obok, jako dodatek, scraper rankingu FIDE zapisuje dane do lokalnej bazy. Wszystko robi jeden skrypt `run_all.sh`.”

Co może pójść nie tak: brak sieci do Atlasa (krok 7 skryptu kończy się błędem). Plan B: pokazać log `wyniki/logi/run_all_probka.log` z próby generalnej.

## Krok 3. HDFS i 8 części (1:00)

```
docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw/lichess_2026-09
docker exec partie-hadoop hdfs dfs -du -s -h /user/chess/raw/lichess_2026-09
```

Oczekiwane: 8 plików `part-000.pgn` … `part-007.pgn` po ok. 655 MB, razem `5.1 G` (to 5,5 GB w jednostkach dziesiętnych). Opcjonalnie `localhost:9870` → Utilities → Browse the file system.

Powiedz: „Hadoop tnie pliki na bloki po 128 MB, a partia ma kilkanaście linii – granica bloku przecięłaby partię. Dlatego sam dzielę plik przed `[Event`, a w jobie ustawiam, żeby Hadoop nie ciął dalej. Każda część to jeden mapper.”

## Krok 4. Hadoop Streaming (2:30)

W tym czasie demo z kroku 2 jest zwykle przy jobach – pokaż w przeglądarce `localhost:8088` (aplikacja RUNNING) albo pasek `map 0% reduce 0%` → `map 100% reduce 100%` w terminalu.

Powiedz: „Mapper w Pythonie dostaje linie pliku, skleja je w partie i dla każdej wypisuje klucz i liczby, np. `blitz 1,1,0`. Hadoop sortuje po kluczu, reducer sumuje liczby o tym samym kluczu. Odsetki liczę dopiero po jobie.”

Czasy pełnego przebiegu (slajd 5): `cat wyniki/full/czasy.tsv` i `cat wyniki/jeden_mapper/czasy.tsv` → 31 min 43 s na jednym mapperze, 5 min 24 s na ośmiu. Liczniki z logu:

```
grep -E "Launched map tasks|games=|no_eval=|negative_think=" wyniki/logi/run_all_full.log
```

Oczekiwane: `Launched map tasks=8`, `games=2362417`.

## Krok 5. Dwie bazy i ponowny import (2:00)

Pokaż wynik kroku 7 demo (albo z logu pełnego przebiegu):

```
grep -E "^aggregates|^OK" wyniki/logi/run_all_full.log
.venv/bin/python -m src.summary
```

Oczekiwane: `aggregates przed importem: {'lokalna': 0, 'atlas': 0}`, po 1. i 2. imporcie 126 i 126; `OK: drugi import nie zwiększył liczby dokumentów`. `summary` pokazuje w lokalnej bazie `aggregates` 126 (+ `aggregates_probka` z demo), `import_runs`, `fide_top` 1202; w Atlasie `aggregates` 126.

Powiedz: „Unikalny indeks na (analysis, key) i upsert: drugi import nadpisuje te same dokumenty, nic się nie dubluje.”

Lokalnie w mongosh (terminal 2, hasło po prompcie):

```
docker exec -it partie-mongo mongosh --tls --tlsCAFile /certs/ca.pem -u admin --authenticationDatabase admin chess
db.aggregates.find({analysis: "comeback_by_tc"}, {_id: 0, key: 1, n: 1, comeback: 1, comeback_held: 1})
```

Dodatek FIDE w jednym zdaniu: „Do lokalnej bazy trafia też ranking FIDE ze scrapingu ratings.fide.com – to moduł dodatkowy, upsert po (lista, okres, miejsce).” `db.fide_top.find({list: "open"}, {_id: 0, rank: 1, name: 1, rating: 1}).sort({rank: 1}).limit(3)`.

Plan B przy braku sieci: `docs/DOWODY.md` punkt 6.

## Krok 6. TLS i uwierzytelnienie (1:30)

```
.venv/bin/python scripts/check_mongo_tls.py
docker inspect partie-mongo --format '{{json .Args}}'
```

Oczekiwane: `OK: TLS z weryfikacją certyfikatu (CA: ca.pem), uwierzytelniony jako: admin`; w argumentach `--auth`, `--tlsMode requireTLS`. Tabela czterech prób (bez TLS / bez CA / bez hasła / komplet) jest na slajdzie i w `DOWODY.md`.

Powiedz: „TLS szyfruje i potwierdza, że serwer jest nasz – klient sprawdza certyfikat naszym CA. Hasło (SCRAM) potwierdza, kim jest klient. Atlas: mongodb+srv, TLS domyślnie.”

## Krok 7. Wyniki (2:30)

Slajdy 8–10 (albo `plots/*.png`).

Powiedz:
1. „Pod flagą błędów jest wyraźnie więcej, np. blitz 1200–1599: 18,7% z czasem, 29,4% pod flagą.”
2. „Im szybsze tempo, tym więcej powrotów. Po recenzji dodałem wariant ostrzejszy – strata musi trwać 6 ocen z rzędu – wartości spadają, ale kierunek zostaje.”
3. „Dłuższy namysł idzie w parze z większą stratą – bo dłużej myśli się w trudnych pozycjach. To korelacja.”

Zastrzeżenie (powiedz sam): tylko partie z oceną silnika (ok. 10%), początek jednego miesiąca, kreskowane komórki to małe próby.

## Krok 8. Wnioski (1:30)

Slajd 11, potem pytania. Ściąga z pytaniami i odpowiedziami: `docs/ARCHITEKTURA_DLA_MNIE.md`, rozdział 10.

---

## Checklista przed zajęciami

- [ ] `docker ps`: `partie-mongo` i `partie-hadoop` healthy; `docker exec partie-hadoop yarn node -list` pokazuje 1 węzeł RUNNING.
- [ ] `docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw/lichess_2026-09` – 8 części.
- [ ] Internet działa; adres IP, z którego idzie pokaz, jest na liście Network Access w Atlasie.
- [ ] Próba generalna: `./run_all.sh --probka` kończy się `Gotowe`.
- [ ] Slajdy `prezentacja/prezentacja.pdf`, `plots/*.png`, `docs/DOWODY.md` otwarte.
- [ ] Jeśli pokaz z laptopa: tunel `ssh -L 9870:localhost:9870 -L 8088:localhost:8088 ...` (porty paneli są tylko na 127.0.0.1).
- [ ] Font terminala powiększony, powiadomienia wyłączone, w historii powłoki brak haseł.
- [ ] Nigdy nie podawaj `/user/chess/out/full` jako wyjścia ręcznie odpalanego jobu (skrypt kasuje katalog wyjściowy przed jobem); demo używa `/user/chess/out/probka`.
