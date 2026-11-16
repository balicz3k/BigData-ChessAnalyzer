"""Wgrywa wyniki trzech jobów (pliki TSV z HDFS) do lokalnej bazy i do Atlasu.

Do obu baz trafiają te same dokumenty, zapisywane upsertem po unikalnym
``(analysis, key)``. Drugie uruchomienie tylko nadpisuje istniejące dokumenty,
nie dopisuje nowych. Puste ``ATLAS_URI`` kończy program błędem.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.aggregate import read_tsv
from src.mongo_io import DB_NAME, atlas_client, local_client, record_import, require_atlas_uri

SOURCE_MONTH = "2026-09"
COLLECTION = "aggregates"  # próbka z run_all.sh --probka idzie do "aggregates_probka"
HDFS_INPUT = "/user/chess/raw/lichess_2026-09"
FIELDS = {
    "blunder_in_trouble": ("n_moves", "n_blunders"),
    "comeback_by_tc": ("n", "comeback", "comeback_held"),
    "think_vs_cpl": ("n_moves", "sum_cpl"),
}


def documents(analysis: str, rows) -> list[dict]:
    """Wiersze ``klucz -> liczby`` z TSV zamienia na dokumenty z nazwanymi polami."""
    names = FIELDS[analysis]
    now = datetime.now(timezone.utc)
    docs = []
    for key, nums in rows:
        if len(nums) != len(names):
            raise ValueError(f"{analysis} klucz {key} ma {len(nums)} liczb, oczekiwano {len(names)}")
        doc = {
            "analysis": analysis,
            "key": key,
            "source_month": SOURCE_MONTH,
            "updated_at": now,
        }
        doc.update(zip(names, nums, strict=True))
        docs.append(doc)
    return docs


def upsert(client, docs: list[dict], collection: str = COLLECTION) -> int:
    """Upsert dokumentów do kolekcji agregatów. Zwraca liczbę dokumentów po zapisie."""
    col = client[DB_NAME][collection]
    col.create_index([("analysis", 1), ("key", 1)], unique=True, name="analysis_key")
    for doc in docs:
        col.update_one(
            {"analysis": doc["analysis"], "key": doc["key"]},
            {"$set": doc},
            upsert=True,
        )
    return col.count_documents({"source_month": SOURCE_MONTH})


def read_docs(blunder: Path, comeback: Path, think: Path) -> list[dict]:
    grouped = {
        "blunder_in_trouble": read_tsv(blunder),
        "comeback_by_tc": read_tsv(comeback),
        "think_vs_cpl": read_tsv(think),
    }
    return [doc for name, rows in grouped.items() for doc in documents(name, rows)]


def load(docs: list[dict], hdfs_path: str, collection: str = COLLECTION) -> dict[str, int]:
    """Zapis do obu baz. Zwraca ``{"lokalna": count, "atlas": count}``."""
    counts = {}
    for name, connect in (("lokalna", local_client), ("atlas", atlas_client)):
        client = connect()
        try:
            counts[name] = upsert(client, docs, collection)
        finally:
            client.close()

    local = local_client()
    try:
        record_import(
            local,
            collection,
            source_month=SOURCE_MONTH,
            hdfs_path=hdfs_path,
            rows=len(docs),
            documents_local=counts["lokalna"],
            documents_atlas=counts["atlas"],
        )
    finally:
        local.close()
    return counts


def add_tsv_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--blunder", type=Path, required=True)
    parser.add_argument("--comeback", type=Path, required=True)
    parser.add_argument("--think", type=Path, required=True)
    parser.add_argument("--kolekcja", default=COLLECTION, help="nazwa kolekcji (domyślnie aggregates)")


def main(argv: list[str] | None = None) -> int:
    try:
        require_atlas_uri()
    except SystemExit as exc:
        print(exc.code, file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Wgrywa agregaty jobów do lokalnej bazy i do Atlasu.")
    add_tsv_arguments(parser)
    parser.add_argument("--hdfs-path", default=HDFS_INPUT)
    args = parser.parse_args(argv)

    docs = read_docs(args.blunder, args.comeback, args.think)
    try:
        counts = load(docs, args.hdfs_path, args.kolekcja)
    except Exception as exc:
        print(f"BŁĄD: zapis agregatów nie powiódł się ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(f"{args.kolekcja}: wierszy TSV {len(docs)}, lokalna {counts['lokalna']}, atlas {counts['atlas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
