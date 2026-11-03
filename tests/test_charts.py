"""Wykresy: osobne tempa i polskie opisy osi."""

from __future__ import annotations

from src.charts import (
    LABEL_BLUNDER_Y,
    LABEL_COMEBACK_Y,
    LABEL_OK,
    LABEL_THINK_Y,
    LABEL_TROUBLE,
    TITLE_BLUNDER,
    blunder_panels,
    comeback_rates,
    plot_all,
    think_panels,
)


def test_opisy_osi_sa_po_polsku():
    assert LABEL_TROUBLE == "Pod flagą"
    assert LABEL_OK == "Z czasem"
    assert "Odsetek" in LABEL_BLUNDER_Y
    assert "Odsetek" in LABEL_COMEBACK_Y
    assert "centypion" in LABEL_THINK_Y
    assert "flag" in TITLE_BLUNDER.casefold() or "Błędy" in TITLE_BLUNDER


def test_bullet_nie_jest_srednia_z_klasykiem():
    rows = [
        ("bullet|1200|trouble", (10, 4)),
        ("classical|1200|trouble", (10, 1)),
        ("bullet|1200|ok", (10, 1)),
        ("classical|1200|ok", (10, 0)),
    ]
    panels = blunder_panels(rows)
    assert panels["bullet"]["1200"]["trouble"] == (10, 4)
    assert panels["classical"]["1200"]["trouble"] == (10, 1)
    pooled = (4 + 1) / (10 + 10)
    assert 4 / 10 != pooled


def test_powrot_i_namysl_tez_dziela_tempo():
    assert comeback_rates([("bullet", (8, 2)), ("classical", (8, 1))])["bullet"] == (8, 2)
    panels = think_panels(
        [
            ("bullet|2400|0-2", (5, 50)),
            ("classical|2400|0-2", (5, 10)),
        ]
    )
    assert panels["bullet"]["2400"]["0-2"] == (5, 50)
    assert panels["classical"]["2400"]["0-2"] == (5, 10)


def test_trzy_png(tmp_path):
    blunder = [
        ("bullet|1200|trouble", (10, 4)),
        ("bullet|1200|ok", (10, 1)),
        ("classical|2000|trouble", (8, 1)),
        ("classical|2000|ok", (8, 1)),
    ]
    comeback = [("bullet", (20, 3)), ("classical", (20, 1))]
    think = [
        ("bullet|1200|0-2", (4, 80)),
        ("bullet|1200|10+", (4, 20)),
        ("classical|2400|2-10", (4, 10)),
    ]
    plot_all(blunder, comeback, think, tmp_path)
    for name in ("blunder.png", "comeback.png", "namysl.png"):
        data = (tmp_path / name).read_bytes()
        assert data.startswith(b"\x89PNG")
