"""Podział PGN na części: cięcie tylko przed [Event i bez zgubienia bajtów."""

from __future__ import annotations

from src.pgn import iter_games
from src.split_pgn import existing_parts, split_pgn


def _game(n: int) -> str:
    return f'[Event "Gra {n}"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 1-0\n\n'


def test_czesci_zaczynaja_sie_od_partii_i_skladaja_w_calosc(tmp_path):
    source = tmp_path / "duzy.pgn"
    text = "".join(_game(n) for n in range(50))
    source.write_text(text, encoding="utf-8")
    paths = split_pgn(source, tmp_path / "parts", 4)
    assert len(paths) == 4
    joined = b"".join(p.read_bytes() for p in paths)
    assert joined == source.read_bytes()
    for path in paths:
        assert path.read_bytes().startswith(b'[Event "')
    games = sum(len(list(iter_games(p.read_text(encoding="utf-8").splitlines()))) for p in paths)
    assert games == 50


def test_gotowe_czesci_nie_sa_dzielone_drugi_raz(tmp_path):
    source = tmp_path / "duzy.pgn"
    source.write_text("".join(_game(n) for n in range(10)), encoding="utf-8")
    out = tmp_path / "parts"
    assert existing_parts(source, out, 2) is None
    split_pgn(source, out, 2)
    assert existing_parts(source, out, 2) is not None
    assert existing_parts(source, out, 3) is None
