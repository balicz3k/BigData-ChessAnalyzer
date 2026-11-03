"""Trzy obowiązujące analizy: błąd przy fladze, powrót z przegranej, czas namysłu.

Wzory są tylko tutaj (docs/DANE-I-ANALIZY.md). Mappery Hadoopa importują te funkcje.
Strata centypionów, tempo i kubełki Elo pochodzą z ``src.accuracy`` i ``src.pgn``
i nie są tu liczone drugi raz. Silnika szachowego nie uruchamiamy.
"""

from __future__ import annotations

from src.accuracy import centipawn_loss
from src.pgn import (
    TIME_TROUBLE_SECONDS,
    JobResult,
    Ply,
    RawGame,
    Record,
    elo_bucket,
    header_reject_reason,
    parse_movetext,
    parse_time_control,
    player_elos,
    tempo_of,
)

# Strata co najmniej tylu centypionów jest błędem.
BLUNDER_CP = 100
# Pozycja gorsza o co najmniej 2 piony (ocena z pliku, perspektywa białych).
COMEBACK_CP = 200

REJECT_NO_QUALIFYING = "no_qualifying"
REJECT_NOT_DECISIVE = "not_decisive"
REJECT_NO_EVAL = "no_eval"

WHITE_SIDE = 0
BLACK_SIDE = 1


def think_bucket(seconds: int) -> str | None:
    """Koszyk czasu namysłu. Ujemny czas nie ma koszyka (ruch odrzucamy)."""
    if seconds < 0:
        return None
    if seconds < 2:
        return "0-2"
    if seconds < 10:
        return "2-10"
    return "10+"


def _player_cpl(plies: list[Ply], index: int) -> int | None:
    """Strata centypionów ruchu ``index`` z perspektywy gracza, który go wykonał.

    ``None``, gdy brak pary liczbowych ocen (pierwszy półruch, luka albo mat).
    Oceny w pliku są z perspektywy białych, więc czarnym odwracamy znak.
    """
    if index < 1:
        return None
    before, after = plies[index - 1], plies[index]
    if before.eval_mate is not None or after.eval_mate is not None:
        return None
    if before.eval_cp is None or after.eval_cp is None:
        return None
    sign = 1 if index % 2 == WHITE_SIDE else -1
    return centipawn_loss(sign * before.eval_cp, sign * after.eval_cp)


def _think_seconds(plies: list[Ply], index: int, initial: int, increment: int) -> int | None:
    """Czas namysłu ruchu albo ``None``, gdy nie da się go policzyć (brak zegara).

    Pierwszy ruch gracza: czas początkowy minus zegar po ruchu, bez inkrementu.
    Kolejny: różnica wobec bezpośrednio poprzedniego własnego zegara plus inkrement.
    Luka (poprzedni własny półruch bez zegara) nie sięga do starszego odczytu.
    Ujemny wynik też zwracamy, żeby wołający mógł go odrzucić i policzyć.
    """
    clk = plies[index].clk
    if clk is None:
        return None
    if index == index % 2:
        return initial - clk
    previous = plies[index - 2].clk
    if previous is None:
        return None
    return (previous - clk) + increment


def _checked(game: RawGame) -> tuple[str | None, list[Ply], tuple[int, int] | None]:
    """Wspólne czyszczenie. Zwraca (powód odrzucenia, półruchy, (baza, inkrement))."""
    reason = header_reject_reason(game.headers)
    if reason:
        return reason, [], None
    parsed = parse_time_control(game.headers.get("TimeControl"))
    if parsed is None:
        return "timecontrol", [], None
    return None, parse_movetext(game.movetext), parsed


def blunder_job(game: RawGame) -> JobResult:
    """Jeden rekord na klucz ``tempo|elo|trouble`` albo ``tempo|elo|ok``.

    Liczby: ``(n_moves, n_blunders)``. Ruch wchodzi tylko z parą liczbowych ocen
    i zegarem. Błąd to strata co najmniej ``BLUNDER_CP``. Zegar ``<= 10`` s to ``trouble``.
    """
    reason, plies, _parsed = _checked(game)
    if reason:
        return JobResult(reject=reason)
    tempo = tempo_of(game.headers)
    elos = player_elos(game.headers)
    totals: dict[str, list[int]] = {}
    for index, ply in enumerate(plies):
        if ply.clk is None:
            continue
        loss = _player_cpl(plies, index)
        if loss is None:
            continue
        state = "trouble" if ply.clk <= TIME_TROUBLE_SECONDS else "ok"
        key = f"{tempo}|{elo_bucket(elos[index % 2])}|{state}"
        bucket = totals.setdefault(key, [0, 0])
        bucket[0] += 1
        bucket[1] += int(loss >= BLUNDER_CP)
    if not totals:
        return JobResult(reject=REJECT_NO_QUALIFYING)
    records: tuple[Record, ...] = tuple((key, (nums[0], nums[1])) for key, nums in sorted(totals.items()))
    return JobResult(records=records)


def comeback_job(game: RawGame) -> JobResult:
    """Jeden rekord na partię: klucz to tempo, liczby ``(n, comeback)``.

    Tylko partie rozstrzygnięte z co najmniej jedną oceną liczbową. Białe wracają,
    gdy wygrały i kiedyś ocena z pliku była ``<= -200``. Czarne wracają, gdy wygrały
    i kiedyś ocena była ``>= 200``.
    """
    reason, plies, _parsed = _checked(game)
    if reason:
        return JobResult(reject=reason)
    result = game.headers["Result"]
    if result == "1/2-1/2":
        return JobResult(reject=REJECT_NOT_DECISIVE)
    evals = [ply.eval_cp for ply in plies if ply.eval_cp is not None]
    if not evals:
        return JobResult(reject=REJECT_NO_EVAL)
    if result == "1-0":
        comeback = int(any(cp <= -COMEBACK_CP for cp in evals))
    else:
        comeback = int(any(cp >= COMEBACK_CP for cp in evals))
    return JobResult(records=((tempo_of(game.headers), (1, comeback)),))


def think_job(game: RawGame) -> JobResult:
    """Jeden rekord na klucz ``tempo|elo|koszyk``. Liczby: ``(n_moves, sum_cpl)``.

    Ujemny czas namysłu zwiększa licznik ``negative_think`` i nie wchodzi do sumy.
    """
    reason, plies, parsed = _checked(game)
    if reason:
        return JobResult(reject=reason)
    assert parsed is not None
    initial, increment = parsed
    tempo = tempo_of(game.headers)
    elos = player_elos(game.headers)
    totals: dict[str, list[int]] = {}
    negative = 0
    for index, _ply in enumerate(plies):
        think = _think_seconds(plies, index, initial, increment)
        if think is None:
            continue
        if think < 0:
            negative += 1
            continue
        bucket_name = think_bucket(think)
        if bucket_name is None:
            continue
        loss = _player_cpl(plies, index)
        if loss is None:
            continue
        key = f"{tempo}|{elo_bucket(elos[index % 2])}|{bucket_name}"
        bucket = totals.setdefault(key, [0, 0])
        bucket[0] += 1
        bucket[1] += loss
    counters = {"negative_think": negative}
    if not totals:
        return JobResult(reject=REJECT_NO_QUALIFYING, counters=counters)
    records = tuple((key, (nums[0], nums[1])) for key, nums in sorted(totals.items()))
    return JobResult(records=records, counters=counters)
