"""Sprawdza, że drugi import nie powiela danych.

Liczy dokumenty ``aggregates`` w obu bazach, wgrywa te same pliki TSV dwa razy
i porównuje liczby. Z opcją ``--fide`` to samo robi dla scrapera FIDE (dodatek).
"""

from __future__ import annotations

import argparse
import sys

from src.load_aggregates import HDFS_INPUT, add_tsv_arguments, load, read_docs
from src.mongo_io import DB_NAME, atlas_client, local_client


def count_aggregates(collection: str) -> dict[str, int]:
    counts = {}
    for name, connect in (("lokalna", local_client), ("atlas", atlas_client)):
        client = connect()
        try:
            counts[name] = client[DB_NAME][collection].count_documents({})
        finally:
            client.close()
    return counts


def drop_aggregates(collection: str) -> None:
    """Usuwa kolekcję agregatów w obu bazach (przebieg "od zera")."""
    for connect in (local_client, atlas_client):
        client = connect()
        try:
            client[DB_NAME][collection].drop()
        finally:
            client.close()


def verify_aggregates(docs: list[dict], collection: str) -> bool:
    before = count_aggregates(collection)
    first = load(docs, HDFS_INPUT, collection)
    second = load(docs, HDFS_INPUT, collection)
    print(f"{collection} przed importem:  {before}")
    print(f"{collection} po 1. imporcie:  {first}")
    print(f"{collection} po 2. imporcie:  {second}")
    expected = {"lokalna": len(docs), "atlas": len(docs)}
    if first != expected or second != expected:
        print(f"BŁĄD: oczekiwano {expected} dokumentów w każdej bazie", file=sys.stderr)
        return False
    return True


def verify_fide() -> bool:
    from src.scrape_fide import run

    first = run()
    second = run()
    print(f"fide_top po 1. przebiegu: {first}, po 2. przebiegu: {second}")
    if first == 0 or second != first:
        print("BŁĄD: scraper FIDE powielił dane albo nic nie zapisał", file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dwa importy pod rząd nie mogą zwiększyć liczby dokumentów.")
    add_tsv_arguments(parser)
    parser.add_argument("--fide", action="store_true", help="sprawdź też scraper FIDE (dodatek)")
    parser.add_argument("--od-zera", action="store_true", help="najpierw usuń kolekcję agregatów w obu bazach")
    args = parser.parse_args(argv)

    if args.od_zera:
        drop_aggregates(args.kolekcja)
        print(f"usunięto kolekcje {args.kolekcja} w obu bazach")
    ok = verify_aggregates(read_docs(args.blunder, args.comeback, args.think), args.kolekcja)
    if args.fide:
        ok = verify_fide() and ok
    if ok:
        print("OK: drugi import nie zwiększył liczby dokumentów")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
