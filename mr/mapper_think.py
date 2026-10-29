#!/usr/bin/env python3
"""Mapper jobu think_vs_cpl. Wzór jest w src.analyses."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent):
        if (candidate / "src" / "analyses.py").is_file():
            entry = str(candidate)
            if entry not in sys.path:
                sys.path.insert(0, entry)
            return


_bootstrap()

from src.analyses import think_job  # noqa: E402
from src.streaming import map_games  # noqa: E402


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(map_games(sys.stdin, think_job))
