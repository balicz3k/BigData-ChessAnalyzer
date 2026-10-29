"""Porównuje sumy trzech jobów z lokalnym parserem na tym samym pliku PGN."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.aggregate import JOBS, diff_totals, read_tsv, totals_for_path, totals_from_rows


def compare_job(pgn: Path, name: str, tsv: Path) -> list[str]:
    local = totals_for_path(pgn, JOBS[name])
    remote = totals_from_rows(read_tsv(tsv))
    return diff_totals(local, remote)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sumy jobów muszą równać się lokalnemu parserowi.")
    parser.add_argument("pgn", type=Path)
    parser.add_argument("--blunder", type=Path, required=True)
    parser.add_argument("--comeback", type=Path, required=True)
    parser.add_argument("--think", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = {
        "blunder_in_trouble": args.blunder,
        "comeback_by_tc": args.comeback,
        "think_vs_cpl": args.think,
    }
    failed = False
    for name, tsv in paths.items():
        diffs = compare_job(args.pgn, name, tsv)
        if diffs:
            failed = True
            print(f"BŁĄD: sumy jobu {name} różnią się od lokalnego parsera:", file=sys.stderr)
            for line in diffs:
                print(f"  {line}", file=sys.stderr)
        else:
            print(f"sumy jobu {name} są zgodne z lokalnym parserem")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
