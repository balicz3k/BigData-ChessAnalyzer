# Scenariusz pokazu (ok. 14 minut)

Projekt: BigData Chess Analyzer (Lichess wrzesień 2026, HDFS + Hadoop Streaming + MongoDB lokalnie i Atlas). Wszystkie polecenia uruchamiane są w katalogu projektu na PC: `cd ~/Documents/master-studies/BigData/ChessAnalyzer`. Twarde liczby z żywego stanu: `docs/DOWODY.md`.

## Zasady prowadzenia pokazu

- Pełny job Hadoop na 5,5 GB trwa u nas 9,5–10,5 minuty na JEDEN job (razem ok. 30 minut dla trzech, wg historii jobów z 3.11: 10:13, 9:29, 10:35). Na żywo nie uruchamiamy pełnych jobów. Na żywo: te same trzy joby na próbce 47,7 MB (ok. 12–13 s na job, ok. minuta razem). Wyniki z pełnych danych pokazujemy z HDFS, z Mongo i z zapisanych logów.
- Hasła nie pojawiają się na ekranie: nigdy `cat .env`, `echo $ATLAS_URI`, `env`. Hasło lokalnego Mongo wpisujesz po prompcie (nie widać go). Terminal z dużym fontem (min. 16 pt).
- Okna otwarte przed zajęciami (patrz checklista): 1) terminal w katalogu projektu, 2) drugi terminal z `mongosh` do lokalnej bazy, 3) przeglądarka z kartami `localhost:9870` (NameNode) i `localhost:8088` (YARN), 4) przeglądarka/przeglądarka obrazów z `plots/*.png`, 5) `docs/DOWODY.md` jako ściąga.

## Plan czasowy

| # | Krok | Czas |
|---|---|---|
| 1 | Przepływ danych (diagram słowny) | 1:30 |
| 2 | Dane i rozmiar | 1:00 |
| 3 | Import i idempotencja | 1:30 |
| 4 | Dwie bazy: lokalna i Atlas | 1:30 |
| 5 | Scraping FIDE | 1:00 |
| 6 | HDFS | 1:00 |
| 7 | Hadoop Streaming (próbka na żywo + logi pełnego przebiegu) | 2:30 |
| 8 | Agregaty w MongoDB | 1:00 |
| 9 | Szyfrowanie i uwierzytelnienie | 1:30 |
| 10 | Wykresy i wnioski | 1:30 |
| | Razem | 14:00 (zapas 1 min) |

Gdy brakuje czasu, skracaj w tej kolejności: krok 5 (tylko liczba), krok 4 (tylko jedna z baz), krok 7 (bez próbki, tylko logi).

---

## Krok 1. Przepływ danych (1:30), bez poleceń

Powiedz: "Bierzemy surowy plik PGN z Lichess, 5,5 GB, 2,36 mln partii. Wkładamy go do HDFS. Trzy joby Hadoop Streaming, mapper w Pythonie liczy statystyki z każdej partii, reducer je sumuje. Wyniki, 126 wierszy, trafiają do MongoDB Atlas w chmurze. Lokalna MongoDB trzyma ranking FIDE ze scrapingu i metadane importu. Na końcu wykresy."

Diagram słowny do wypowiedzenia (albo pokaż rysunek ASCII z `sprawozdanie.md`, sekcja 3):

```
Lichess PGN (5,5 GB) -> HDFS /user/chess/raw -> 3 x Hadoop Streaming (mapper -> reducer)
   -> HDFS /user/chess/out/full (TSV) -> load_aggregates -> Atlas (aggregates, 126 dok.)
                                                          -> lokalna Mongo (import_runs)
Strona FIDE (HTML) -> scraper -> lokalna Mongo (fide_top, 1202 dok.)
Wyniki TSV -> matplotlib -> plots/*.png
```

Co może pójść nie tak: nic technicznego. Plan B: wydrukowany/otwarty diagram z `sprawozdanie.md`.

