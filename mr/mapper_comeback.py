#!/usr/bin/env python3
"""Mapper jobu comeback_by_tc. Wzór jest w src.analyses."""

from __future__ import annotations

import sys
from pathlib import Path


# Hadoop Streaming uruchamia każdy worker osobno przez -files, więc nie ma
# wspólnego virtualenva. _bootstrap() kopiujemy do każdego mappera/reducera
# zamiast importować ze shared modułu — bo przy -files inne pliki .py mogą
# nie trafić na sys.path. To ograniczenie środowiska, nie błąd projektu.
def _bootstrap() -> None:
    import os
    cwd = Path(os.getcwd())
    here = Path(__file__).resolve().parent
    for candidate in (cwd, here, here.parent):
        if (candidate / "src" / "analyses.py").is_file():
            entry = str(candidate)
            if entry not in sys.path:
                sys.path.insert(0, entry)
            return


_bootstrap()

from src.analyses import comeback_job  # noqa: E402
from src.streaming import map_games  # noqa: E402


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(map_games(sys.stdin, comeback_job))
