"""Dokładność ruchów z gotowych ocen ``[%eval]`` (job accuracy_by_elo).

Wzory z docs/DANE-I-ANALIZY.md, szansa wygranej wg https://lichess.org/page/accuracy.
Silnika szachowego nie uruchamiamy: korzystamy tylko z ocen zapisanych w pliku PGN.

To jest uproszczenie względem kodu Lichess: bez dopłaty za niepewność analizy i bez
średniej harmonicznej całej partii. Liczymy średnią dokładności ruchów.
"""

from __future__ import annotations

import math

from src.pgn import (
    REJECT_FEW_EVALS,
    JobResult,
    RawGame,
    Record,
    elo_bucket,
    header_reject_reason,
    parse_movetext,
    player_elos,
)

# Partia musi mieć co najmniej tyle ocen liczbowych (mat się nie wlicza).
MIN_NUMERIC_EVALS = 10

_WIN_COEFFICIENT = 0.00368208
# exp() przekracza zakres float około 709; to granica, za którą wynik jest już 0 albo 100.
_EXP_LIMIT = 700.0


def win_percent(centipawns: float) -> float:
    """Szansa wygranej (0-100) gracza, z którego perspektywy podano ocenę."""
    exponent = -_WIN_COEFFICIENT * centipawns
    if exponent > _EXP_LIMIT:
        return 0.0
    if exponent < -_EXP_LIMIT:
        return 100.0
    return 50 + 50 * (2 / (1 + math.exp(exponent)) - 1)


def move_accuracy(win_before: float, win_after: float) -> float:
    """Dokładność ruchu (0-100). Brak spadku szansy wygranej to 100."""
    if win_after >= win_before:
        return 100.0
    value = 103.1668 * math.exp(-0.04354 * (win_before - win_after)) - 3.1669
    return max(0.0, min(100.0, value))


def centipawn_loss(cp_before: int, cp_after: int) -> int:
    """Strata centypionów ruchu z perspektywy gracza, który go wykonał."""
    return max(0, cp_before - cp_after)


def accuracy_job(game: RawGame) -> JobResult:
    """Jeden rekord na stronę z co najmniej jednym policzonym ruchem.

    Klucz: kubełek Elo gracza, który wykonał ruch. Liczby: ``(n_moves, sum_accuracy_millis,
    sum_cpl)``. Rekordy idą w kolejności białe, czarne.

    Para ocen to ocena po poprzednim półruchu i po tym ruchu, więc pierwszy ruch partii
    (bez oceny przed nim) jest pominięty. Pary z matem są pomijane i liczone w liczniku
    ``mate_pairs``. Brak ``[%eval]`` przy którymkolwiek końcu pary też pomija ruch.
    """
    reason = header_reject_reason(game.headers)
    if reason:
        return JobResult(reject=reason)
    plies = parse_movetext(game.movetext)
    if sum(p.eval_cp is not None for p in plies) < MIN_NUMERIC_EVALS:
        return JobResult(reject=REJECT_FEW_EVALS)

    n_moves = [0, 0]
    sum_accuracy = [0.0, 0.0]
    sum_cpl = [0, 0]
    mate_pairs = 0

    for i in range(1, len(plies)):
        before, after = plies[i - 1], plies[i]
        if before.eval_mate is not None or after.eval_mate is not None:
            mate_pairs += 1
            continue
        if before.eval_cp is None or after.eval_cp is None:
            continue
        side = i % 2  # 0 = białe (parzysty indeks), 1 = czarne
        # Oceny w pliku są z perspektywy białych. Czarnym odwracamy znak.
        sign = 1 if side == 0 else -1
        cp_before, cp_after = sign * before.eval_cp, sign * after.eval_cp
        n_moves[side] += 1
        sum_accuracy[side] += move_accuracy(win_percent(cp_before), win_percent(cp_after))
        sum_cpl[side] += centipawn_loss(cp_before, cp_after)

    elos = player_elos(game.headers)
    records: list[Record] = []
    for side in (0, 1):
        if n_moves[side]:
            millis = math.floor(sum_accuracy[side] * 1000 + 0.5)
            records.append((elo_bucket(elos[side]), (n_moves[side], millis, sum_cpl[side])))
    return JobResult(records=tuple(records), counters={"mate_pairs": mate_pairs})
