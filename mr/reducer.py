#!/usr/bin/env python3
"""Reducer trzech jobów: sumuje liczby w liniach o tym samym kluczu.

Hadoop przed reducerem sortuje wyjście mapperów po kluczu, więc wszystkie linie
jednego klucza przychodzą po kolei. Import ``src`` działa jak w mapper.py.
"""

import sys

from src.streaming import reduce_lines

if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    for line in reduce_lines(sys.stdin):
        print(line)
