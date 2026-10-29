#!/usr/bin/env bash
# Trzy joby Streaming na jednym pliku PGN w HDFS.
# Jeden split, żeby granica bloku nie przecięła partii w połowie.
#
# W kontenerze:
#   bash /opt/projekt/mr/run_jobs.sh /user/chess/raw/lichess_2026-09.sample.pgn /user/chess/out/sample
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
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/src"
cp "$ROOT"/src/*.py "$STAGE/src/"
cp "$ROOT/mr/reducer.py" "$STAGE/reducer.py"

hdfs dfs -test -e "$INPUT"

run_one() {
  local analysis=$1
  local mapper_name=$2
  cp "$ROOT/mr/$mapper_name" "$STAGE/mapper.py"
  hdfs dfs -rm -r -f "$OUTPUT/$analysis" >/dev/null 2>&1 || true
  echo "Start jobu $analysis"
  hadoop jar "$JAR" \
    -D mapreduce.job.name="$analysis" \
    -D mapreduce.job.reduces=1 \
    -D mapreduce.job.ubertask.enable=false \
    -D mapreduce.input.fileinputformat.split.minsize=2000000000000 \
    -D mapreduce.task.timeout=7200000 \
    -D mapreduce.map.memory.mb=1024 \
    -D mapreduce.reduce.memory.mb=512 \
    -D mapreduce.map.java.opts=-Xmx768m \
    -D yarn.app.mapreduce.am.resource.mb=768 \
    -files "$STAGE/src,$STAGE/mapper.py,$STAGE/reducer.py" \
    -mapper "python3 -u mapper.py" \
    -reducer "python3 -u reducer.py" \
    -input "$INPUT" \
    -output "$OUTPUT/$analysis"
  echo "Koniec jobu $analysis -> $OUTPUT/$analysis"
}

run_one blunder_in_trouble mapper_blunder.py
run_one comeback_by_tc mapper_comeback.py
run_one think_vs_cpl mapper_think.py
echo "Trzy joby skończone: $OUTPUT"
