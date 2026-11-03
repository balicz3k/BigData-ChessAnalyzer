"""Mapper, reducer i zgodność sum z lokalnym parserem. Bez klastra."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.aggregate import diff_totals, totals_for_path, totals_from_rows
from src.analyses import comeback_job
from src.compare_sums import compare_job
from src.streaming import hadoop_lines, map_games, reduce_lines

ROOT = Path(__file__).resolve().parent.parent

PGN = """[Event "x"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1400"]
[TimeControl "60+0"]

1. e4 { [%eval -2.00] [%clk 0:01:00] } 1... e5 { [%eval -1.00] [%clk 0:01:00] } 1-0

"""


def test_hadoop_odcina_offset_bajtu():
    raw = [f"{index}\t{line}" for index, line in enumerate(PGN.splitlines(keepends=True))]
    assert "".join(hadoop_lines(raw)) == PGN


def test_mapper_emituje_rekord_i_licznik(capsys):
    lines = [f"{index}\t{line}" for index, line in enumerate(PGN.splitlines(keepends=True))]
    assert map_games(lines, comeback_job) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "bullet\t1,1"
    assert "reporter:counter:chess,games,1" in captured.err


def test_reducer_sumuje_pogrupowany_klucz():
    lines = ["bullet\t1,1\n", "bullet\t2,0\n", "blitz\t4,1\n"]
    assert list(reduce_lines(lines)) == ["bullet\t3,1", "blitz\t4,1"]


def test_skrypt_reducera(tmp_path):
    proc = subprocess.run(
        [sys.executable, "mr/reducer.py"],
        input="bullet\t1,1\nbullet\t2,0\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "bullet\t3,1\n"


def test_skrypt_mappera_comeback():
    proc = subprocess.run(
        [sys.executable, "mr/mapper_comeback.py"],
        input="".join(f"{i}\t{line}" for i, line in enumerate(PGN.splitlines(keepends=True))),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "bullet\t1,1"
    assert "reporter:counter:chess,games,1" in proc.stderr


def test_sumy_zgodne_z_parserem(tmp_path):
    pgn = tmp_path / "gry.pgn"
    pgn.write_text(PGN, encoding="utf-8")
    local = totals_for_path(pgn, comeback_job)
    assert local == {"bullet": (1, 1)}
    tsv = tmp_path / "comeback.tsv"
    tsv.write_text("bullet\t1,1\n", encoding="utf-8")
    assert compare_job(pgn, "comeback_by_tc", tsv) == []
    tsv.write_text("bullet\t1,0\n", encoding="utf-8")
    diffs = diff_totals(local, totals_from_rows([("bullet", (1, 0))]))
    assert diffs
    assert "bullet" in diffs[0]


def test_mapper_nie_kopiuje_wzoru():
    for name in ("mapper_blunder.py", "mapper_comeback.py", "mapper_think.py"):
        text = (ROOT / "mr" / name).read_text(encoding="utf-8")
        assert "centipawn_loss" not in text
        assert "def blunder_job" not in text
        assert "def comeback_job" not in text
        assert "def think_job" not in text
