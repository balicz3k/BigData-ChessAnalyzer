"""Parser PGN z Lichess i wspólna logika jobów długości partii oraz zegara.

To jest jedyne miejsce, w którym żyje parsowanie zapisu partii, czyszczenie nagłówków,
tempo, kubełki Elo oraz logika czasówki. Testy i mappery Hadoopa importują stąd.
Definicje metryk: docs/DANE-I-ANALIZY.md.

Kod celowo używa tylko biblioteki standardowej, bo mapper dostaje go przez ``-files``
i działa na węźle bez naszego virtualenva.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

# --- powody odrzucenia (nazwy liczników w logach MapReduce) ---------------------------

REJECT_RESULT = "result"
REJECT_ELO = "elo"
REJECT_TIMECONTROL = "timecontrol"
REJECT_NO_CLK = "no_clk"
REJECT_FEW_EVALS = "few_evals"

WHITE = "white"
BLACK = "black"

# Gracz ma czasówkę, gdy którykolwiek jego zegar jest mniejszy lub równy tej wartości.
TIME_TROUBLE_SECONDS = 10

# Rekord agregatu: klucz i stała kolejność liczb całkowitych (patrz docs/DANE-I-ANALIZY.md).
Record = tuple[str, tuple[int, ...]]

_VALID_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2"})


@dataclass(frozen=True)
class RawGame:
    """Partia z podziału strumienia: nagłówki i niesparsowany zapis ruchów."""

    headers: Mapping[str, str]
    movetext: str


@dataclass(frozen=True)
class Ply:
    """Półruch. ``clk`` w sekundach. ``eval_cp`` w centypionach z perspektywy białych.

    Mat jest w ``eval_mate`` (np. -4 dla ``#-4``), wtedy ``eval_cp`` jest ``None``.
    """

    san: str
    clk: int | None = None
    eval_cp: int | None = None
    eval_mate: int | None = None


@dataclass(frozen=True)
class JobResult:
    """Wynik jobu dla jednej partii: rekordy do wyemitowania albo powód odrzucenia."""

    records: tuple[Record, ...] = ()
    reject: str | None = None
    counters: Mapping[str, int] = field(default_factory=dict)


# --- podział strumienia na partie -------------------------------------------------------

_HEADER_LINE = re.compile(r'^\[(\w+)\s+"(.*)"\]$')


def iter_games(lines: Iterable[str]) -> Iterator[RawGame]:
    """Dzieli strumień linii PGN na partie.

    Partia zaczyna się od linii ``[Event "``. Linie przed pierwszym ``[Event`` to ogon
    partii z poprzedniego splitu Hadoopa i są pomijane, bo nie mają nagłówków.
    """
    headers: dict[str, str] | None = None
    parts: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith('[Event "'):
            if headers is not None:
                yield RawGame(headers, " ".join(parts))
            headers, parts = {}, []
        elif headers is None or not line:
            continue  # ogon poprzedniego splitu albo pusta linia
        elif parts or not line.startswith("["):
            parts.append(line)  # linia ruchów
            continue
        # tu trafia nowa linia [Event ...] oraz kolejne nagłówki przed ruchami
        match = _HEADER_LINE.match(line)
        if match:
            headers[match.group(1)] = match.group(2)

    if headers is not None:
        yield RawGame(headers, " ".join(parts))


# --- zapis ruchów -----------------------------------------------------------------------

# komentarz w klamrach albo dowolny token bez białych znaków i klamry
_TOKEN = re.compile(r"\{([^}]*)\}|([^\s{]+)")
_MOVE_NUMBER = re.compile(r"^\d+\.+")
_SAN = re.compile(
    r"^(?P<san>(?:O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)[+#]?)[?!]{0,2}$"
)
_MOVETEXT_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2", "*"})
_CLK = re.compile(r"\[%clk\s+(\d+):(\d{2})(?::(\d{2}))?(?:\.\d+)?\]")
_EVAL = re.compile(r"\[%eval\s+(#)?([+-]?\d+(?:\.\d+)?)(?:,\d+)?\]")


def _parse_clk(comment: str) -> int | None:
    match = _CLK.search(comment)
    if not match:
        return None
    first, second, third = match.groups()
    if third is None:  # M:SS
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)  # H:MM:SS


def _parse_eval(comment: str) -> tuple[int | None, int | None]:
    """Zwraca (centypiony, mat). Dokładnie jedno z nich jest ustawione, gdy jest ocena."""
    match = _EVAL.search(comment)
    if not match:
        return None, None
    is_mate, number = match.groups()
    if is_mate:
        return None, int(float(number))
    return int(round(float(number) * 100)), None


def parse_movetext(movetext: str) -> list[Ply]:
    """Zamienia zapis ruchów na listę półruchów razem z ich komentarzami.

    Półruch to token SAN. Numery ruchów, wynik i adnotacje ($n, !, ?) nie są półruchami.
    Komentarz ``{ ... }`` dotyczy półruchu, który stoi tuż przed nim.
    """
    # [san, clk, eval_cp, eval_mate] jako listy, bo komentarz dochodzi po tokenie ruchu
    current: list = []
    plies: list[list] = []

    for match in _TOKEN.finditer(movetext):
        comment, token = match.groups()
        if comment is not None:
            if current:
                clk = _parse_clk(comment)
                if clk is not None:
                    current[1] = clk
                cp, mate = _parse_eval(comment)
                if cp is not None or mate is not None:
                    current[2], current[3] = cp, mate
            continue

        token = _MOVE_NUMBER.sub("", token)
        if not token or token in _MOVETEXT_RESULTS or token.startswith("$"):
            continue
        san = _SAN.match(token)
        if san is None:
            continue
        current = [san.group("san"), None, None, None]
        plies.append(current)

    return [Ply(p[0], p[1], p[2], p[3]) for p in plies]


# --- czyszczenie, tempo, kubełki ----------------------------------------------------------

_INTEGER = re.compile(r"[+-]?\d+")
_TIME_CONTROL = re.compile(r"(\d+)(?:\+(\d+))?")


def parse_time_control(value: str | None) -> tuple[int, int] | None:
    """``180+2`` -> (180, 2). Brak inkrementu to 0. Puste, ``-`` i niezrozumiałe -> None."""
    if value is None:
        return None
    match = _TIME_CONTROL.fullmatch(value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def header_reject_reason(headers: Mapping[str, str]) -> str | None:
    """Wspólne czyszczenie wszystkich jobów. None oznacza, że partia przechodzi."""
    if headers.get("Result") not in _VALID_RESULTS:
        return REJECT_RESULT
    for key in ("WhiteElo", "BlackElo"):
        if not _INTEGER.fullmatch(headers.get(key, "")):
            return REJECT_ELO
    if parse_time_control(headers.get("TimeControl")) is None:
        return REJECT_TIMECONTROL
    return None


def estimated_seconds(base: int, increment: int) -> int:
    """Szacowany czas partii jak na Lichess: sekundy na zegarze plus 40 razy inkrement."""
    return base + 40 * increment


def tempo_class(seconds: int) -> str:
    if seconds < 30:
        return "ultrabullet"
    if seconds < 180:
        return "bullet"
    if seconds < 480:
        return "blitz"
    if seconds < 1500:
        return "rapid"
    return "classical"


def tempo_of(headers: Mapping[str, str]) -> str:
    """Klasa tempa z nagłówka ``TimeControl``. Zakłada partię, która przeszła czyszczenie."""
    parsed = parse_time_control(headers.get("TimeControl"))
    if parsed is None:
        raise ValueError(f"nieprawidłowy TimeControl: {headers.get('TimeControl')!r}")
    return tempo_class(estimated_seconds(*parsed))


def elo_bucket(elo: float) -> str:
    if elo < 1200:
        return "u1200"
    if elo < 1600:
        return "1200"
    if elo < 2000:
        return "1600"
    if elo < 2400:
        return "2000"
    return "2400"


def player_elos(headers: Mapping[str, str]) -> tuple[int, int]:
    """(WhiteElo, BlackElo). Zakłada partię, która przeszła ``header_reject_reason``."""
    return int(headers["WhiteElo"]), int(headers["BlackElo"])


# --- job ply_by_tc_elo -------------------------------------------------------------------


def ply_job(game: RawGame) -> JobResult:
    """Jeden rekord na partię: klucz ``tempo|kubełek średniego Elo``, liczby ``(n, sum_plies)``."""
    reason = header_reject_reason(game.headers)
    if reason:
        return JobResult(reject=reason)
    white_elo, black_elo = player_elos(game.headers)
    key = f"{tempo_of(game.headers)}|{elo_bucket((white_elo + black_elo) / 2)}"
    return JobResult(records=((key, (1, len(parse_movetext(game.movetext)))),))


# --- job time_trouble_by_tc --------------------------------------------------------------


def clock_job(game: RawGame) -> JobResult:
    """Jeden rekord na stronę: klucz ``tempo|white`` albo ``tempo|black``.

    Liczby: ``(n, trouble, trouble_loss, ok_loss)``. Nieparzysty półruch to białe, parzysty
    czarne. Zgodnie ze specyfikacją strona dostaje rekord także wtedy, gdy nie ma ani
    jednego zegara (np. czarne po jednym półruchu): wtedy ``trouble`` = 0.
    """
    reason = header_reject_reason(game.headers)
    if reason:
        return JobResult(reject=reason)
    plies = parse_movetext(game.movetext)
    if not any(p.clk is not None for p in plies):
        return JobResult(reject=REJECT_NO_CLK)

    tempo = tempo_of(game.headers)
    result = game.headers["Result"]
    records = []
    for side, offset, loses_on in ((WHITE, 0, "0-1"), (BLACK, 1, "1-0")):
        clocks = [p.clk for p in plies[offset::2] if p.clk is not None]
        trouble = any(c <= TIME_TROUBLE_SECONDS for c in clocks)
        lost = result == loses_on
        records.append(
            (
                f"{tempo}|{side}",
                (1, int(trouble), int(trouble and lost), int(not trouble and lost)),
            )
        )
    return JobResult(records=tuple(records))
