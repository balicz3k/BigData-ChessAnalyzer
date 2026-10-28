"""Etap 1: dokładność ruchów z gotowych [%eval]. Wzory z docs/DANE-I-ANALIZY.md.

Oczekiwane liczby w testach fixtur policzono niezależnie od kodu produkcyjnego.
"""

from __future__ import annotations

import pytest

from src.accuracy import (
    MIN_NUMERIC_EVALS,
    accuracy_job,
    centipawn_loss,
    move_accuracy,
    win_percent,
)
from src.pgn import REJECT_ELO, REJECT_FEW_EVALS, REJECT_RESULT

# --- wzory ---------------------------------------------------------------------------


def test_win_percent_zero_to_50():
    assert win_percent(0) == pytest.approx(50.0)


def test_win_percent_jest_rosnaca_i_symetryczna():
    assert win_percent(100) == pytest.approx(59.10258971916128)
    assert win_percent(-200) == pytest.approx(32.378836251494604)
    assert win_percent(150) + win_percent(-150) == pytest.approx(100.0)
    assert win_percent(-100) < win_percent(0) < win_percent(100)


@pytest.mark.parametrize(("cp", "expected"), [(10**7, 100.0), (-(10**7), 0.0)])
def test_win_percent_nie_przepelnia_przy_skrajnych_ocenach(cp, expected):
    assert win_percent(cp) == expected


def test_dokladnosc_to_100_gdy_szansa_nie_spada():
    assert move_accuracy(46.0, 46.0) == 100.0
    assert move_accuracy(46.0, 60.0) == 100.0


def test_dokladnosc_gdy_szansa_spada():
    wb, wa = win_percent(-40), win_percent(-200)
    assert move_accuracy(wb, wa) == pytest.approx(53.04622165764779)


def test_dokladnosc_obcieta_do_zera():
    # 103.1668 * exp(-0.04354 * 100) - 3.1669 < 0, wiec wynik to 0
    assert move_accuracy(100.0, 0.0) == 0.0


def test_dokladnosc_zawsze_w_przedziale():
    for drop in [0.0, 1e-9, 0.5, 5, 20, 60, 100]:
        value = move_accuracy(100.0, 100.0 - drop)
        assert 0.0 <= value <= 100.0


@pytest.mark.parametrize(("before", "after", "loss"), [(20, -10, 30), (-40, -200, 160), (10, 50, 0), (0, 0, 0)])
def test_strata_centypionow_nie_jest_ujemna(before, after, loss):
    assert centipawn_loss(before, after) == loss


# --- job accuracy_by_elo -------------------------------------------------------------


def test_prog_dziesieciu_ocen_to_stala_ze_specyfikacji():
    assert MIN_NUMERIC_EVALS == 10


def test_fixtura_z_ocenami_czarne_pogarszaja_pozycje(one_fixture):
    """Ruch 5...Be7: ocena białych rośnie z +0,40 do +2,00, więc to strata czarnych (160 cp)."""
    result = accuracy_job(one_fixture("eval_black_worse.pgn"))
    assert result.reject is None
    records = dict(result.records)
    assert set(records) == {"2000", "1600"}  # Elo 2100 (białe) i 1900 (czarne)
    assert records["2000"] == (5, 500_000, 0)  # białe: ocena zawsze nie gorsza, 100% na każdy ruch
    assert records["1600"] == (6, 553_046, 160)  # czarne
    assert result.counters == {"mate_pairs": 0}


def test_dokladnosc_czarnych_wymaga_odwrocenia_znaku_oceny(one_fixture):
    """Test strażnik: bez odwrócenia znaku czarne miałyby stratę 60 cp i dokładność 576834/6."""
    records = dict(accuracy_job(one_fixture("eval_black_worse.pgn")).records)
    n_moves, sum_millis, sum_cpl = records["1600"]
    assert sum_cpl == 160, "strata czarnych policzona bez odwrócenia znaku (błędna wartość to 60)"
    assert sum_millis == 553_046, "dokładność czarnych policzona bez odwrócenia znaku (błędna wartość to 576834)"
    assert sum_millis / n_moves / 1000 == pytest.approx(92.1743, abs=1e-3)  # blunder obniża średnią