## Krok 2. Dane i rozmiar (1:00)

Powiedz: "Dane to wrzesień 2026 z Lichess Open Database, licencja CC0. Po rozpakowaniu 5,5 GB, czyli ponad wymagane 5 GB."

```
ls -l data/lichess_2026-09.pgn && du -h data/lichess_2026-09.pgn
```

Oczekiwane: `5500001981 ... lichess_2026-09.pgn` i `5,2G`. (5 500 001 981 B to 5,12 GiB; `du` pokazuje 5,2G, bo zaokrągla w górę. Jeśli ktoś zapyta o różnicę, to jest ta odpowiedź.) Liczbę partii podaj z liczników Hadoopa (krok 7): 2 362 417.

Czas: 10 s. Ryzyko: brak. Plan B: zrzut ekranu z `DOWODY.md` pkt 1.

## Krok 3. Import i idempotencja (1:30)

Powiedz: "Ponowny import nie powiela danych. W HDFS plik jest nadpisywany, w Mongo robimy upsert po unikalnym kluczu. Pokażę to na agregatach: liczę dokumenty, importuję drugi raz, liczę znowu."

Najpierw stan przed i metadane importu (lokalna baza; polecenie z kroku 4, tutaj skrót):

```
.venv/bin/python -m src.load_aggregates \
  --blunder data/out/full/blunder_in_trouble/part-00000 \
  --comeback data/out/full/comeback_by_tc/part-00000 \
  --think data/out/full/think_vs_cpl/part-00000
```

Oczekiwane: `aggregates count=126 (source_month=2026-09)`. Uruchom to DWA razy pod rząd i za każdym razem to samo 126. Wyjaśnienie 1 zdaniem: unikalny indeks `analysis_key` na `(analysis, key)` i `update_one(..., upsert=True)`, więc istniejący dokument jest aktualizowany, nowy nie powstaje.

Czas: ok. 5–10 s na przebieg (wysyłka 126 upsertów do chmury). Co może pójść nie tak: brak internetu albo hasło w Atlas; komunikat `BŁĄD: zapis agregatów do Atlasu nie powiódł się`. Plan B: pokaż `DOWODY.md` pkt 7 (tabela 126/126/126) i powiedz, że to wynik z dzisiejszego uruchomienia.

## Krok 4. Dwie bazy: lokalna i Atlas (1:30)

Powiedz: "Dwie bazy. Lokalna MongoDB 7 w Dockerze, tutaj ranking FIDE i metadane importu. Chmurowa, Atlas M0, tutaj wyniki analiz."

Lokalna (terminal 2, hasło wpisz po prompcie):

```
docker exec -it partie-mongo mongosh --tls --tlsCAFile /certs/ca.pem -u admin --authenticationDatabase admin chess
```

W mongosh:

```
show collections
db.fide_top.countDocuments({})
db.import_runs.find({}, {_id: 0, pipeline: 1, count: 1, documents: 1, finished_at: 1})
```

Oczekiwane: kolekcje `fide_top`, `import_runs`; 1202; trzy dokumenty (`hdfs_pgn`, `fide_scrape`, `aggregates`).

Atlas (terminal 1; URI wczytujemy z `.env` bez wypisywania):

```
set -a; . ./.env; set +a
mongosh "$ATLAS_URI" --quiet --eval 'const d = db.getSiblingDB("chess"); printjson(d.getCollectionNames()); print(d.aggregates.countDocuments({}))'
```

Oczekiwane: `[ 'aggregates' ]` i `126`. Alternatywa: MongoDB Compass (na PC nie stwierdzono zainstalowanego Compassa, więc planem podstawowym jest mongosh; jeśli student ma Compassa na laptopie z zapisanym połączeniem do Atlasa, może pokazać kolekcję `aggregates` graficznie).

