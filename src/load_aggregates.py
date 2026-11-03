"""Agregaty trzech jobów tylko do Atlasu. Metadane importu zostają lokalnie.

Puste ``ATLAS_URI`` kończy program błędem i nic nie zapisuje w innej bazie.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.aggregate import read_tsv
from src.mongo_io import DB_NAME, atlas_client, local_client, record_import, require_atlas_uri

SOURCE_MONTH = "2026-09"
FIELDS = {
    "blunder_in_trouble": ("n_moves", "n_blunders"),
    "comeback_by_tc": ("n", "comeback"),
    "think_vs_cpl": ("n_moves", "sum_cpl"),
}


def documents(analysis: str, rows) -> list[dict]:
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


def upsert_atlas(docs: list[dict]) -> int:
    client = atlas_client()
    try:
        col = client[DB_NAME]["aggregates"]
        col.create_index([("analysis", 1), ("key", 1)], unique=True, name="analysis_key")
        for doc in docs:
            col.update_one(
                {"analysis": doc["analysis"], "key": doc["key"]},
                {"$set": doc},
                upsert=True,
            )
        return col.count_documents({"source_month": SOURCE_MONTH})
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    try:
        require_atlas_uri()
    except SystemExit as exc:
        print(exc.code, file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Wgrywa agregaty jobów do Atlasu.")
    parser.add_argument("--blunder", type=Path, required=True)
    parser.add_argument("--comeback", type=Path, required=True)
    parser.add_argument("--think", type=Path, required=True)
    parser.add_argument("--hdfs-path", default="/user/chess/raw/lichess_2026-09.pgn")
    args = parser.parse_args(argv)

    grouped = {
        "blunder_in_trouble": read_tsv(args.blunder),
        "comeback_by_tc": read_tsv(args.comeback),
        "think_vs_cpl": read_tsv(args.think),
    }
    docs = [doc for name, rows in grouped.items() for doc in documents(name, rows)]
    try:
        count = upsert_atlas(docs)
    except Exception as exc:
        print(f"BŁĄD: zapis agregatów do Atlasu nie powiódł się ({type(exc).__name__})", file=sys.stderr)
        return 1

    local = local_client()
    try:
        record_import(
            local,
            "aggregates",
            source_month=SOURCE_MONTH,
            hdfs_path=args.hdfs_path,
            documents=count,
            rows=len(docs),
        )
    finally:
        local.close()
    print(f"aggregates count={count} (source_month={SOURCE_MONTH})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