def test_biale_i_czarne_maja_osobne_klucze_elo(make_game):
    """Kubełek dokładności to Elo gracza, który wykonał ruch, a nie średnia z obu."""
    plies = [("e4", None, "0.2"), ("e5", None, "0.1")] * 6
    game = make_game(plies, white_elo="2500", black_elo="1000")
    assert {k for k, _ in accuracy_job(game).records} == {"2400", "u1200"}


def test_fixtura_z_matem_pomija_pary_z_matem_i_liczy_je_osobno(one_fixture):
    result = accuracy_job(one_fixture("mate_eval.pgn"))
    assert result.reject is None
    # oba klucze to "2400" (Elo 2450 i 2500), wiec porownujemy liste rekordow: białe, potem czarne
    assert result.records == (("2400", (5, 445_742, 190)), ("2400", (6, 594_180, 15)))
    assert result.counters == {"mate_pairs": 2}


def test_mat_nie_wlicza_sie_do_progu_dziesieciu_ocen(make_game):
    """9 ocen liczbowych + mat to nadal za mało."""
    plies = [("e4", None, "0.2")] * 9 + [("e5", None, "#-3")]
    result = accuracy_job(make_game(plies))
    assert result.reject == REJECT_FEW_EVALS
    assert result.records == ()


def test_dokladnie_dziesiec_ocen_wystarcza(make_game):
    plies = [("e4", None, "0.2")] * 10
    result = accuracy_job(make_game(plies))
    assert result.reject is None
    assert sum(rec[1][0] for rec in result.records) == 9  # 10 ocen to 9 par (bez pierwszego ruchu)


def test_dziewiec_ocen_to_za_malo(make_game):
    result = accuracy_job(make_game([("e4", None, "0.2")] * 9))
    assert result.reject == REJECT_FEW_EVALS


def test_fixtura_bez_ocen_jest_odrzucona(one_fixture):
    result = accuracy_job(one_fixture("no_eval.pgn"))
    assert result.records == ()
    assert result.reject == REJECT_FEW_EVALS


def test_fixtura_bez_elo_odrzucona_przed_sprawdzeniem_ocen(one_fixture):
    assert accuracy_job(one_fixture("no_elo.pgn")).reject == REJECT_ELO


def test_zly_wynik_odrzuca_partie_z_ocenami(make_game):
    plies = [("e4", None, "0.2")] * 12
    assert accuracy_job(make_game(plies, result="*")).reject == REJECT_RESULT


def test_brakujaca_ocena_w_srodku_pomija_tylko_sasiednie_pary(make_game):
    """Półruch bez [%eval] nie tworzy pary ani z poprzednim, ani z następnym ruchem."""
    plies = [("e4", None, "0.2")] * 5 + [("e5", None, None)] + [("Nf3", None, "0.2")] * 6
    result = accuracy_job(make_game(plies))
    assert result.reject is None
    assert result.counters == {"mate_pairs": 0}
    total_moves = sum(rec[1][0] for rec in result.records)
    # 12 półruchów daje 11 par (bez pierwszego ruchu); dwie sąsiadują z luką, zostaje 9
    assert total_moves == 9


def test_pierwszy_polruch_nie_ma_oceny_przed_i_jest_pominiety(make_game):
    plies = [("e4", None, "0.2")] * 10
    result = accuracy_job(make_game(plies))
    assert sum(rec[1][0] for rec in result.records) == 9


def test_strona_bez_policzonego_ruchu_nie_dostaje_rekordu(make_game):
    """Dziesięć ocen liczbowych, ale jedyna para sąsiednich ocen to ruch białych (indeksy 1 i 2).

    Pozostałe oceny leżą na co drugim półruchu, więc nie tworzą par. Czarne nie mają
    policzonego ruchu i nie dostają rekordu (specyfikacja: rekord tylko dla strony z ruchem).
    """
    with_eval = {1, 2, 4, 6, 8, 10, 12, 14, 16, 18}
    plies = [("e4", None, "0.2" if i in with_eval else None) for i in range(19)]
    result = accuracy_job(make_game(plies))
    assert result.reject is None
    assert result.records == (("1200", (1, 100_000, 0)),)