Czas: 1,5 min. Co może pójść nie tak: brak sieci do Atlasa (timeout ok. 15 s), złe hasło lokalne. Plan B: `DOWODY.md` pkt 4 i 5 albo zrzut ekranu z Atlasa (UI atlas web: Browse Collections), zrobiony przed zajęciami.

## Krok 5. Scraping (1:00)

Powiedz: "Dane z web scrapingu: ranking FIDE z ratings.fide.com, 12 list Top, parsowanie HTML Beautiful Soup. Zapis jako upsert po (lista, okres, miejsce), więc ponowne uruchomienie nie zwiększa liczby dokumentów."

```
.venv/bin/python -m src.scrape_fide
```

Oczekiwane: `fide_top count=1202` (tyle samo co przed). Czas: ok. 15 s (scraper robi przerwy między żądaniami). Co może pójść nie tak: FIDE niedostępne lub zmieniona strona; komunikat `BŁĄD: scrape FIDE nie powiódł się`. Plan B: pokaż `db.fide_top.find({list: "open"}, {_id: 0}).sort({rank: 1}).limit(3)` w mongosh (dane już są lokalnie) i powiedz, że scraper był uruchomiony wcześniej, a ten wynik 1202 jest z dzisiejszego dowodu.

## Krok 6. HDFS (1:00)

Powiedz: "Główny zbiór leży w HDFS, nie na zwykłym dysku. Jest to jednowęzłowy Hadoop 3.4.3 w Dockerze."

```
docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw
docker exec partie-hadoop hdfs dfs -du -h /user/chess
```

Oczekiwane: `lichess_2026-09.pgn` 5.1 G (to samo co 5,5 GB w jednostkach dziesiętnych), plus próbka 47.7 M. Opcjonalnie przeglądarka: `http://localhost:9870` -> Utilities -> Browse the file system -> `/user/chess/raw` (widać rozmiar i liczbę bloków).

Czas: 20 s. Ryzyko: UI na `127.0.0.1`, więc działa tylko na PC lub z tunelem `ssh -L 9870:localhost:9870 -L 8088:localhost:8088 ...`. Plan B: sam terminal (wystarcza).

## Krok 7. Hadoop Streaming (2:30)

Powiedz: "Mapper w Pythonie czyta strumień PGN ze stdin i dla każdej partii emituje klucz i liczby. Reducer sumuje liczby po kluczu. Trzy joby: błędy pod presją czasu, powroty po stratnej pozycji, czas namysłu a strata centypionów. Na żywo uruchamiam je na próbce 47 MB, bo pełny job to 10 minut."

7a. Próbka na żywo (ok. 1 min). WAŻNE: katalog wyjścia tylko `demo`, nigdy `out/full` (skrypt kasuje katalog wyjściowy przed jobem):

```
docker exec partie-hadoop bash /opt/projekt/mr/run_jobs.sh /user/chess/raw/lichess_2026-09.sample.pgn /user/chess/out/demo
```

Oczekiwane: `Start jobu blunder_in_trouble`, pasek `map 0% reduce 0%` -> `map 100% reduce 100%`, `Job ... completed successfully`, potem kolejne dwa joby i `Trzy joby skończone: /user/chess/out/demo`. W historii z 3.11 próbka trwała ok. 12–13 s na job. W tym czasie pokaż w przeglądarce `http://localhost:8088` (aplikacja RUNNING). Potem:

```
docker exec partie-hadoop hdfs dfs -cat /user/chess/out/demo/comeback_by_tc/part-00000
```

Oczekiwane: 5 wierszy (`blitz`, `bullet`, `classical`, `rapid`, `ultrabullet`) z dwiema liczbami: partie i powroty.

7b. Pełny przebieg z zapisanych logów (historia jobów w HDFS, skopiowana do plików poza repozytorium):

```
grep -E "^JobName|Submitted At|Finished At|^Status|Launched (map|reduce)|Map input records|Reduce output records|chess +\|games" ~/demo-chess/job_blunder_in_trouble_full.txt
```

