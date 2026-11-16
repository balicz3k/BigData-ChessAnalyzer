#!/usr/bin/env bash
# Cały projekt jednym poleceniem: dane -> HDFS -> Hadoop -> MongoDB -> wykresy.
#
#   ./run_all.sh                    pełne dane 5,5 GB w 8 częściach (ok. 15 min)
#   ./run_all.sh --probka           próbka 50 MB (ok. 2 min), szybkie sprawdzenie
#   ./run_all.sh --od-zera          jak wyżej, ale najpierw czyści wyniki w HDFS
#                                   i kolekcję agregatów w obu bazach
#   ./run_all.sh --probka --od-zera
#
# Potrzebne: Docker (kontenery partie-hadoop i partie-mongo), plik .env
# (wzór w .env.example), certyfikaty z scripts/gen_certs.sh, Python 3.
# Log całego przebiegu: wyniki/logi/run_all_<tryb>.log
set -euo pipefail
cd "$(dirname "$0")"

TRYB=full
OD_ZERA=0
for arg in "$@"; do
  case $arg in
    --probka) TRYB=probka ;;
    --od-zera) OD_ZERA=1 ;;
    *) echo "Nieznana opcja: $arg (dozwolone: --probka, --od-zera)" >&2; exit 1 ;;
  esac
done

PY=.venv/bin/python
OUT_LOCAL=wyniki/$TRYB
HDFS_OUT=/user/chess/out/$TRYB
if [[ $TRYB == full ]]; then
  HDFS_IN=/user/chess/raw/lichess_2026-09        # katalog z 8 częściami
  KOLEKCJA=aggregates
else
  HDFS_IN=/user/chess/raw/lichess_2026-09.sample.pgn
  KOLEKCJA=aggregates_probka                     # próbka nie nadpisuje wyników z pełnych danych
fi

mkdir -p wyniki/logi "$OUT_LOCAL"
LOG=wyniki/logi/run_all_$TRYB.log
exec > >(tee "$LOG") 2>&1   # wszystko, co niżej, idzie też do logu

START=$SECONDS
krok() { echo; echo "=== [$(date '+%H:%M:%S')] $* ==="; }

krok "0. Środowisko: Python i kontenery"
if [[ ! -x $PY ]]; then
  python3 -m venv .venv
  $PY -m pip install -q -r requirements.txt
fi
$PY --version
docker compose up -d
for usluga in partie-mongo partie-hadoop; do
  for _ in $(seq 1 60); do
    [[ $(docker inspect -f '{{.State.Health.Status}}' $usluga) == healthy ]] && break
    sleep 5
  done
  echo "$usluga: $(docker inspect -f '{{.State.Health.Status}}' $usluga)"
done

krok "1. Testy jednostkowe"
$PY -m pytest -q

krok "2. Lokalna MongoDB: TLS z plikiem CA i logowanie SCRAM"
$PY scripts/check_mongo_tls.py

krok "3. Dane Lichess (pobranie pomijane, gdy plik już jest)"
if [[ $TRYB == full ]]; then
  $PY -m src.download --full
  ls -l data/lichess_2026-09.pgn
else
  $PY -m src.download
  ls -l data/lichess_2026-09.sample.pgn
fi

krok "4. HDFS: wgranie danych (bez powielania przy ponownym uruchomieniu)"
if [[ $TRYB == full ]]; then
  $PY -m src.split_pgn --parts 8
else
  $PY -m src.download --upload
fi
docker exec partie-hadoop hdfs dfs -ls -h "$HDFS_IN"
docker exec partie-hadoop hdfs dfs -du -s -h "$HDFS_IN"

if [[ $OD_ZERA == 1 ]]; then
  krok "4a. Od zera: usuwam stare wyniki z HDFS i z dysku"
  docker exec partie-hadoop hdfs dfs -rm -r -f -skipTrash "$HDFS_OUT"
  rm -f "$OUT_LOCAL"/*.tsv
fi

krok "5. Hadoop Streaming: trzy joby MapReduce"
docker exec partie-hadoop bash /opt/projekt/mr/run_jobs.sh "$HDFS_IN" "$HDFS_OUT"

krok "6. Wyniki z HDFS na dysk ($OUT_LOCAL)"
for analiza in blunder_in_trouble comeback_by_tc think_vs_cpl; do
  docker exec partie-hadoop hdfs dfs -cat "$HDFS_OUT/$analiza/part-00000" > "$OUT_LOCAL/$analiza.tsv"
  echo "$analiza: $(wc -l < "$OUT_LOCAL/$analiza.tsv") wierszy"
done
docker exec partie-hadoop hdfs dfs -cat "$HDFS_OUT/czasy.tsv" > "$OUT_LOCAL/czasy.tsv"
cat "$OUT_LOCAL/czasy.tsv"

if [[ $TRYB == probka ]]; then
  krok "6a. Kontrola: sumy z Hadoopa = sumy z lokalnego parsera"
  $PY -m src.compare_sums data/lichess_2026-09.sample.pgn \
    --blunder "$OUT_LOCAL/blunder_in_trouble.tsv" \
    --comeback "$OUT_LOCAL/comeback_by_tc.tsv" \
    --think "$OUT_LOCAL/think_vs_cpl.tsv"
fi

krok "7. MongoDB lokalnie i w Atlasie: import dwa razy, liczba dokumentów bez zmian"
RESET=()
[[ $OD_ZERA == 1 ]] && RESET=(--od-zera)
$PY -m src.verify_idempotent --kolekcja "$KOLEKCJA" "${RESET[@]}" \
  --blunder "$OUT_LOCAL/blunder_in_trouble.tsv" \
  --comeback "$OUT_LOCAL/comeback_by_tc.tsv" \
  --think "$OUT_LOCAL/think_vs_cpl.tsv"

krok "8. Dodatek: web scraping rankingu FIDE do lokalnej bazy"
# Moduł poboczny. Błąd strony FIDE nie przerywa głównego przepływu.
$PY -m src.scrape_fide || echo "UWAGA: scraping FIDE się nie udał (strona niedostępna?), idę dalej"

krok "9. Wykresy"
if [[ $TRYB == full ]]; then WYKRESY=plots; else WYKRESY=$OUT_LOCAL/plots; fi
$PY -m src.charts --out "$WYKRESY" \
  --blunder "$OUT_LOCAL/blunder_in_trouble.tsv" \
  --comeback "$OUT_LOCAL/comeback_by_tc.tsv" \
  --think "$OUT_LOCAL/think_vs_cpl.tsv"

krok "10. Stan baz po przebiegu"
$PY -m src.summary

echo
echo "Gotowe w $(( (SECONDS - START) / 60 )) min $(( (SECONDS - START) % 60 )) s. Log: $LOG"
