#!/usr/bin/env python3
"""Mapper wszystkich trzech jobów. Nazwę analizy podajemy jako argument.

Przykład: ``python3 mapper.py comeback_by_tc``. Wzory analiz są w src/analyses.py.

Hadoop kopiuje katalog src/ do katalogu roboczego zadania (opcja -files),
a run_jobs.sh ustawia PYTHONPATH=. (opcja -cmdenv), więc zwykły import
``from src...`` działa. Lokalnie tak samo: ``PYTHONPATH=. python3 mr/mapper.py ...``.
"""

import sys

from src.aggregate import JOBS
from src.streaming import map_games

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        sys.exit("użycie: mapper.py " + "|".join(JOBS))
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(map_games(sys.stdin, JOBS[sys.argv[1]]))
