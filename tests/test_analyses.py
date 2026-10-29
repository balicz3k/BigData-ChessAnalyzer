"""Trzy obowiązujące analizy: błąd przy fladze, powrót, czas namysłu.

Oczekiwane liczby policzono z docs/DANE-I-ANALIZY.md, niezależnie od kodu produkcyjnego.
Najpierw są te testy, potem src/analyses.py.
"""

from __future__ import annotations

import pytest

from src.analyses import (
    BLUNDER_CP,
    COMEBACK_CP,
    REJECT_NO_EVAL,
    REJECT_NO_QUALIFYING,
    REJECT_NOT_DECISIVE,
    blunder_job,
    comeback_job,
    think_bucket,
    think_job,
)
from src.pgn import REJECT_ELO, REJECT_RESULT, REJECT_TIMECONTROL, TIME_TROUBLE_SECONDS


def test_prog_bledu_i_flagi_sa_stalymi_ze_specyfikacji():
    assert BLUNDER_CP == 100
    assert TIME_TROUBLE_SECONDS == 10
    assert COMEBACK_CP == 200


def test_blad_przy_zegarze_9s(make_game):
    """Strata 150 cp przy zegarze 9 s to błąd pod flagą."""
    plies = [
        ("e4", 30, "0.50"),
        ("e5", None, "0.50"),
        ("Nf3", 9, "-1.00"),
    ]
    result = blunder_job(make_game(plies, time_control="180+0"))
    assert result.reject is None
    assert dict(result.records) == {"blitz|1200|trouble": (1, 1)}


def test_brak_bledu_przy_zegarze_11s(make_game):
    """Zegar 11 s jest poza flagą, a strata 30 cp nie jest błędem."""
    plies = [
        ("e4", 30, "0.50"),
        ("e5", None, "0.50"),
        ("Nf3", 11, "0.20"),
    ]
    result = blunder_job(make_game(plies, time_control="180+0"))
    assert result.reject is None
    records = dict(result.records)
    assert records == {"blitz|1200|ok": (1, 0)}
    assert not any(key.endswith("|trouble") for key in records)


def test_strata_100_cp_to_blad_a_99_nie(make_game):
    blunder = [
        ("e4", 30, "0.00"),
        ("e5", None, "0.00"),
        ("Nf3", 20, "-1.00"),
    ]
    quiet = [
        ("e4", 30, "0.00"),
        ("e5", None, "0.00"),
        ("Nf3", 20, "-0.99"),
    ]
    assert dict(blunder_job(make_game(blunder)).records)["blitz|1200|ok"] == (1, 1)
    assert dict(blunder_job(make_game(quiet)).records)["blitz|1200|ok"] == (1, 0)


def test_blad_czarnych_odwraca_znak_oceny(make_game):
    """Ocena białych rośnie z +0,10 do +1,20: to strata czarnych (110 cp), nie białych."""
    plies = [("e4", 30, "0.10"), ("e5", 9, "1.20")]
    records = dict(blunder_job(make_game(plies, white_elo="2100", black_elo="1900")).records)
    assert records == {"blitz|1600|trouble": (1, 1)}


def test_powrot_bialych_przy_minus_200(make_game):
    plies = [("e4", None, "-2.00"), ("e5", None, "0.30")]
    result = comeback_job(make_game(plies, result="1-0", time_control="60+0"))
    assert result.reject is None
    assert result.records == (("bullet", (1, 1)),)


def test_powrot_czarnych_przy_plus_200(make_game):
    plies = [("e4", None, "2.00"), ("e5", None, "1.00")]
    result = comeback_job(make_game(plies, result="0-1", time_control="1800+0"))
    assert result.reject is None
    assert result.records == (("classical", (1, 1)),)


def test_ocena_199_cp_nie_jest_powrotem(make_game):
    white = comeback_job(make_game([("e4", None, "-1.99")], result="1-0", time_control="60+0"))
    black = comeback_job(make_game([("e4", None, "1.99")], result="0-1", time_control="60+0"))
    assert white.records == (("bullet", (1, 0)),)
    assert black.records == (("bullet", (1, 0)),)


