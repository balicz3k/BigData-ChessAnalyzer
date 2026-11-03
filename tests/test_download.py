"""Cięcie strumienia PGN na granicy partii i nazwa progu w błędzie."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import zstandard as zstd

from src.download import (
    DEV_MAX_BYTES,
    FULL_MIN_BYTES,
    PGN_URL,
    ThresholdError,
    cut_zst_stream,
    write_cut,
)
from src.pgn import iter_games

ROOT = Path(__file__).resolve().parent.parent

GAME_A = b'[Event "a"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n\n'
GAME_B = b'[Event "b"]\n[Result "0-1"]\n\n1. d4 d5 0-1\n\n'


def _cut(data: bytes, threshold: int) -> bytes:
    out = io.BytesIO()
    write_cut([data], out, threshold)
    return out.getvalue()


def test_adres_archiwum_jest_w_dokumencie():
    assert PGN_URL.endswith("lichess_db_standard_rated_2026-09.pgn.zst")
    assert PGN_URL in (ROOT / "docs" / "DANE-I-ANALIZY.md").read_text(encoding="utf-8")
    assert DEV_MAX_BYTES == 50_000_000
    assert FULL_MIN_BYTES == 5_500_000_000


def test_ciecie_konczy_pierwsza_partie_i_nie_rusza_nastepnej():
    out = _cut(GAME_A + GAME_B, 1)
    assert out == GAME_A
    games = list(iter_games(out.decode().splitlines()))
    assert len(games) == 1
    assert games[0].headers["Event"] == "a"
    assert "e4" in games[0].movetext


def test_prog_w_srodku_drugiej_partii_dopisuje_ja_do_konca():
    out = _cut(GAME_A + GAME_B, len(GAME_A) + 1)
    assert out == GAME_A + GAME_B
    assert len(list(iter_games(out.decode().splitlines()))) == 2


def test_nie_czyta_kolejnego_kawalka_po_progu():
    def chunks():
        yield GAME_A
        raise AssertionError("czyta archiwum poza progiem")

    out = io.BytesIO()
    total = write_cut(chunks(), out, 1)
    assert total == len(GAME_A)
    assert out.getvalue() == GAME_A


def test_nastepny_event_bez_pustej_linii_tez_ucina():
    glued = b'[Event "a"]\n\n1. e4 e5 1-0\n[Event "b"]\n\n1. d4 0-1\n\n'
    out = _cut(glued, 1)
    assert b'[Event "b"]' not in out
    assert b"1. e4 e5 1-0\n" in out


def test_zst_rozpakowuje_sie_i_parser_widzi_partie():
    blob = zstd.ZstdCompressor().compress(GAME_A + GAME_B)
    dest = io.BytesIO()
    total = cut_zst_stream(io.BytesIO(blob), dest, 1)
    assert total == len(GAME_A)
    games = list(iter_games(dest.getvalue().decode().splitlines()))
    assert [g.headers["Event"] for g in games] == ["a"]


def test_blad_progu_nazywa_full_min_bytes():
    err = ThresholdError("FULL_MIN_BYTES", FULL_MIN_BYTES, 100)
    text = str(err)
    assert "FULL_MIN_BYTES" in text
    assert "5500000000" in text
    assert "100" in text


def test_blad_progu_nazywa_dev_max_bytes():
    text = str(ThresholdError("DEV_MAX_BYTES", DEV_MAX_BYTES, 10))
    assert "DEV_MAX_BYTES" in text
    assert "50000000" in text


def test_za_krotki_strumien_nazywa_prog_i_kasuje_plik(tmp_path, monkeypatch):
    """Strumień kończy się przed progiem: błąd nazywa próg i nie zostawia pliku."""
    import requests

    blob = zstd.ZstdCompressor().compress(GAME_A)

    class Resp:
        def __init__(self):
            self.raw = io.BytesIO(blob)

        def raise_for_status(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    dest = tmp_path / "out.pgn"
    with pytest.raises(ThresholdError) as exc:
        from src.download import download_to

        download_to("http://example.invalid/x.zst", dest, 10_000, "DEV_MAX_BYTES", force=True)
    assert "DEV_MAX_BYTES" in str(exc.value)
    assert "10000" in str(exc.value)
    assert not dest.exists()
    assert not dest.with_suffix(".pgn.part").exists()
