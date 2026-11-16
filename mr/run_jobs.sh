#!/usr/bin/env bash
# Trzy joby Hadoop Streaming na danych PGN w HDFS.
#
# Wejście to plik albo katalog z częściami (src/split_pgn.py dzieli plik
# po granicach partii). split.minsize jest ogromne, więc Hadoop nie tnie
# pliku na bloki 128 MB: każdy plik wejściowy = jeden split = jeden mapper.
# Jeden plik -> 1 mapper, katalog z 8 częściami -> 8 mapperów naraz.
#
# Uruchamiać w kontenerze, np.:
#   docker exec partie-hadoop bash /opt/projekt/mr/run_jobs.sh \
#       /user/chess/raw/lichess_2026-09 /user/chess/out/full
# Czas każdego jobu trafia do <wyjście>/czasy.tsv w HDFS i na ekran.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Użycie: $0 <ścieżka-hdfs-wejścia> <katalog-hdfs-wyjścia>" >&2
  exit 1
fi

INPUT=$1
OUTPUT=$2
ROOT=/opt/projekt
JAR=/opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-3.4.3.jar
STAGE=$(mktemp -d)
TIMES=$STAGE/czasy.tsv
trap 'rm -rf "$STAGE"' EXIT

# Kopia kodu, którą Hadoop rozsyła do zadań (-files).
mkdir -p "$STAGE/src"
cp "$ROOT"/src/*.py "$STAGE/src/"
cp "$ROOT/mr/mapper.py" "$ROOT/mr/reducer.py" "$STAGE/"

hdfs dfs -test -e "$INPUT"
hdfs dfs -mkdir -p "$OUTPUT"

run_one() {
  local analysis=$1
  hdfs dfs -rm -r -f -skipTrash "$OUTPUT/$analysis" >/dev/null 2>&1 || true
  echo "Start jobu $analysis"
  local start=$SECONDS
  hadoop jar "$JAR" \
    -D mapreduce.job.name="$analysis" \
    -D mapreduce.job.reduces=1 \
    -D mapreduce.input.fileinputformat.split.minsize=2000000000000 \
    -D mapreduce.task.timeout=7200000 \
    -D mapreduce.map.memory.mb=1024 \
    -D mapreduce.map.java.opts=-Xmx512m \
    -D mapreduce.reduce.memory.mb=1024 \
    -D yarn.app.mapreduce.am.resource.mb=1024 \
    -files "$STAGE/src,$STAGE/mapper.py,$STAGE/reducer.py" \
    -cmdenv PYTHONPATH=. \
    -mapper "python3 mapper.py $analysis" \
    -reducer "python3 reducer.py" \
    -input "$INPUT" \
    -output "$OUTPUT/$analysis"
  local took=$((SECONDS - start))
  printf '%s\t%s\t%s\n' "$analysis" "$INPUT" "$took" >> "$TIMES"
  echo "Koniec jobu $analysis -> $OUTPUT/$analysis (${took} s)"
}

run_one blunder_in_trouble
run_one comeback_by_tc
run_one think_vs_cpl

hdfs dfs -put -f "$TIMES" "$OUTPUT/czasy.tsv"
echo "Trzy joby skończone: $OUTPUT"
cat "$TIMES"
