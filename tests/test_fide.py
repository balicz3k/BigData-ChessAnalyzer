"""Odkrywanie list FIDE z linków i parsowanie tabeli. Bez sieci i bez Mongo."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.scrape_fide import (
    first_list_page,
    list_codes_from_index,
    ordered_data_urls,
    parse_period,
    parse_players,
)

INDEX = """
<a href=/top_lists.phtml?list=open>Top Open</a>
<a href=/top_lists.phtml?list=women>Top Women</a>
<a href=/top_lists.phtml?list=men_rapid>Rapid</a>
<a href="https://www.fide.com/news/">NEWS</a>
"""

PAGE = """
$.ajax({ url: '/a_top.php?list=open', success: function(data) {} });
$.ajax({ url: '/a_top.php?list=women', success: function(data) {} });
$.ajax({ url: '/a_top.php?list=men_rapid', success: function(data) {} });
$.ajax({ url: '/a_top.php?list=made_up', success: function(data) {} });
"""

TABLE = """
<div class="title-page">Top 100 Players October 2026</div>
<table class="top_recors_table">
<tr>
<td><span class="rank_span">1</span></td>
<td><a href=/profile/1503014>Carlsen, Magnus</a></td>
<td class="flag-wrapper"><img src="/images/flags/no.svg"> NOR</td>
<td class=rating_column>2823</td>
<td class=bday_column>1990</td>
</tr>
<tr>
<td><span class="rank_span">2</span></td>
<td><a href=/profile/1>Test, Anna</a></td>
<td class="flag-wrapper"> POL</td>
<td class=rating_column>2100</td>
<td class=bday_column></td>
</tr>
</table>
"""


def test_kody_list_pochodza_z_linkow_w_kolejnosci():
    assert list_codes_from_index(INDEX) == ["open", "women", "men_rapid"]


def test_adres_tabeli_musi_byc_w_html_i_nie_zgaduje_kodu():
    codes = list_codes_from_index(INDEX)
    urls = ordered_data_urls(PAGE, codes)
    assert urls == [
        "https://ratings.fide.com/a_top.php?list=open",
        "https://ratings.fide.com/a_top.php?list=women",
        "https://ratings.fide.com/a_top.php?list=men_rapid",
    ]
    assert all("made_up" not in url for url in urls)


def test_brak_adresu_w_html_nie_sklada_kodu():
    with pytest.raises(ValueError, match="nie zgaduję"):
        ordered_data_urls("<html>brak tabeli</html>", ["open"])


def test_pierwszy_link_listy():
    assert first_list_page(INDEX) == "https://ratings.fide.com/top_lists.phtml?list=open"


def test_parser_tabeli_i_okresu():
    assert parse_period(TABLE) == "2026-10"
    rows = parse_players(TABLE, "open", "https://ratings.fide.com/a_top.php?list=open")
    assert rows[0] == {
        "list": "open",
        "period": "2026-10",
        "rank": 1,
        "name": "Carlsen, Magnus",
        "federation": "NOR",
        "rating": 2823,
        "birth_year": 1990,
        "source_url": "https://ratings.fide.com/a_top.php?list=open",
    }
    assert rows[1]["birth_year"] is None
    assert rows[1]["federation"] == "POL"
    assert rows[1]["rank"] == 2


def test_scraper_nie_czyta_partii_lichess():
    text = (Path(__file__).resolve().parent.parent / "src" / "scrape_fide.py").read_text(encoding="utf-8")
    assert "import pgn" not in text
    assert "WhiteElo" not in text
    assert "lichess.org" not in text