Oczekiwane (blunder): `Finished At ... (10mins, 13sec)`, `SUCCEEDED`, `Launched map tasks 1`, `Launched reduce tasks 1`, `Map input records 47,269,027`, `Reduce output records 49`, `games 2,362,417`. Dla pozostałych: `job_comeback_by_tc_full.txt` (9 min 29 s, 5 wierszy), `job_think_vs_cpl_full.txt` (10 min 35 s, 72 wiersze). Pliki są kopią wyniku `mapred job -history all <plik .jhist>`; źródło w HDFS: `/tmp/hadoop-yarn/staging/history/done_intermediate/root/`.

Powiedz uczciwie o architekturze: jeden mapper i jeden reducer (`split.minsize=2e12`), bo partia PGN jest wieloliniowa i nie wolno jej przeciąć na granicy bloku; to jest świadomy kompromis, na jednym węźle i tak nie ma większej równoległości.

Czas: 2:30. Co może pójść nie tak: (1) pierwszy job po restarcie wolniejszy (zimny JVM), czekaj; (2) `yarn node -list` pusty albo kontener niezdrowy, wtedy `docker ps`; (3) ktoś uruchomi z `out/full` jako wyjściem (kasuje wyniki, trzeba je odtworzyć z `data/out/full/*`, kopie lokalne istnieją). Plan B: pomiń 7a i pokaż 7b oraz `hdfs dfs -ls -R /user/chess/out/full` (trzy katalogi z `_SUCCESS`) i `-cat` jednego `part-00000`.

## Krok 8. Agregaty w MongoDB (1:00)

Powiedz: "Wyniki jobów z HDFS przenosimy do Atlasa jako dokumenty: analiza, klucz i liczby. Odsetek liczymy dopiero przy odczycie."

```
mongosh "$ATLAS_URI" --quiet --eval 'const d = db.getSiblingDB("chess").aggregates; printjson(d.aggregate([{$group: {_id: "$analysis", n: {$sum: 1}}}]).toArray()); printjson(d.find({analysis: "comeback_by_tc"}, {_id: 0, key: 1, n: 1, comeback: 1}).toArray())'
```

Oczekiwane: `blunder_in_trouble` 49, `comeback_by_tc` 5, `think_vs_cpl` 72 (razem 126) i pięć dokumentów comeback, np. `blitz: n=104385, comeback=49312` (czyli 47,2%).

Czas: 20 s. Plan B: zrzut z Atlasa (Browse Collections) albo `DOWODY.md` pkt 5.

## Krok 9. Szyfrowanie i uwierzytelnienie (1:30)

Powiedz: "Lokalna Mongo wymaga TLS i hasła. Klient weryfikuje certyfikat serwera naszym własnym CA, nie wyłączamy walidacji. Atlas to mongodb+srv, czyli TLS domyślnie."

```
.venv/bin/python scripts/check_mongo_tls.py
mongosh "mongodb://127.0.0.1:27017" --quiet --eval 'db.runCommand({ping: 1})'
mongosh --tls "mongodb://127.0.0.1:27017" --quiet --eval 'db.runCommand({ping: 1})'
mongosh --tls --tlsCAFile certs/ca.pem "mongodb://127.0.0.1:27017/chess" --quiet --eval 'db.fide_top.countDocuments({})'
```

Oczekiwane: pierwsze: `OK: TLS z weryfikacją certyfikatu (CA: ca.pem), uwierzytelniony jako: admin`. Drugie (bez TLS): błąd połączenia (w teście Pythona: `connection closed`). Trzecie (TLS bez CA): błąd weryfikacji certyfikatu (`self-signed certificate in certificate chain`). Czwarte (TLS + CA, bez hasła): `requires authentication` / `Unauthorized`. Dokładne brzmienie komunikatów w `mongosh` może się nieco różnić od Pythona; sprawdź to na próbę przed zajęciami i zapisz.

