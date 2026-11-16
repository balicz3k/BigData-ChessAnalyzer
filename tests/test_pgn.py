"""Parser PGN, czyszczenie nagłówków, tempo i kubełki Elo.

Definicje pochodzą z docs/DANE-I-ANALIZY.md.
"""

from __future__ import annotations

import pytest

from src import pgn
from src.pgn import (
    REJECT_ELO,
    REJECT_RESULT,
    REJECT_TIMECONTROL,
    Ply,
    elo_bucket,
    header_reject_reason,
    iter_games,
    parse_movetext,
    parse_time_control,
    tempo_class,
    tempo_of,
)

ALL_FIXTURES = ["clk_game.pgn", "eval_black_worse.pgn", "no_elo.pgn", "no_eval.pgn", "mate_eval.pgn"]


# --- podział strumienia na partie --------------------------------------------------


def test_iter_games_czyta_wszystkie_fixtury_z_jednego_strumienia(load_fixture):
    games = [g for name in ALL_FIXTURES for g in load_fixture(name)]
    assert len(games) == 5
    assert [g.headers["Site"][-8:] for g in games] == [
        "clk00001", "eval0001", "noelo001", "noeval01", "mate0001",
    ]


def test_iter_games_naglowki_i_ruchy(one_fixture):
    game = one_fixture("clk_game.pgn")
    assert game.headers["WhiteElo"] == "1500"
    assert game.headers["TimeControl"] == "180+2"
    assert game.headers["Result"] == "0-1"
    assert game.movetext.startswith("1. e4")
    assert game.movetext.endswith("0-1")


def test_iter_games_pomija_ogon_partii_bez_naglowkow():
    """Split Hadoopa może zacząć w środku partii: osierocone ruchy bez [Event] odpadają."""
    lines = [
        "12. Qd2 Bxc3 13. Qxc3 1-0",
        "",
        '[Event "x"]',
        '[Result "1-0"]',
        "",
        "1. e4 e5 1-0",
    ]
    games = list(iter_games(lines))
    assert len(games) == 1
    assert games[0].movetext == "1. e4 e5 1-0"


def test_iter_games_ostatnia_partia_bez_pustej_linii_i_crlf():
    lines = ['[Event "x"]\r', '[Result "1-0"]\r', "\r", "1. e4 e5 1-0"]
    games = list(iter_games(lines))
    assert len(games) == 1
    assert games[0].headers == {"Event": "x", "Result": "1-0"}


def test_iter_games_ruchy_w_wielu_liniach():
    lines = ['[Event "x"]', "", "1. e4 e5", "2. Nf3 Nc6 1-0"]
    (game,) = iter_games(lines)
    assert len(parse_movetext(game.movetext)) == 4


# --- półruchy -----------------------------------------------------------------------


def test_polruchy_nie_licza_numerow_komentarzy_ani_wyniku():
    plies = parse_movetext("1. e4 { [%clk 0:03:00] } 1... c5 { e4 e5 Nf3 } 2. Nf3 d6 1-0")
    assert [p.san for p in plies] == ["e4", "c5", "Nf3", "d6"]


@pytest.mark.parametrize(
    "token",
    ["e4", "Nf3", "O-O", "O-O-O", "exd5", "e8=Q+", "Nbd7", "R1a3", "Qh4xe1#", "bxa8=N", "Bxf7+"],
)
def test_wszystkie_formy_san_sa_polruchem(token):
    plies = parse_movetext(f"1. {token} 1/2-1/2")
    assert [p.san for p in plies] == [token]


@pytest.mark.parametrize("result", ["1-0", "0-1", "1/2-1/2", "*"])
def test_wynik_na_koncu_nie_jest_polruchem(result):
    assert len(parse_movetext(f"1. e4 e5 {result}")) == 2


def test_numer_ruchu_przyklejony_do_ruchu():
    assert [p.san for p in parse_movetext("1.e4 e5 2.Nf3 Nc6")] == ["e4", "e5", "Nf3", "Nc6"]


def test_adnotacje_nag_i_znaki_jakosci_nie_tworza_polruchow():
    plies = parse_movetext("1. e4 $1 e5 $2 2. Nf3! Nc6?! 1-0")
    assert [p.san for p in plies] == ["e4", "e5", "Nf3", "Nc6"]


# --- komentarze [%clk] i [%eval] ----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [("0:00:30", 30), ("0:03:00", 180), ("1:02:03", 3723), ("2:30", 150), ("0:00:09.5", 9), ("0:00:00", 0)],
)
def test_format_zegara(raw, seconds):
    (ply,) = parse_movetext(f"1. e4 {{ [%clk {raw}] }} 1-0")
    assert ply.clk == seconds


@pytest.mark.parametrize(
    ("raw", "cp", "mate"),
    [
        ("0.17", 17, None),
        ("-0.50", -50, None),
        ("0.29", 29, None),  # 0.29 * 100 w float to 28.999..., ma wyjść 29
        ("-0.00", 0, None),
        ("12.34", 1234, None),
        ("1.00,18", 100, None),  # ocena z głębokością
        ("#4", None, 4),
        ("#-4", None, -4),
    ],
)
def test_format_oceny(raw, cp, mate):
    (ply,) = parse_movetext(f"1. e4 {{ [%eval {raw}] }} 1-0")
    assert (ply.eval_cp, ply.eval_mate) == (cp, mate)


