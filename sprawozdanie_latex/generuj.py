"""Tabele (tables_generated.tex) i rysunki PDF do sprawozdania i prezentacji.

Wszystkie liczby biorą się z plików w wyniki/ (wyniki jobów Hadoop i logi),
nic nie jest przepisywane ręcznie. Uruchomienie z katalogu projektu:
    .venv/bin/python sprawozdanie_latex/generuj.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # żeby działał import src.* przy uruchomieniu z dowolnego miejsca

from src.aggregate import read_tsv, totals_from_rows  # noqa: E402
from src.charts import ELO_ORDER, MIN_SAMPLE, TEMPO_ORDER, plot_all  # noqa: E402

FULL = ROOT / "wyniki" / "full"
ONE_MAPPER = ROOT / "wyniki" / "jeden_mapper"
LOG_FULL = ROOT / "wyniki" / "logi" / "run_all_full.log"
OUT_TEX = Path(__file__).resolve().parent / "tables_generated.tex"
FIGURES = Path(__file__).resolve().parent / "figures"
ELO_TEX = {"u1200": "$<$1200", "1200": "1200", "1600": "1600", "2000": "2000", "2400": "2400+"}
JOBS = ("blunder_in_trouble", "comeback_by_tc", "think_vs_cpl")


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}".replace(".", ",") + r"\%"


def num(value: int) -> str:
    """1234567 -> 1\\,234\\,567 (polski zapis tysięcy)."""
    return f"{value:,}".replace(",", r"\,")


def dec(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def table_blunder(rows) -> str:
    cells = totals_from_rows(rows)
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Tempo & Elo & Z czasem & Pod flagą & Wzrost & Ruchy pod flagą \\", r"\midrule"]
    for tempo in TEMPO_ORDER:
        any_row = False
        for elo in ELO_ORDER:
            ok = cells.get(f"{tempo}|{elo}|ok")
            trouble = cells.get(f"{tempo}|{elo}|trouble")
            if not ok or not trouble:
                continue  # brak jednej z grup, nie ma czego porównać
            star = "*" if min(ok[0], trouble[0]) < MIN_SAMPLE else ""
            rate_ok, rate_tr = ok[1] / ok[0], trouble[1] / trouble[0]
            # przy małej próbie nie podajemy wzrostu, bo bywa absurdalny (np. -100%)
            growth = "--" if star or not rate_ok else f"{100 * (rate_tr / rate_ok - 1):+.0f}\\%"
            lines.append(f"{tempo} & {ELO_TEX[elo]} & {pct(ok[1], ok[0])} & {pct(trouble[1], trouble[0])}{star} "
                         f"& {growth} & {num(trouble[0])} \\\\")
            any_row = True
        if any_row:
            lines.append(r"\addlinespace[2pt]")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def table_comeback(rows) -> str:
    cells = totals_from_rows(rows)
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"Tempo & Choć jedna ocena & 6 ocen z rzędu & $n$ \\", r"\midrule"]
    for tempo in TEMPO_ORDER:
        if tempo not in cells:
            continue
        n, any_, held = cells[tempo]
        star = "*" if n < MIN_SAMPLE * 5 else ""
        lines.append(f"{tempo} & {pct(any_, n)}{star} & {pct(held, n)}{star} & {num(n)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def table_think(rows, tempos=("blitz", "bullet")) -> str:
    cells = totals_from_rows(rows)
    lines = [r"\begin{tabular}{llrrr}", r"\toprule", r"Tempo & Elo & 0--2 s & 2--10 s & 10+ s \\", r"\midrule"]
    for tempo in tempos:
        for elo in ELO_ORDER:
            row = []
            for bucket in ("0-2", "2-10", "10+"):
                n, total = cells.get(f"{tempo}|{elo}|{bucket}", (0, 0))
                row.append(dec(total / n) + ("*" if n < MIN_SAMPLE else "") if n else "--")
            lines.append(f"{tempo} & {ELO_TEX[elo]} & " + " & ".join(row) + r" \\")
        lines.append(r"\addlinespace[2pt]")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def read_times(path: Path) -> dict[str, int]:
    """czasy.tsv z run_jobs.sh: analiza, wejście, sekundy."""
    times = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _input, seconds = line.split("\t")
        times[name] = int(seconds)
    return times


def mmss(seconds: int) -> str:
    return f"{seconds // 60} min {seconds % 60:02d} s"


def table_times(one: dict[str, int], eight: dict[str, int]) -> str:
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"Job & 1 plik, 1 mapper & 8 części, 8 mapperów & Przyspieszenie \\", r"\midrule"]
    for job in JOBS:
        lines.append(f"\\kod{{{job.replace('_', chr(92) + '_')}}} & {mmss(one[job])} & {mmss(eight[job])} "
                     f"& {dec(one[job] / eight[job])}$\\times$ \\\\")
    total_one, total_eight = sum(one.values()), sum(eight.values())
    lines += [r"\midrule", f"Razem & {mmss(total_one)} & {mmss(total_eight)} & {dec(total_one / total_eight)}$\\times$ \\\\",
              r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def job_counters(log: Path) -> dict[str, dict[str, int]]:
    """Liczniki Hadoopa z logu run_all: job -> {nazwa: wartość} (grupa chess i liczba mapperów)."""
    counters: dict[str, dict[str, int]] = {}
    current = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        start = re.match(r"Start jobu (\w+)", line)
        if start:
            current = start.group(1)
            counters[current] = {}
            continue
        match = re.match(r"\s+([A-Za-z_ ]+)=(\d+)$", line)
        if current and match:
            counters[current][match.group(1).strip()] = int(match.group(2))
    return counters


def growth(rows, tempo: str, elo: str) -> str:
    """Względny wzrost odsetka błędów pod flagą dla jednej komórki, np. +45\\%."""
    cells = totals_from_rows(rows)
    ok, trouble = cells[f"{tempo}|{elo}|ok"], cells[f"{tempo}|{elo}|trouble"]
    return f"{100 * ((trouble[1] / trouble[0]) / (ok[1] / ok[0]) - 1):+.0f}\\%"


def import_log(log: Path, dest: Path) -> None:
    """Wycina z logu run_all wiersze kroku importu (dowód braku powielania)."""
    keep = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith(("aggregates ", "OK: drugi", "usunięto kolekcje aggregates"))]
    dest.write_text("\n".join(keep) + "\n", encoding="utf-8")


def macros(counters: dict[str, dict[str, int]], times: dict[str, int], one: dict[str, int]) -> str:
    """Pojedyncze liczby do tekstu, np. \\nGames."""
    blunder = counters["blunder_in_trouble"]
    comeback = counters["comeback_by_tc"]
    think = counters["think_vs_cpl"]
    values = {
        "nGames": num(blunder["games"]),
        "nMapInput": num(blunder["Map input records"]),
        "nMaps": str(blunder["Launched map tasks"]),
        "nRejResult": num(blunder.get("result", 0)),
        "nRejTimecontrol": num(blunder.get("timecontrol", 0)),
        "nNoQualifying": num(blunder.get("no_qualifying", 0)),
        "nNoEval": num(comeback.get("no_eval", 0)),
        "nNotDecisive": num(comeback.get("not_decisive", 0)),
        "nNegativeThink": num(think.get("negative_think", 0)),
        "tEight": mmss(sum(times.values())),
        "tOne": mmss(sum(one.values())),
        "speedup": dec(sum(one.values()) / sum(times.values())),
    }
    return "\n".join(f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in values.items())


def main() -> int:
    rows = {job: read_tsv(FULL / f"{job}.tsv") for job in JOBS}
    eight = read_times(FULL / "czasy.tsv")
    one = read_times(ONE_MAPPER / "czasy.tsv")
    counters = job_counters(LOG_FULL)
    parts = [
        "% Plik generowany przez generuj.py z plików w wyniki/. Nie edytować ręcznie.",
        macros(counters, eight, one),
        "\\newcommand{\\tabBlunder}{%\n" + table_blunder(rows["blunder_in_trouble"]) + "}",
        "\\newcommand{\\tabComeback}{%\n" + table_comeback(rows["comeback_by_tc"]) + "}",
        "\\newcommand{\\tabThink}{%\n" + table_think(rows["think_vs_cpl"]) + "}",
        "\\newcommand{\\tabCzasy}{%\n" + table_times(one, eight) + "}",
        "\\newcommand{\\nRows}{" + str(sum(len(r) for r in rows.values())) + "}",
        "\\newcommand{\\BlitzLow}{" + growth(rows["blunder_in_trouble"], "blitz", "u1200") + "}",
        "\\newcommand{\\BlitzHigh}{" + growth(rows["blunder_in_trouble"], "blitz", "2400") + "}",
    ]
    import_log(LOG_FULL, OUT_TEX.parent / "import_log.txt")
    OUT_TEX.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    plot_all(rows["blunder_in_trouble"], rows["comeback_by_tc"], rows["think_vs_cpl"], FIGURES, ext="pdf")
    print(f"zapisano {OUT_TEX.name} i rysunki PDF w {FIGURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