Opcjonalnie pokaż konfigurację serwera: `docker inspect partie-mongo --format '{{json .Args}}'` (widać `--auth`, `--tlsMode requireTLS`). Ta komenda nie pokazuje hasła (jest w env, nie w Args), ale nie dodawaj do niej `.Config.Env`.

Czas: 1:30. Plan B: `DOWODY.md` pkt 4 (tabela czterech prób z komunikatami).

## Krok 10. Wykresy i wnioski (1:30)

Otwórz `plots/blunder.png`, `plots/comeback.png`, `plots/namysl.png` (np. `xdg-open plots/comeback.png`). Pliki są też w repozytorium.

Powiedz: "Trzy wnioski z danych. Pierwszy: pod presją czasu (zegar poniżej 10 s) odsetek poważnych błędów jest wyższy. Przykład z wyników: blitz, Elo 1200–1599, 18,7% błędów z normalnym czasem (359 076 z 1 919 137 ruchów) wobec 29,4% pod flagą (11 731 z 39 951). Drugi: odsetek powrotów z gorszej pozycji rośnie przy szybszym tempie: klasyka 40,4%, blitz 47,2%, bullet 55,7%, ultrabullet 77,2%. Trzeci: dłuższy namysł idzie w parze z większą stratą centypionów, bo gracze myślą dłużej w trudnych pozycjach."

Uczciwe zastrzeżenie (powiedz je sam, zanim zapyta prowadzący): analiza dotyczy tylko partii z adnotacją silnika `[%eval]` (podzbiór, nie losowa próba), wynik jest korelacyjny, w klasyce jest mało partii (4 394 w comeback).

Czas: 1:30. Plan B: wykresy w pliku PNG są i tak statyczne, więc nic się nie psuje; w razie braku przeglądarki obrazów pokaż je w VS Code lub z `sprawozdanie.md`.

---

## Pytania, na które trzeba być gotowym (10)

1. Dlaczego jeden mapper i jeden reducer? Czy to w ogóle jest "Big Data"? (Odp.: partia PGN to wiele linii; podział na bloki 128 MB przecinałby partie, więc `split.minsize=2e12` wymusza 1 split. To kompromis. Jeden węzeł i tak nie daje więcej równoległości. Zysk Hadoopa tu: model map-reduce, HDFS, liczniki, powtarzalność; skalowalność wymagałaby własnego `InputFormat` dzielącego po granicach partii.)
2. Skąd wiadomo, że wyniki są poprawne? (Odp.: test porównujący sumy jobów z lokalnym parserem na tym samym pliku, `src/compare_sums.py`; 217 testów jednostkowych; zgodność sum z 126 dokumentami.)
3. Jak działa idempotencja i co dokładnie się powtarza? (Odp.: unikalne indeksy `analysis_key` i `list_period_rank`, `update_one` z `upsert=True`; po drugim imporcie liczby bez zmian: 126, 1202. Zmienia się tylko `updated_at`/`finished_at`.)
4. Co oznacza "TLS + SCRAM" i skąd klient wie, że serwer jest prawdziwy? (Odp.: szyfrowanie kanału + uwierzytelnienie hasłem z wymianą wyzwań; klient weryfikuje certyfikat serwera lokalnym CA `certs/ca.pem` z SAN `localhost`/`127.0.0.1`; walidacji nie wyłączamy.)
5. Dlaczego serwer ma `--tlsAllowConnectionsWithoutCertificates`? (Odp.: wymaga TLS, ale nie certyfikatu klienta; bez tej flagi `--tlsCAFile` wymuszało certyfikaty klientów i łączenie z mongosh/Pythona się nie udawało. To nie wyłącza TLS ani weryfikacji serwera.)
6. Dlaczego surowe partie nie trafiają do Mongo? (Odp.: 5,5 GB / 2,36 mln partii nie mieści się w darmowym Atlas M0 (512 MB); do Mongo idzie wynik, 126 wierszy, a surowe dane żyją w HDFS.)
7. Po co dwie bazy i co jest gdzie? (Odp.: wymaganie oceny 4,0: lokalna + chmura. Lokalna: `fide_top` ze scrapingu i `import_runs`; chmura: `aggregates`. Nie ma łączenia danych FIDE z nickami Lichess.)
8. Skąd tylko część partii ma adnotacje silnika i czy to zniekształca wyniki? (Odp.: `[%eval]` ma podzbiór partii (liczniki: `no_eval` 2 036 761 w comeback, `no_qualifying` 2 118 187 w blunder i think z 2 362 417); to nie jest losowa próba, więc wnioski dotyczą partii analizowanych; opisane w ograniczeniach.)
9. Co to jest "błąd" i "presja czasu" w analizie? (Odp.: błąd = strata co najmniej 100 centypionów w ruchu; presja = zegar gracza 10 s lub mniej; powrót = wygrana po ocenie co najmniej 2 piony gorszej; definicje w `docs/DANE-I-ANALIZY.md`.)
10. Co się stanie po restarcie i jak odtworzyć wyniki? (Odp.: wolumeny Dockera trzymają HDFS i Mongo, dane przetrwały restart komputera; wyniki jobów są także w `data/out/full/*/part-00000`; ponowny import to ten sam `load_aggregates`. Po restarcie ResourceManager nie pamięta jobów, ale historia jest w HDFS.)

