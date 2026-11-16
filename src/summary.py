"""Krótkie podsumowanie stanu obu baz MongoDB (same liczby, bez adresów i haseł)."""

from __future__ import annotations

import sys

from src.mongo_io import DB_NAME, atlas_client, local_client


def describe(name: str, client) -> None:
    db = client[DB_NAME]
    print(f"{name}: baza {DB_NAME}")
    for col in sorted(db.list_collection_names()):
        print(f"  {col}: {db[col].count_documents({})} dokumentów")
    per_analysis = db["aggregates"].aggregate([{"$group": {"_id": "$analysis", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
    for row in per_analysis:
        print(f"    aggregates / {row['_id']}: {row['n']}")


def main() -> int:
    for name, connect in (("MongoDB lokalna (TLS + SCRAM)", local_client), ("MongoDB Atlas (mongodb+srv)", atlas_client)):
        client = connect()
        try:
            describe(name, client)
        finally:
            client.close()
    client = local_client()
    try:
        print("import_runs (metadane importów, lokalnie):")
        for doc in client[DB_NAME]["import_runs"].find({}, {"_id": 0}).sort("pipeline", 1):
            finished = doc.pop("finished_at", None)
            pipeline = doc.pop("pipeline")
            print(f"  {pipeline}: {doc} (koniec {finished:%Y-%m-%d %H:%M} UTC)" if finished else f"  {pipeline}: {doc}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
