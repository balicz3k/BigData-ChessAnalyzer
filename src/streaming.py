"""Wejście i liczniki Hadoop Streaming. Wzory analiz zostają w ``src.analyses``."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator

from src.pgn import iter_games

_OFFSET = re.compile(r"^\d+\t")
COUNTER_GROUP = "chess"


def hadoop_lines(lines: Iterable[str]) -> Iterator[str]:
    """Usuwa numer bajtu, który TextInputFormat dokleja przed tabulatorem."""
    for line in lines:
        yield _OFFSET.sub("", line, count=1)


def emit_counter(name: str, amount: int = 1) -> None:
    sys.stderr.write(f"reporter:counter:{COUNTER_GROUP},{name},{amount}\n")
    sys.stderr.flush()


def emit_record(key: str, nums: tuple[int, ...]) -> None:
    print(f"{key}\t{','.join(str(num) for num in nums)}", flush=True)


def map_games(lines: Iterable[str], job) -> int:
    """Czyta partie ze stdin mappera i emituje rekordy oraz liczniki odrzuceń."""
    for game in iter_games(hadoop_lines(lines)):
        emit_counter("games")
        result = job(game)
        if result.reject:
            emit_counter(result.reject)
        for name, amount in result.counters.items():
            if amount:
                emit_counter(name, amount)
        for key, nums in result.records:
            emit_record(key, nums)
    return 0


def reduce_lines(lines: Iterable[str]) -> Iterator[str]:
    """Sumuje pogrupowane po kluczu linie ``klucz\\tliczba,liczba``."""
    current: str | None = None
    totals: list[int] = []
    for raw in lines:
        line = raw.strip("\r\n")
        if not line:
            continue
        key, sep, value = line.partition("\t")
        if not sep:
            raise ValueError(f"linia bez tabulatora: {line!r}")
        nums = [int(part) for part in value.split(",")]
        if key != current:
            if current is not None:
                yield f"{current}\t{','.join(str(num) for num in totals)}"
            current = key
            totals = nums
            continue
        if len(nums) != len(totals):
            raise ValueError(f"klucz {key} ma niespójną liczbę pól")
        for i, num in enumerate(nums):
            totals[i] += num
    if current is not None:
        yield f"{current}\t{','.join(str(num) for num in totals)}"