## Checklista przed zajęciami

- [ ] PC włączony, zalogowany; `docker ps` pokazuje `partie-mongo` i `partie-hadoop` jako `healthy` (po restarcie 1–2 min na zdrowie kontenerów).
- [ ] `docker exec partie-hadoop yarn node -list` pokazuje 1 węzeł `RUNNING`; `docker exec partie-hadoop hdfs dfsadmin -safemode get` -> `Safe mode is OFF`.
- [ ] `docker exec partie-hadoop hdfs dfs -ls -h /user/chess/raw` pokazuje plik 5.1 G (nie odtwarzamy go przy prezentacji: wysyłka trwa długo).
- [ ] Sieć: internet działa (Atlas, ratings.fide.com); jeśli prezentacja idzie z laptopa, sieć lokalna do PC (192.168.100.246) albo VPN działa; tunel SSH `-L 9870 -L 8088`, jeśli przeglądarka jest na laptopie (porty UI są związane z 127.0.0.1).
- [ ] Atlas: adres IP, z którego idzie pokaz, jest na Network Access allowlist (inaczej `ping` do Atlasa się nie uda w innej sieci).
- [ ] Hasło lokalnego Mongo (admin) i dostęp do Atlas pod ręką w menedżerze haseł; `.env` istnieje w katalogu projektu (nie otwieraj go na ekranie).
- [ ] Próba generalna: `.venv/bin/python -m pytest -q` (217 passed), `.venv/bin/python scripts/check_mongo_tls.py`, `.venv/bin/python -m src.load_aggregates ...` (126).
- [ ] Pliki z planem B gotowe: `~/demo-chess/job_*_full.txt` (logi trzech pełnych jobów), `plots/*.png`, `docs/DOWODY.md`, zrzut Atlasa (Browse Collections) i zrzut Compass/mongosh.
- [ ] Okna otwarte i ułożone: terminal 1 (projekt), terminal 2 (`mongosh` do lokalnej bazy, zalogowany), przeglądarka z `localhost:9870` i `localhost:8088`, obrazy wykresów, ten scenariusz.
- [ ] Font terminala powiększony, powiadomienia systemowe wyłączone, brak widocznych sekretów w historii powłoki (`history` nie zawiera haseł).
- [ ] Katalog `/user/chess/out/demo` w HDFS: jeśli istnieje po próbie, skrypt go nadpisze, to jest w porządku. Nigdy nie podawaj `/user/chess/out/full` jako wyjścia.
- [ ] Nie commitować przed pokazem zmian w `README.md` i `sprawozdanie.md`, dopóki nie zostaną przejrzane (są w `git status` jako zmienione).
