#!/usr/bin/env python3
"""Reducer trzech jobów: sumuje liczby całkowite w pogrupowanych kluczach."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent):
        if (candidate / "src" / "streaming.py").is_file():
            entry = str(candidate)
            if entry not in sys.path:
                sys.path.insert(0, entry)
            return


_bootstrap()

from src.streaming import reduce_lines  # noqa: E402


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    for line in reduce_lines(sys.stdin):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