def test_remis_nie_wchodzi_do_powrotu(make_game):
    result = comeback_job(make_game([("e4", None, "-3.00")], result="1/2-1/2"))
    assert result.records == ()
    assert result.reject == REJECT_NOT_DECISIVE


def test_powrot_wymaga_oceny_liczbowej(make_game):
    result = comeback_job(make_game([("e4", None, "#-4")], result="1-0"))
    assert result.records == ()
    assert result.reject == REJECT_NO_EVAL


@pytest.mark.parametrize(
    ("seconds", "bucket"),
    [(0, "0-2"), (1, "0-2"), (2, "2-10"), (9, "2-10"), (10, "10+"), (40, "10+")],
)
def test_koszyki_czasu_namyslu(seconds, bucket):
    assert think_bucket(seconds) == bucket


def test_ujemny_czas_namyslu_nie_ma_koszyka():
    assert think_bucket(-1) is None


def test_czas_namyslu_z_inkrementem(make_game):
    """Drugi ruch białych: zegar spadł o 1 s, inkrement 2 s, więc namysł to 3 s (koszyk 2-10).

    Bez dodania inkrementu wyszłaby 1 s i koszyk 0-2. Strata z +0,10 do -1,00 to 110 cp.
    """
    plies = [
        ("e4", 170, "0.10"),
        ("e5", None, "0.10"),
        ("Nf3", 169, "-1.00"),
    ]
    result = think_job(make_game(plies, time_control="180+2"))
    assert result.reject is None
    assert result.counters.get("negative_think", 0) == 0
    assert dict(result.records) == {"blitz|1200|2-10": (1, 110)}


def test_pierwszy_ruch_nie_dostaje_inkrementu(make_game):
    """Pierwszy ruch czarnych: 180 − 179 = 1 s. Doliczenie inkrementu dałoby 3 s i inny koszyk."""
    plies = [("e4", 30, "0.10"), ("e5", 179, "0.10")]
    result = think_job(make_game(plies, time_control="180+2"))
    assert dict(result.records) == {"blitz|1200|0-2": (1, 0)}


def test_luka_zegara_nie_siega_do_starszego_odczytu(make_game):
    """Brak zegara na poprzednim własnym półruchu nie łączy dwóch odcinków w jeden namysł."""
    plies = [
        ("e4", 100, "0.20"),
        ("e5", 100, "0.20"),
        ("Nf3", None, "0.20"),
        ("Nc6", 90, "0.20"),
        ("Nc3", 90, "0.00"),
    ]
    result = think_job(make_game(plies, time_control="180+0"))
    assert result.reject is None
    assert result.counters.get("negative_think", 0) == 0
    assert dict(result.records) == {"blitz|1200|10+": (2, 0)}


def test_ujemny_czas_namyslu_jest_odrzucony(make_game):
    """Zegar urósł o 10 s przy inkrementie 2 s: namysł −8 s odpada i nie wchodzi do sumy straty."""
    plies = [
        ("e4", 100, "0.20"),
        ("e5", None, "0.20"),
        ("Nf3", 110, "0.00"),
    ]
    result = think_job(make_game(plies, time_control="180+2"))
    assert result.records == ()
    assert result.reject == REJECT_NO_QUALIFYING
    assert result.counters["negative_think"] == 1
    assert all(nums[1] != 20 for _, nums in result.records)


@pytest.mark.parametrize("job", [blunder_job, comeback_job, think_job])
@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"result": "*"}, REJECT_RESULT),
        ({"white_elo": None}, REJECT_ELO),
        ({"time_control": "-"}, REJECT_TIMECONTROL),
    ],
)
def test_czyszczenie_naglowka_odrzuca_przed_wzorami(make_game, job, kwargs, reason):
    game = make_game([("e4", 30, "0.20"), ("e5", 30, "-2.50")], **kwargs)
    result = job(game)
    assert result.records == ()
    assert result.reject == reason
