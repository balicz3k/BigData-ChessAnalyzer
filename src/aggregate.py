"""Sumowanie rekordów trzech analiz i porównanie z plikiem TSV jobu."""

from __future__ import annotations

from pathlib import Path

from src.analyses import blunder_job, comeback_job, think_job
from src.pgn import iter_games

JOBS = {
    "blunder_in_trouble": blunder_job,
    "comeback_by_tc": comeback_job,
    "think_vs_cpl": think_job,
}


def add_records(totals: dict[str, list[int]], records) -> None:
    for key, nums in records:
        acc = totals.get(key)
        if acc is None:
            totals[key] = list(nums)
            continue
        if len(acc) != len(nums):
            raise ValueError(f"klucz {key} ma {len(acc)} pól, a doszedł rekord o {len(nums)}")
        for i, num in enumerate(nums):
            acc[i] += num


def totals_for_path(path: Path, job) -> dict[str, tuple[int, ...]]:
    totals: dict[str, list[int]] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for game in iter_games(fh):
            add_records(totals, job(game).records)
    return {key: tuple(nums) for key, nums in totals.items()}


def read_tsv(path: Path) -> list[tuple[str, tuple[int, ...]]]:
    rows: list[tuple[str, tuple[int, ...]]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        key, sep, value = line.partition("\t")
        if not sep:
            raise ValueError(f"linia bez tabulatora: {line!r}")
        rows.append((key, tuple(int(part) for part in value.split(","))))
    return rows


def totals_from_rows(rows: list[tuple[str, tuple[int, ...]]]) -> dict[str, tuple[int, ...]]:
    totals: dict[str, list[int]] = {}
    add_records(totals, rows)
    return {key: tuple(nums) for key, nums in totals.items()}


def diff_totals(local: dict[str, tuple[int, ...]], remote: dict[str, tuple[int, ...]]) -> list[str]:
    lines = []
    for key in sorted(set(local) | set(remote)):
        if local.get(key) != remote.get(key):
            lines.append(f"{key}: lokalnie {local.get(key)} job {remote.get(key)}")
    return lines
