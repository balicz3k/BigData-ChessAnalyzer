#!/usr/bin/env bash
# Start jednowęzłowego Hadoopa w jednym kontenerze: NameNode, DataNode,
# ResourceManager, NodeManager. Konfigurację XML tworzy wcześniej entrypoint
# obrazu z docker/hadoop.env.
set -euo pipefail

NAME_DIR=/hadoop-data/name

if [ ! -w /hadoop-data ]; then
  echo "BŁĄD: /hadoop-data nie jest zapisywalny dla użytkownika $(id -un). HDFS nie ma gdzie trzymać danych." >&2
  exit 1
fi

if [ ! -d "$NAME_DIR/current" ]; then
  echo "Pierwszy start: formatuję NameNode w $NAME_DIR"
  hdfs namenode -format -nonInteractive
fi

hdfs --daemon start namenode
hdfs --daemon start datanode
yarn --daemon start resourcemanager
yarn --daemon start nodemanager

echo "Czekam, aż HDFS wyjdzie z trybu awaryjnego (safemode)..."
hdfs dfsadmin -safemode wait

# Katalog na surowy PGN. Operacja idempotentna.
hdfs dfs -mkdir -p /user/chess/raw
echo "HDFS gotowy. /user/chess/raw istnieje."

# Kontener ma żyć dopóki żyją demony; logi idą na stdout.
LOG_DIR="${HADOOP_LOG_DIR:-${HADOOP_HOME:-/opt/hadoop}/logs}"
exec tail -F "$LOG_DIR"/*.log
