"""Trzy wykresy z wyników jobów (pliki TSV). Osie po polsku, każde tempo osobno.

Komórki z małą próbą (mniej niż ``MIN_SAMPLE`` ruchów albo partii) są
kreskowane albo mają puste kółko, żeby nie wyciągać z nich wniosków.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

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

# Poniżej tylu ruchów (albo partii) wynik komórki uznajemy za niepewny.
MIN_SAMPLE = 1000

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
NOTE_SMALL = f"kreskowane / puste kółka: mniej niż {MIN_SAMPLE} ruchów, wynik niepewny"

COLOR_TROUBLE = "#b3473a"
COLOR_OK = "#3d7a5a"
COLOR_ANY = "#3d5a80"
COLOR_HELD = "#98c1d9"

plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "legend.fontsize": 9})


def blunder_panels(rows) -> dict[str, dict[str, dict[str, tuple[int, int]]]]:
    """tempo -> elo -> trouble|ok -> (n_moves, n_blunders). Tempa zostają rozdzielone."""
    panels: dict[str, dict[str, dict[str, tuple[int, int]]]] = {}
    for key, nums in totals_from_rows(rows).items():
        tempo, elo, state = key.split("|")
        panels.setdefault(tempo, {}).setdefault(elo, {})[state] = (nums[0], nums[1])
    return panels


def comeback_rates(rows) -> dict[str, tuple[int, ...]]:
    """tempo -> (n, comeback, comeback_held). Jedno tempo, jedna liczba, bez średniej z innych."""
    return dict(totals_from_rows(rows))


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


def _grid(count: int):
    """Panele w dwóch kolumnach, żeby wykres nie był bardzo wysoki i wąski."""
    cols = 2 if count > 1 else 1
    rows = (count + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(13, 4.2 * rows), squeeze=False, layout="constrained")
    flat = list(axes.flat)
    for ax in flat[count:]:
        ax.set_axis_off()  # pusty panel, gdy liczba temp jest nieparzysta
    return fig, flat[:count]


def plot_blunder(rows, dest: Path) -> None:
    panels = blunder_panels(rows)
    tempos = _tempos_present(panels)
    if not tempos:
        _empty(dest, TITLE_BLUNDER, LABEL_BLUNDER_Y)
        return
    fig, axes = _grid(len(tempos))
    fig.suptitle(f"{TITLE_BLUNDER}\n({NOTE_SMALL})", fontsize=13)
    for ax, tempo in zip(axes, tempos):
        elos = [elo for elo in ELO_ORDER if elo in panels[tempo]]
        for shift, state, label, color in ((-0.2, "trouble", LABEL_TROUBLE, COLOR_TROUBLE), (0.2, "ok", LABEL_OK, COLOR_OK)):
            for x, elo in enumerate(elos):
                n, blunders = panels[tempo][elo].get(state, (0, 0))
                if n == 0:
                    continue  # brak ruchów w tej komórce, nie rysujemy zerowego słupka
                ax.bar(
                    x + shift,
                    _rate(blunders, n),
                    width=0.4,
                    color=color,
                    hatch="///" if n < MIN_SAMPLE else None,
                    edgecolor="white" if n < MIN_SAMPLE else color,
                )
        ax.set_xticks(range(len(elos)), [ELO_LABELS[elo] for elo in elos])
        ax.set_ylabel(LABEL_BLUNDER_Y)
        ax.set_xlabel(LABEL_ELO_X)
        ax.set_title(tempo)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(handles=[Patch(color=COLOR_TROUBLE, label=LABEL_TROUBLE), Patch(color=COLOR_OK, label=LABEL_OK)])
    fig.savefig(dest, dpi=130)
    plt.close(fig)


def plot_comeback(rows, dest: Path) -> None:
    rates = comeback_rates(rows)
    tempos = _tempos_present(rates)
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    fig.suptitle(TITLE_COMEBACK)
    if not tempos:
        ax.text(0.5, 0.5, "Brak danych", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(dest, dpi=130)
        plt.close(fig)
        return
    for x, tempo in enumerate(tempos):
        n, comeback = rates[tempo][0], rates[tempo][1]
        held = rates[tempo][2] if len(rates[tempo]) > 2 else None
        small = n < MIN_SAMPLE
        bar = ax.bar(
            x - 0.2, _rate(comeback, n), width=0.4, color=COLOR_ANY,
            hatch="///" if small else None,
        )[0]
        ax.annotate(f"{_rate(comeback, n):.1f}%", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9)
        if held is not None:
            bar = ax.bar(
                x + 0.2, _rate(held, n), width=0.4, color=COLOR_HELD,
                hatch="///" if small else None,
            )[0]
            ax.annotate(f"{_rate(held, n):.1f}%", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontsize=9)
    ax.set_xticks(range(len(tempos)), [f"{tempo}\nn = {rates[tempo][0]}" for tempo in tempos])
    ax.set_ylabel(LABEL_COMEBACK_Y)
    ax.set_xlabel(LABEL_TEMPO_X + " (n = liczba rozstrzygniętych partii z oceną)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    handles = [Patch(color=COLOR_ANY, label="choć jedna ocena")]
    if any(len(nums) > 2 for nums in rates.values()):
        handles.append(Patch(color=COLOR_HELD, label="6 ocen z rzędu"))
    ax.legend(handles=handles, title="zwycięzca gorszy o ≥ 2 piony", loc="upper right")
    fig.savefig(dest, dpi=130)
    plt.close(fig)


def plot_think(rows, dest: Path) -> None:
    panels = think_panels(rows)
    tempos = _tempos_present(panels)
    if not tempos:
        _empty(dest, TITLE_THINK, LABEL_THINK_Y)
        return
    fig, axes = _grid(len(tempos))
    fig.suptitle(f"{TITLE_THINK}\n({NOTE_SMALL})", fontsize=13)
    xs = list(range(len(THINK_ORDER)))
    for ax, tempo in zip(axes, tempos):
        for elo in ELO_ORDER:
            buckets = panels[tempo].get(elo, {})
            if not buckets:
                continue
            cells = [buckets.get(bucket, (0, 0)) for bucket in THINK_ORDER]
            ys = [s / n if n else float("nan") for n, s in cells]
            line = ax.plot(xs, ys, linewidth=2, label=ELO_LABELS[elo])[0]
            for x, y, (n, _s) in zip(xs, ys, cells):
                small = n < MIN_SAMPLE
                ax.plot(x, y, "o", markersize=8, color=line.get_color(),
                        markerfacecolor="white" if small else line.get_color())
        ax.set_xticks(xs, [THINK_LABELS[bucket] for bucket in THINK_ORDER])
        ax.set_ylabel(LABEL_THINK_Y)
        ax.set_xlabel(LABEL_THINK_X)
        ax.set_title(tempo)
        ax.grid(alpha=0.3)
        ax.legend(title=LABEL_ELO_X)
    fig.savefig(dest, dpi=130)
    plt.close(fig)


def _empty(dest: Path, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 3), layout="constrained")
    fig.suptitle(title)
    ax.set_ylabel(ylabel)
    ax.text(0.5, 0.5, "Brak danych", ha="center", va="center", transform=ax.transAxes)
    fig.savefig(dest, dpi=130)
    plt.close(fig)


def plot_all(blunder_rows, comeback_rows, think_rows, out_dir: Path, ext: str = "png") -> None:
    """Zapisuje blunder, comeback i namysl jako ``ext`` (png do repo, pdf do sprawozdania)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_blunder(blunder_rows, out_dir / f"blunder.{ext}")
    plot_comeback(comeback_rows, out_dir / f"comeback.{ext}")
    plot_think(think_rows, out_dir / f"namysl.{ext}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wykresy trzech analiz.")
    parser.add_argument("--blunder", type=Path, required=True)
    parser.add_argument("--comeback", type=Path, required=True)
    parser.add_argument("--think", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("plots"))
    parser.add_argument("--ext", choices=("png", "pdf"), default="png")
    args = parser.parse_args(argv)
    plot_all(read_tsv(args.blunder), read_tsv(args.comeback), read_tsv(args.think), args.out, args.ext)
    print(f"zapisano blunder, comeback i namysl ({args.ext}) w {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
