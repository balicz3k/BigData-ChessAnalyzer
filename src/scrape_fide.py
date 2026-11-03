"""Ranking FIDE do lokalnego Mongo. List bierzemy z linków, kodów nie zgadujemy.

Nazwisk nie łączymy z nickami Lichess. Drugi zapis tych samych wierszy jest upsertem
po ``(list, period, rank)`` i nie zwiększa ``count``.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterable

from src.mongo_io import DB_NAME, local_client, record_import

INDEX_URL = "https://ratings.fide.com/"
PAUSE_SECONDS = 1.0
_HEADERS = {"User-Agent": "educational-ratings-scrape/1.0"}

_HREF = re.compile(r"""href\s*=\s*['"]?([^'"\s>]+)""", re.I)
_LIST = re.compile(r"""[?&]list=([A-Za-z0-9_]+)""")
_DATA = re.compile(r"""(?:https?://ratings\.fide\.com)?(/a_top\.php\?list=([A-Za-z0-9_]+))""")
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def list_codes_from_index(html: str) -> list[str]:
    """Kody ``list=`` wyłącznie z atrybutów ``href`` (linków, nie ze skryptu)."""
    codes: list[str] = []
    seen: set[str] = set()
    for href in _HREF.findall(html):
        match = _LIST.search(href)
        if not match:
            continue
        code = match.group(1)
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def first_list_page(html: str) -> str:
    """Pierwszy link z indeksu, który wskazuje listę. Adres składamy tylko z href."""
    for href in _HREF.findall(html):
        if not _LIST.search(href):
            continue
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return "https://ratings.fide.com" + href
        return "https://ratings.fide.com/" + href
    raise ValueError("na stronie głównej nie ma linku z list=")


def ordered_data_urls(html: str, codes: Iterable[str]) -> list[str]:
    """Adresy tabel, które naprawdę występują w HTML i są na liście z indeksu.

    Kodu spoza indeksu nie bierzemy. Kodu z indeksu, którego adresu nie ma w HTML,
    nie dopisujemy z szablonu.
    """
    found: dict[str, str] = {}
    for path, code in _DATA.findall(html):
        if code in found:
            continue
        found[code] = "https://ratings.fide.com" + path if path.startswith("/") else path
    missing = [code for code in codes if code not in found]
    if missing:
        raise ValueError(
            "brak adresu tabeli w HTML dla list: "
            + ", ".join(missing)
            + ". Kodu nie zgaduję."
        )
    return [found[code] for code in codes]


def parse_period(html: str) -> str:
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(20\d{2})",
        html,
        re.I,
    )
    if not match:
        raise ValueError("brak okresu (miesiąc i rok) w HTML listy FIDE")
    month = _MONTHS[match.group(1).lower()]
    return f"{int(match.group(2)):04d}-{month:02d}"


def parse_players(html: str, list_code: str, source_url: str) -> list[dict]:
    """Wiersze jednej listy: nazwisko, federacja, ranking, rok urodzenia, miejsce."""
    from bs4 import BeautifulSoup

    period = parse_period(html)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for tr in soup.select("tr"):
        rank_el = tr.select_one("td:first-child")
        name_el = tr.select_one("a[href*='/profile/']")
        rating_el = tr.select_one(".rating_column")
        if rank_el is None or name_el is None or rating_el is None:
            continue
        fed_el = tr.select_one(".flag-wrapper")
        federation = ""
        if fed_el is not None:
            fed_match = re.search(r"\b([A-Z]{3})\b", fed_el.get_text(" ", strip=True))
            federation = fed_match.group(1) if fed_match else ""
        bday_el = tr.select_one(".bday_column")
        bday_text = bday_el.get_text(strip=True) if bday_el is not None else ""
        rating_text = rating_el.get_text(strip=True)
        if not rating_text.isdigit():
            continue
        rows.append(
            {
                "list": list_code,
                "period": period,
                "rank": int(rank_el.get_text(strip=True)),
                "name": name_el.get_text(strip=True),
                "federation": federation,
                "rating": int(rating_text),
                "birth_year": int(bday_text) if bday_text.isdigit() else None,
                "source_url": source_url,
            }
        )
    if not rows:
        raise ValueError(f"brak wierszy rankingu na liście {list_code}")
    return rows


def _get(session, url: str) -> str:
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.text


def fetch_rows(pause: float = PAUSE_SECONDS) -> list[dict]:
    """Pobiera listy odkryte na stronie głównej. Między żądaniami jest przerwa."""
    import requests

    session = requests.Session()
    session.headers.update(_HEADERS)
    index = _get(session, INDEX_URL)
    codes = list_codes_from_index(index)
    if not codes:
        raise SystemExit("BŁĄD: na stronie głównej nie ma linku z list=")
    time.sleep(pause)
    page = _get(session, first_list_page(index))
    urls = ordered_data_urls(page, codes)
    rows: list[dict] = []
    for url in urls:
        time.sleep(pause)
        code = _LIST.search(url)
        if code is None:
            raise SystemExit(f"BŁĄD: adres tabeli bez list=: {url}")
        html = _get(session, url)
        rows.extend(parse_players(html, code.group(1), url))
    return rows


def upsert_rows(rows: list[dict]) -> int:
    """Upsert po ``(list, period, rank)``. Zwraca ``count`` kolekcji po zapisie."""
    client = local_client()
    try:
        col = client[DB_NAME]["fide_top"]
        col.create_index([("list", 1), ("period", 1), ("rank", 1)], unique=True, name="list_period_rank")
        for row in rows:
            col.update_one(
                {"list": row["list"], "period": row["period"], "rank": row["rank"]},
                {"$set": row},
                upsert=True,
            )
        count = col.count_documents({})
        lists = sorted({row["list"] for row in rows})
        record_import(
            client,
            "fide_scrape",
            source_url=INDEX_URL,
            count=count,
            lists=lists,
            rows=len(rows),
        )
        return count
    finally:
        client.close()


def run(pause: float = PAUSE_SECONDS) -> int:
    return upsert_rows(fetch_rows(pause=pause))


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        count = run()
    except Exception as exc:
        print(f"BŁĄD: scrape FIDE nie powiódł się: {exc}", file=sys.stderr)
        return 1
    print(f"fide_top count={count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
