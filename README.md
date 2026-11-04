# partie-lichess

**Tempo, zegar i dokładność partii szachowych na podstawie bazy Lichess** (wrzesień 2026, licencja CC0).

Trzy joby Hadoop MapReduce liczą statystyki z surowego PGN w HDFS: długość partii wg tempa i rankingu, czasówkę wg tempa oraz dokładność wg rankingu (z gotowych `[%eval]`, bez silnika szachowego). Lokalne MongoDB trzyma ranking FIDE i metadane importu, Atlas trzyma agregaty. Definicje metryk: `docs/DANE-I-ANALIZY.md`, plan: `docs/PLAN.md`.

## Stan realizacji

| Etap | Stan |
|---|---|
| 0. Szkielet | gotowy |
| 1. Parser (`src/pgn.py`, `src/accuracy.py`) | gotowy, `pytest` zielony |
| 2. Środowisko Docker/HDFS/Mongo TLS | gotowy. `hdfs dfs -ls /` w kontenerze i `scripts/check_mongo_tls.py` kończą się kodem 0 |
| 3 i dalej | nie rozpoczęte |

## Wymagania

- Linux albo WSL2, Docker z wtyczką Compose, `openssl`, około 16 GB RAM (pełny wycinek około 15 GB dysku).
- Python 3.11 (docelowo). Kod i testy sprawdzono na Pythonie 3.14.4, składnię sprawdzono pod 3.11 (`ast`, `feature_version=(3, 11)`), ale testów pod 3.11 nie uruchamiano.
- Node.js (`npx`) tylko do instalacji skilla Cursora (patrz niżej).

## Szybki start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest          # kod wyjścia 0
```

### Zmienne środowiskowe

```bash
cp .env.example .env
# uzupełnij w .env: MONGO_ROOT_PASSWORD, LOCAL_MONGO_URI, LOCAL_MONGO_CA, a gdy dojdzie etap 6, ATLAS_URI
```

`.env` jest w `.gitignore`. Hasło wpisuj tylko tam. Przykładowy `LOCAL_MONGO_URI`:
`mongodb://admin:HASLO@localhost:27017/?authSource=admin` (TLS włącza klient, nie URI), `LOCAL_MONGO_CA=certs/ca.pem`.

### Certyfikaty TLS dla lokalnego Mongo

```bash
scripts/gen_certs.sh          # tworzy certs/ca.pem, ca.key, server.pem, server.key (poza gitem)
scripts/gen_certs.sh --force  # od nowa, nadpisuje istniejące
```

Certyfikat serwera ma SAN `localhost`, `mongo`, `127.0.0.1`. CA ma `basicConstraints` i `keyUsage`, bo Python 3.13+ weryfikuje certyfikaty ściśle i bez tych rozszerzeń odrzuca takie CA. `server.pem` ma tryb 644, żeby kontener `mongo` (inny użytkownik) mógł go odczytać. To lokalne CA do rozwoju, nie do produkcji.

### Start składu

```bash
set -a; . ./.env; set +a      # compose wymaga MONGO_ROOT_PASSWORD (albo zostaw .env w katalogu projektu)
docker compose up -d
docker compose ps             # mongo i hadoop mają być healthy
```

Sprawdzenie:

```bash
docker compose exec hadoop hdfs dfs -ls /           # HDFS odpowiada
.venv/bin/python scripts/check_mongo_tls.py         # połączenie TLS z plikiem CA, uwierzytelnienie SCRAM
```

`check_mongo_tls.py` kończy się błędem, gdy brakuje `LOCAL_MONGO_URI` albo `LOCAL_MONGO_CA`, gdy URI zawiera `tlsAllowInvalidCertificates`, gdy plik CA nie istnieje, gdy nie ma połączenia TLS i gdy klient nie jest uwierzytelniony.

## Wersje obrazów (sprawdzone na Docker Hub 15.10.2026)

| Usługa | Obraz | Uwagi |
|---|---|---|
| MongoDB | `mongo:7.0.45` | najnowsza łatka linii 7.0 |
| Hadoop | `apache/hadoop:3.4.3` | oficjalny obraz Apache, stabilna linia 3.4. Jest też 3.5.0 (kwiecień 2026), jej świadomie nie bierzemy |

Hadoop działa jako jeden kontener z NameNode, DataNode, ResourceManager i NodeManager (`docker/hadoop-start.sh`). Konfiguracja XML pochodzi ze zmiennych w `docker/hadoop.env`. Dane HDFS leżą w wolumenie `hadoop-data`, dane Mongo w `mongo-data`.

## Status uruchomienia składu

Skład został uruchomiony (Docker 29.1.3, Compose 2.40.3, 29.10.2026). `docker compose ps` pokazuje `partie-mongo` i `partie-hadoop` jako healthy.

- `docker compose exec hadoop hdfs dfs -ls /` zwraca katalog `/user`. Start tworzy też `/user/chess/raw`.
- `.venv/bin/python scripts/check_mongo_tls.py` kończy się kodem 0: TLS z weryfikacją pliku CA, użytkownik `admin` uwierzytelniony (SCRAM). Hasło bierze z `.env`.

Dwie poprawki względem szkicu z etapu 0, bez których kontenery nie przechodziły sprawdzenia:

- Mongo z `--tlsCAFile` wymagało certyfikatu klienta i zrywało połączenie mongosh oraz Pythona. W `docker-compose.yml` jest `--tlsAllowConnectionsWithoutCertificates`. Klient nadal weryfikuje certyfikat serwera plikiem CA.
- Wolumen `hadoop-data` należy do roota, obraz ma `USER=hadoop`. Kontener startuje jako root, `docker/hadoop-start.sh` oddaje `/hadoop-data` użytkownikowi `hadoop` i schodzi z uprawnień przez `runuser`. Demony piszą do `/var/log/hadoop/*.out`, a skrypt wypisuje je na stdout. W obrazie jest Python 3.10 (`/usr/bin/python3`).

## Skill `python-testing`

Plan przewiduje `npx skills add https://github.com/paldom/python-skills --skill python-testing`. Na maszynie nie było Node.js, więc pliki skilla (`SKILL.md`, skrypt audytu i trzy pliki referencyjne) pobrano ręcznie z gałęzi `main` tego samego repozytorium do `.agents/skills/python-testing/`. Zawartość jest taka sama jak po instalacji przez `npx`, ale instalator nie zostawił swoich metadanych. Po instalacji Node.js można uruchomić polecenie z planu, żeby odtworzyć je oficjalnie.

## Struktura

```text
src/pgn.py        parser PGN, czyszczenie, tempo, kubełki Elo, joby długości i zegara (dla jednej partii)
src/accuracy.py   wzory dokładności i job dokładności (dla jednej partii)
tests/            testy i fixtury PGN (tests/fixtures)
mr/               mapper_blunder.py, mapper_comeback.py, mapper_think.py, reducer.py — Hadoop Streaming (etap 5)
scripts/          gen_certs.sh, check_mongo_tls.py
docker/           konfiguracja i start Hadoopa
data/ out/ certs/ poza gitem (tylko .gitkeep)
```

## Czego nie wolno commitować

`.env`, certyfikaty i klucze, pliki PGN i `.zst` (poza fixturami w `tests/fixtures`) oraz zawartość `data/`. Pilnuje tego `.gitignore` i `tests/test_szkielet.py`.
