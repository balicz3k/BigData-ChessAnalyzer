"""Próg Atlasu, kształt dokumentu i decyzja o pominięciu wysyłki do HDFS."""

from __future__ import annotations

import pytest

from src.hdfs_io import parse_du, should_skip_upload
from src.load_aggregates import SOURCE_MONTH, documents
from src.mongo_io import require_atlas_uri


def test_dokument_agregatu():
    docs = documents("blunder_in_trouble", [("blitz|1200|ok", (4, 1))])
    assert docs[0]["analysis"] == "blunder_in_trouble"
    assert docs[0]["key"] == "blitz|1200|ok"
    assert docs[0]["n_moves"] == 4
    assert docs[0]["n_blunders"] == 1
    assert docs[0]["source_month"] == SOURCE_MONTH == "2026-09"
    comeback = documents("comeback_by_tc", [("bullet", (3, 1))])
    assert comeback[0]["n"] == 3
    assert comeback[0]["comeback"] == 1


def test_pusty_atlas_uri_jest_bledem(monkeypatch):
    monkeypatch.setattr("src.mongo_io.load_dotenv", lambda path=None: None)
    monkeypatch.setenv("ATLAS_URI", "")
    with pytest.raises(SystemExit) as exc:
        require_atlas_uri()
    assert "ATLAS_URI" in str(exc.value.code)


def test_loader_nie_otwiera_bazy_gdy_atlas_pusty(monkeypatch, capsys):
    monkeypatch.setattr("src.mongo_io.load_dotenv", lambda path=None: None)
    monkeypatch.setenv("ATLAS_URI", "")

    def boom(*args, **kwargs):
        raise AssertionError("klient Mongo nie powinien powstać")

    monkeypatch.setattr("src.load_aggregates.atlas_client", boom)
    monkeypatch.setattr("src.load_aggregates.local_client", boom)
    from src.load_aggregates import main

    assert main([]) == 1
    assert "ATLAS_URI" in capsys.readouterr().err


def test_hdfs_du_i_pominiecie_tego_samego_pliku():
    assert parse_du("5500 /user/chess/raw/lichess_2026-09.pgn\n") == 5500
    assert parse_du("5500  5500  /user/chess/raw/lichess_2026-09.pgn\n") == 5500
    assert parse_du("") is None
    assert should_skip_upload("abc", 10, "abc", 10) is True
    assert should_skip_upload("abc", 10, "abc", 11) is False
    assert should_skip_upload(None, 10, "abc", 10) is False
