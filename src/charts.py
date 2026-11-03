"""Trzy wykresy z wyników jobów. Osie po polsku. Bullet nie jest uśredniany z klasykiem."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.aggregate import read_tsv, totals_from_rows

TEMPO_ORDER = ("ultrabullet", "bullet", "blitz", "rapid", "classical")
ELO_ORDER = ("u1200", "1200", "1600", "2000", "2400")
ELO_LABELS = {
    "u1200": "poniżej 1200",
    "1200": "1200–1599",
    "1600": "1600–1999",
    "2000": "2000–2399",
    "2400": "2400+",
}
THINK_ORDER = ("0-2", "2-10", "10+")
THINK_LABELS = {"0-2": "0–2 s", "2-10": "2–10 s", "10+": "10+ s"}

LABEL_TROUBLE = "Pod flagą"
LABEL_OK = "Z czasem"
LABEL_BLUNDER_Y = "Odsetek błędów (%)"
LABEL_COMEBACK_Y = "Odsetek powrotów (%)"
LABEL_THINK_Y = "Średnia strata (centypiony)"
LABEL_THINK_X = "Czas namysłu"
LABEL_ELO_X = "Ranking"
LABEL_TEMPO_X = "Tempo"
TITLE_BLUNDER = "Błędy przy fladze i z czasem"
TITLE_COMEBACK = "Powrót z pozycji gorszej o dwa piony"
TITLE_THINK = "Czas namysłu a strata centypionów"


def blunder_panels(rows) -> dict[str, dict[str, dict[str, tuple[int, int]]]]:
    """tempo -> elo -> trouble|ok -> (n_moves, n_blunders). Tempa zostają rozdzielone."""
    panels: dict[str, dict[str, dict[str, tuple[int, int]]]] = {}
    for key, nums in totals_from_rows(rows).items():
        tempo, elo, state = key.split("|")
        panels.setdefault(tempo, {}).setdefault(elo, {})[state] = (nums[0], nums[1])
    return panels


def comeback_rates(rows) -> dict[str, tuple[int, int]]:
    """tempo -> (n, comeback). Jedno tempo, jedna liczba, bez średniej z innych."""
    return {key: (nums[0], nums[1]) for key, nums in totals_from_rows(rows).items()}


def think_panels(rows) -> dict[str, dict[str, dict[str, tuple[int, int]]]]:
    """tempo -> elo -> koszyk -> (n_moves, sum_cpl)."""
    panels: dict[str, dict[str, dict[str, tuple[int, int]]]] = {}
    for key, nums in totals_from_rows(rows).items():
        tempo, elo, bucket = key.split("|")
        panels.setdefault(tempo, {}).setdefault(elo, {})[bucket] = (nums[0], nums[1])
    return panels


def _tempos_present(keys) -> list[str]:
    present = set(keys)
    return [tempo for tempo in TEMPO_ORDER if tempo in present]


def _rate(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return 100.0 * part / whole


def plot_blunder(rows, dest: Path) -> None:
    panels = blunder_panels(rows)
    tempos = _tempos_present(panels)
    if not tempos:
        _empty(dest, TITLE_BLUNDER, LABEL_BLUNDER_Y)
        return
    fig, axes = plt.subplots(len(tempos), 1, figsize=(10, 3.2 * len(tempos)), squeeze=False, layout="constrained")
    fig.suptitle(TITLE_BLUNDER)
    for ax, tempo in zip(axes[:, 0], tempos):
        elos = [elo for elo in ELO_ORDER if elo in panels[tempo]]
        xs = list(range(len(elos)))
        trouble = [_rate(*_pair(panels[tempo][elo], "trouble")) for elo in elos]
        ok = [_rate(*_pair(panels[tempo][elo], "ok")) for elo in elos]
        ax.bar([x - 0.18 for x in xs], trouble, width=0.36, label=LABEL_TROUBLE, color="#b3473a")
        ax.bar([x + 0.18 for x in xs], ok, width=0.36, label=LABEL_OK, color="#3d7a5a")
        ax.set_xticks(xs, [ELO_LABELS[elo] for elo in elos])
        ax.set_ylabel(LABEL_BLUNDER_Y)
        ax.set_xlabel(LABEL_ELO_X)
        ax.set_title(tempo)
        ax.legend()
    fig.savefig(dest, dpi=120)
    plt.close(fig)


def _pair(elo_map: dict, state: str) -> tuple[int, int]:
    nums = elo_map.get(state)
    if not nums or nums[0] == 0:
        return 0, 0
    return nums[1], nums[0]


def plot_comeback(rows, dest: Path) -> None:
    rates = comeback_rates(rows)
    tempos = _tempos_present(rates)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    fig.suptitle(TITLE_COMEBACK)
    if not tempos:
        ax.text(0.5, 0.5, "Brak danych", ha="center", va="center")
        ax.set_axis_off()
    else:
        xs = list(range(len(tempos)))
        values = [_rate(rates[tempo][1], rates[tempo][0]) for tempo in tempos]
        bars = ax.bar(xs, values, color="#3d5a80")
        ax.set_xticks(xs, tempos)
        ax.set_ylabel(LABEL_COMEBACK_Y)
        ax.set_xlabel(LABEL_TEMPO_X)
        for bar, tempo in zip(bars, tempos):
            n, comeback = rates[tempo]
            ax.annotate(
                f"{_rate(comeback, n):.1f}%\n(n={n})",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                ha="center",
                va="bottom",
                fontsize=8,
            )
    fig.savefig(dest, dpi=120)
    plt.close(fig)


def plot_think(rows, dest: Path) -> None:
    panels = think_panels(rows)
    tempos = _tempos_present(panels)
    if not tempos:
        _empty(dest, TITLE_THINK, LABEL_THINK_Y)
        return
    fig, axes = plt.subplots(len(tempos), 1, figsize=(10, 3.2 * len(tempos)), squeeze=False, layout="constrained")
    fig.suptitle(TITLE_THINK)
    xs = list(range(len(THINK_ORDER)))
    for ax, tempo in zip(axes[:, 0], tempos):
        for elo in ELO_ORDER:
            buckets = panels[tempo].get(elo, {})
            if not buckets:
                continue
            ys = []
            for bucket in THINK_ORDER:
                cell = buckets.get(bucket)
                ys.append(cell[1] / cell[0] if cell and cell[0] else float("nan"))
            ax.plot(xs, ys, marker="o", label=ELO_LABELS[elo])
        ax.set_xticks(xs, [THINK_LABELS[bucket] for bucket in THINK_ORDER])
        ax.set_ylabel(LABEL_THINK_Y)
        ax.set_xlabel(LABEL_THINK_X)
        ax.set_title(tempo)
        ax.legend(title=LABEL_ELO_X)
    fig.savefig(dest, dpi=120)
    plt.close(fig)


def _empty(dest: Path, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 3), layout="constrained")
    fig.suptitle(title)
    ax.set_ylabel(ylabel)
    ax.text(0.5, 0.5, "Brak danych", ha="center", va="center", transform=ax.transAxes)
    fig.savefig(dest, dpi=120)
    plt.close(fig)


def plot_all(blunder_rows, comeback_rows, think_rows, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_blunder(blunder_rows, out_dir / "blunder.png")
    plot_comeback(comeback_rows, out_dir / "comeback.png")
    plot_think(think_rows, out_dir / "namysl.png")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wykresy trzech analiz.")
    parser.add_argument("--blunder", type=Path, required=True)
    parser.add_argument("--comeback", type=Path, required=True)
    parser.add_argument("--think", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)
    plot_all(read_tsv(args.blunder), read_tsv(args.comeback), read_tsv(args.think), args.out)
    print(f"zapisano {args.out / 'blunder.png'}, {args.out / 'comeback.png'}, {args.out / 'namysl.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
