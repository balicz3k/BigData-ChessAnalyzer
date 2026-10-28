# Plan implementacji

Jeden etap na jedną wiadomość do agenta. Treść wiadomości jest w `PROMPTY.md`.

Środowisko docelowe: Linux albo WSL2, Docker, Python 3.11, około 16 GB RAM. Pełny wycinek potrzebuje około 15 GB wolnego dysku. Do etapu 7 wystarcza próbka.

## Etap 0. Szkielet

Agent tworzy:

- `.gitignore` wykluczający `.env`, `data/*` poza `.gitkeep`, `certs/*.pem`, `certs/*.key`, `out/*.png`, `__pycache__/`, `.pytest_cache/`, `.venv/`
- `.env.example` z pustymi `LOCAL_MONGO_URI`, `LOCAL_MONGO_CA`, `ATLAS_URI` oraz z `PGN_URL`, `HDFS_PATH`, `DEV_MAX_BYTES=50000000`, `FULL_MIN_BYTES=5500000000`
- `requirements.txt`: `pymongo`, `requests`, `beautifulsoup4`, `matplotlib`, `pytest`
- `pytest.ini` albo konfigurację w `pyproject.toml`, tak aby `pytest` zbierał katalog `tests`
- `src/__init__.py`, `mr/.gitkeep`, `tests/.gitkeep`, `data/.gitkeep`, `out/.gitkeep`, `certs/.gitkeep`, `sprawozdanie/.gitkeep`, `scripts/.gitkeep`
- `.cursor/rules/projekt.mdc` z `alwaysApply: true` i skrótem zasad z `AGENTS.md` (miesiąc, trzy joby, brak silnika, sekrety poza gitem, tylko wskazany etap)
- skill `python-testing` w tym repozytorium, zakres Project, bez `-g`. Komenda: `npx skills add https://github.com/paldom/python-skills --skill python-testing`. Na Windowsie metoda Copy
- `docker-compose.yml` z MongoDB 7 oraz jednowęzłowym Hadoopem na oficjalnym obrazie. Wersje obrazów agent sprawdza i zapisuje w README. Skrypt `scripts/gen_certs.sh` generuje lokalne CA i certyfikat serwera. Hasło użytkownika Mongo bierze ze zmiennej środowiskowej, nie z pliku w gicie

Skończone, gdy: `pytest` kończy się kodem 0 (wolno nie mieć jeszcze testów parsera), `git status` nie pokazuje `.env` ani pem, skill leży w `.cursor/skills` albo `.agents/skills`, a README mówi, jak wystartować skład. Jeśli Docker działa, agent podnosi skład i sprawdza, że klient Pythona robi połączenie do Mongo z `tls=True` i plikiem CA. Jeśli Dockera nie ma, zapisuje to w README i nie udaje, że klaster wstaje.

## Etap 1. Parser

Najpierw fixtury w `tests/fixtures` i testy, potem `src/pgn.py` oraz `src/accuracy.py`.

Fixtury obowiązkowe:

- partia z `[%clk]` i policzalnymi półruchami
- partia z `[%eval]`, w której ruch czarnych pogarsza pozycję czarnych (ocena białych rośnie)
- partia bez Elo
- partia bez żadnego `[%eval]`
- para z matem `[%eval #-4]`, pominięta w dokładności i policzona osobno

Skończone, gdy `pytest` jest zielony i test dokładności czarnych pada, jeśli ktoś zapomni odwrócić znak oceny.

## Etap 2. Środowisko, jeśli etap 0 go nie podniósł

Doprowadzić Docker do stanu z warunku etapu 0. Uzupełnić README o komendy startu, generowania certyfikatów i zmiennych z `.env.example`.

Skończone, gdy `hdfs dfs -ls /` działa w kontenerze, a skrypt Pythona łączy się z lokalnym Mongo po TLS.

## Etap 3. Pobranie

`src/download.py`. Tryb domyślny: próbka 50 MB nieskompresowanego PGN, ucięta po kompletnej partii. Tryb `--full` kończy się błędem, gdy plik ma mniej niż 5 500 000 000 bajtów. Nie ściągać pełnego miesiąca.

Skończone, gdy próbka rozpakowuje się do samych kompletnych partii i daje się wczytać parserem z etapu 1.

## Etap 4. FIDE

`src/scrape_fide.py`. Upsert do lokalnego Mongo. Indeks unikalny `(list, period, rank)`.

Skończone, gdy drugi przebieg zostawia ten sam `count`.

## Etap 5. Hadoop na próbce

`mr/mapper_ply.py`, `mr/mapper_clock.py`, `mr/mapper_accuracy.py`, `mr/reducer.py`, `mr/run_jobs.sh`. Mappery importują parser z `src` (plik dosłany do jobu przez `-files`), nie kopiują wzorów.

Skończone, gdy trzy joby na próbce z etapu 3 dają te same sumy co ten sam parser uruchomiony lokalnie na tym pliku.

## Etap 6. Zapis agregatów

`src/load_aggregates.py` i `src/verify_idempotent.py`. Agregaty do Atlasu, metadane do `import_runs`. URI Atlasa użytkownik wstawia sam do `.env`. Bez URI skrypt ma skończyć się czytelnym błędem, a nie wpisać agregaty w inne miejsce.

Skończone, gdy weryfikacja drugiego zapisu kończy się kodem 0.

## Etap 7. Wykresy

`src/charts.py` zapisuje `out/dlugosc.png`, `out/czasowka.png`, `out/dokladnosc.png`. Osie opisane po polsku, bullet nie jest uśredniony z klasykiem.

Skończone, gdy trzy pliki powstają z wyników jobów na próbce.

## Etap 8. Pełny wycinek

Ten sam `run_jobs.sh` i ten sam loader na pliku co najmniej 5,5 GB. Logi jobów i wynik `hdfs dfs -du -h` zostają w `sprawozdanie/dowody/`.

Skończone, gdy rozmiar w HDFS spełnia próg, a trzy joby kończą się sukcesem.

## Etap 9. Sprawozdanie i prezentacja

`sprawozdanie/sprawozdanie.md` po polsku: problem, dane i pola, implementacja, uruchomienie, wyniki, ograniczenie podzbioru z `[%eval]`, brak łączenia z FIDE. Konspekt prezentacji na 8–10 minut w `sprawozdanie/prezentacja.md`.

## Podział zespołu

Osoba A: etapy 1, 3, 5, 8. Osoba B: etapy 2, 4, 6, 7, 9. Etap 0 robi ta osoba, która zakłada repozytorium.
