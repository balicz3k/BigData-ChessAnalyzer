"""Etap 0: szkielet repozytorium. Pilnuje, żeby sekrety i dane nie trafiły do gita."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_ENV_KEYS = [
    "LOCAL_MONGO_URI",
    "LOCAL_MONGO_CA",
    "ATLAS_URI",
    "PGN_URL",
    "HDFS_PATH",
    "DEV_MAX_BYTES",
    "FULL_MIN_BYTES",
]


def _env_example() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_env_example_ma_wymagane_klucze():
    values = _env_example()
    missing = [k for k in REQUIRED_ENV_KEYS if k not in values]
    assert not missing, f".env.example nie ma kluczy: {missing}"


@pytest.mark.parametrize("key", ["LOCAL_MONGO_URI", "LOCAL_MONGO_CA", "ATLAS_URI", "MONGO_ROOT_PASSWORD"])
def test_env_example_nie_zawiera_sekretow(key):
    assert _env_example()[key] == "", f"{key} w .env.example musi być pusty (sekrety tylko w .env)"


def test_env_example_progi():
    values = _env_example()
    assert values["DEV_MAX_BYTES"] == "50000000"
    assert values["FULL_MIN_BYTES"] == "5500000000"
    assert values["HDFS_PATH"] == "/user/chess/raw/lichess_2026-09.pgn"
    assert values["PGN_URL"].endswith("lichess_db_standard_rated_2026-09.pgn.zst")


@pytest.mark.skipif(shutil.which("git") is None, reason="brak gita")
@pytest.mark.parametrize(
    "path",
    [".env", "certs/ca.pem", "certs/server.key", "data/lichess_2026-09.pgn", "data/plik.zst", "out/dlugosc.png"],
)
def test_gitignore_wyklucza(path):
    result = subprocess.run(
        ["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True, check=False
    )
    assert result.returncode == 0, f"{path} nie jest ignorowany przez .gitignore"


@pytest.mark.skipif(shutil.which("git") is None, reason="brak gita")
@pytest.mark.parametrize("path", ["data/.gitkeep", "certs/.gitkeep", ".env.example", "tests/fixtures/clk_game.pgn"])
def test_gitignore_nie_wyklucza(path):
    result = subprocess.run(
        ["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True, check=False
    )
    assert result.returncode == 1, f"{path} jest błędnie ignorowany"


def test_pakiet_src_importowalny():
    import src  # noqa: F401