def test_komentarz_dotyczy_poprzedzajacego_polruchu():
    plies = parse_movetext(
        "1. e4 { [%eval 0.17] [%clk 0:00:30] } 1... c5 { [%eval 0.19] [%clk 0:00:29] } 2. Nf3 d6 1-0"
    )
    assert plies[0] == Ply("e4", clk=30, eval_cp=17, eval_mate=None)
    assert plies[1] == Ply("c5", clk=29, eval_cp=19, eval_mate=None)
    assert plies[2] == Ply("Nf3", clk=None, eval_cp=None, eval_mate=None)
    assert plies[3].clk is None


def test_polruch_bez_komentarza_nie_dziedziczy_zegara():
    plies = parse_movetext("1. e4 { [%clk 0:00:30] } 1... e5 2. Nf3 1-0")
    assert [p.clk for p in plies] == [30, None, None]


def test_parser_na_fixturze_z_zegarem(one_fixture):
    plies = parse_movetext(one_fixture("clk_game.pgn").movetext)
    assert len(plies) == 10
    assert [p.clk for p in plies] == [180, 180, 170, 175, 150, 170, 60, 165, 8, 160]
    assert all(p.eval_cp is None and p.eval_mate is None for p in plies)


def test_parser_na_fixturze_z_matem(one_fixture):
    plies = parse_movetext(one_fixture("mate_eval.pgn").movetext)
    assert len(plies) == 14
    assert [p.eval_mate for p in plies[-2:]] == [-4, -3]
    assert all(p.eval_cp is None for p in plies[-2:])
    assert sum(p.eval_cp is not None for p in plies) == 12


# --- czyszczenie --------------------------------------------------------------------


def test_poprawna_partia_nie_ma_powodu_odrzucenia(one_fixture):
    assert header_reject_reason(one_fixture("clk_game.pgn").headers) is None


@pytest.mark.parametrize("result", ["*", "", "1-0 ", "2-0", "draw"])
def test_zly_wynik_odrzuca(result):
    headers = {"Result": result, "WhiteElo": "1500", "BlackElo": "1500", "TimeControl": "180+0"}
    assert header_reject_reason(headers) == REJECT_RESULT


def test_brak_wyniku_odrzuca():
    headers = {"WhiteElo": "1500", "BlackElo": "1500", "TimeControl": "180+0"}
    assert header_reject_reason(headers) == REJECT_RESULT


def test_fixtura_bez_elo_jest_odrzucona(one_fixture):
    assert header_reject_reason(one_fixture("no_elo.pgn").headers) == REJECT_ELO


@pytest.mark.parametrize("bad", ["?", "", "abc", "15.5", "1500?"])
def test_elo_nieliczbowe_odrzuca(bad):
    headers = {"Result": "1-0", "WhiteElo": bad, "BlackElo": "1500", "TimeControl": "180+0"}
    assert header_reject_reason(headers) == REJECT_ELO
    headers = {"Result": "1-0", "WhiteElo": "1500", "BlackElo": bad, "TimeControl": "180+0"}
    assert header_reject_reason(headers) == REJECT_ELO


@pytest.mark.parametrize("tc", [None, "", "-", "abc", "1/86400"])
def test_zle_tempo_odrzuca(tc):
    headers = {"Result": "1-0", "WhiteElo": "1500", "BlackElo": "1500"}
    if tc is not None:
        headers["TimeControl"] = tc
    assert header_reject_reason(headers) == REJECT_TIMECONTROL


def test_kazdy_powod_odrzucenia_ma_inna_nazwe():
    assert len({REJECT_RESULT, REJECT_ELO, REJECT_TIMECONTROL}) == 3


# --- tempo --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tc", "base", "inc"),
    [("180+2", 180, 2), ("60+0", 60, 0), ("300", 300, 0), ("15+0", 15, 0), ("1800+30", 1800, 30)],
)
def test_parse_time_control(tc, base, inc):
    assert parse_time_control(tc) == (base, inc)


def test_szacowany_czas_180_plus_2_to_260_sekund():
    assert pgn.estimated_seconds(180, 2) == 260


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "ultrabullet"), (29, "ultrabullet"),
        (30, "bullet"), (179, "bullet"),
        (180, "blitz"), (479, "blitz"),
        (480, "rapid"), (1499, "rapid"),
        (1500, "classical"), (10_000, "classical"),
    ],
)
def test_granice_tempa(seconds, expected):
    assert tempo_class(seconds) == expected


@pytest.mark.parametrize(
    ("tc", "expected"),
    [("180+2", "blitz"), ("60+0", "bullet"), ("15+0", "ultrabullet"), ("600+5", "rapid"),
     ("900+10", "rapid"), ("1800+0", "classical"), ("120+1", "bullet"), ("120+2", "blitz")],
)
def test_tempo_z_naglowka(tc, expected):
    assert tempo_of({"TimeControl": tc}) == expected


@pytest.mark.parametrize(
    ("elo", "key"),
    [
        (0, "u1200"), (1199, "u1200"), (1200, "1200"), (1599, "1200"),
        (1600, "1600"), (1999, "1600"), (2000, "2000"), (2399, "2000"),
        (2400, "2400"), (3200, "2400"),
    ],
)
def test_kubelki_elo(elo, key):
    assert elo_bucket(elo) == key


def test_kubelek_ze_sredniej_nie_zaokragla_w_gore():
    assert elo_bucket((1199 + 1200) / 2) == "u1200"
