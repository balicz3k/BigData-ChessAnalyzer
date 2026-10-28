"""Wspólne pomoce testowe: ładowanie fixtur i budowanie partii z listy półruchów."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.pgn import RawGame, iter_games

FIXTURES = Path(__file__).parent / "fixtures"


def _fmt_clk(seconds: int) -> str:
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def build_movetext(plies, result="1-0") -> str:
    """plies: lista krotek (san, clk_w_sekundach_lub_None, eval_jako_tekst_lub_None)."""
    parts = []
    for i, (san, clk, ev) in enumerate(plies):
        number = f"{i // 2 + 1}." if i % 2 == 0 else f"{i // 2 + 1}..."
        comment = ""
        if ev is not None:
            comment += f"[%eval {ev}] "
        if clk is not None:
            comment += f"[%clk {_fmt_clk(clk)}] "
        parts.append(f"{number} {san}" + (f" {{ {comment.strip()} }}" if comment else ""))
    parts.append(result)
    return " ".join(parts)


def build_pgn(
    movetext: str,
    *,
    result: str | None = "1-0",
    white_elo: str | None = "1500",
    black_elo: str | None = "1500",
    time_control: str | None = "180+0",
) -> str:
    headers = [("Event", "Rated Blitz game"), ("Site", "https://lichess.org/test0001")]
    headers.append(("White", "w"))
    headers.append(("Black", "b"))
    for name, value in (
        ("Result", result),
        ("WhiteElo", white_elo),
        ("BlackElo", black_elo),
        ("TimeControl", time_control),
    ):
        if value is not None:
            headers.append((name, value))
    head = "\n".join(f'[{k} "{v}"]' for k, v in headers)
    return f"{head}\n\n{movetext}\n\n"


@pytest.fixture
def load_fixture():
    """Zwraca funkcję: nazwa pliku fixtury -> lista RawGame."""

    def _load(name: str) -> list[RawGame]:
        text = (FIXTURES / name).read_text(encoding="utf-8")
        return list(iter_games(text.splitlines()))

    return _load


@pytest.fixture
def one_fixture(load_fixture):
    """Zwraca funkcję: nazwa fixtury z jedną partią -> ta partia."""

    def _one(name: str) -> RawGame:
        games = load_fixture(name)
        assert len(games) == 1, f"fixtura {name} ma mieć dokładnie jedną partię, ma {len(games)}"
        return games[0]

    return _one


@pytest.fixture
def make_game():
    """Zwraca funkcję budującą RawGame z listy półruchów i nagłówków."""

    def _make(plies, *, result="1-0", **header_kwargs) -> RawGame:
        pgn = build_pgn(build_movetext(plies, result), result=result, **header_kwargs)
        games = list(iter_games(pgn.splitlines()))
        assert len(games) == 1
        return games[0]

    return _make
