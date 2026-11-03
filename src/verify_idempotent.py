"""Drugi przebieg nie zwiększa ``count``.

FIDE sprawdza lokalne Mongo. Agregaty wymagają ``ATLAS_URI``; puste URI jest błędem
i nie powoduje zapisu w innym miejscu.
"""

from __future__ import annotations

import sys

from src.mongo_io import DB_NAME, atlas_client, require_atlas_uri
from src.scrape_fide import run


def verify_fide() -> bool:
    first = run()
    second = run()
    print(f"FIDE count po pierwszym przebiegu: {first}")
    print(f"FIDE count po drugim przebiegu: {second}")
    if second != first:
        print(
            f"BŁĄD: drugi import zwiększył count (fide_top: {first} -> {second})",
            file=sys.stderr,
        )
        return False
    if second == 0:
        print("BŁĄD: fide_top jest puste", file=sys.stderr)
        return False
    return True


def verify_aggregates() -> bool:
    uri_error = None
    try:
        require_atlas_uri()
    except SystemExit as exc:
        uri_error = exc.code
    if uri_error:
        print(uri_error, file=sys.stderr)
        return False
    client = atlas_client()
    try:
        col = client[DB_NAME]["aggregates"]
        first = col.count_documents({})
        # Drugi odczyt po upsertach zera nowych kluczy: count ma zostać.
        # Powtórny upsert tych samych dokumentów robi load_aggregates; tutaj
        # sprawdzamy, że samo policzenie i ponowne update_one nic nie dopisuje.
        for doc in col.find({}, {"_id": 0}):
            col.update_one(
                {"analysis": doc["analysis"], "key": doc["key"]},
                {"$set": doc},
                upsert=True,
            )
        second = col.count_documents({})
    finally:
        client.close()
    print(f"aggregates count po pierwszym odczycie: {first}")
    print(f"aggregates count po drugim upsertcie: {second}")
    if first == 0:
        print("BŁĄD: aggregates jest puste", file=sys.stderr)
        return False
    if second != first:
        print(
            f"BŁĄD: drugi import zwiększył count (aggregates: {first} -> {second})",
            file=sys.stderr,
        )
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    del argv
    fide_ok = verify_fide()
    aggregates_ok = verify_aggregates()
    if fide_ok and aggregates_ok:
        print("drugi import nie zwiększył count")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
