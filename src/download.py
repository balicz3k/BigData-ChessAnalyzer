"""Strumień archiwum Lichess `.zst` ucięty po kompletnej partii.

Tryb domyślny kończy pobieranie przy progu ``DEV_MAX_BYTES`` (50 000 000 bajtów
nieskompresowanych). Tryb ``--full`` wymaga co najmniej ``FULL_MIN_BYTES``
(5 500 000 000) i też ucina na granicy partii, zamiast ciągnąć resztę miesiąca.

Adres pliku: docs/DANE-I-ANALIZY.md (wrzesień 2026).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from collections.abc import Iterable, Iterator

from src.mongo_io import load_dotenv
from src.pgn import iter_games

ROOT = Path(__file__).resolve().parent.parent
PGN_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst"
DEV_MAX_BYTES = 50_000_000
FULL_MIN_BYTES = 5_500_000_000
SAMPLE_PATH = ROOT / "data" / "lichess_2026-09.sample.pgn"
FULL_PATH = ROOT / "data" / "lichess_2026-09.pgn"
_REPORT_EVERY = 100_000_000


class ThresholdError(RuntimeError):
    """Pobrany wycinek nie doszedł do nazwanego progu."""

    def __init__(self, name: str, required: int, actual: int):
        self.name = name
        self.required = required
        self.actual = actual
        super().__init__(
            f"próg {name} ({required} bajtów) nie został spełniony: "
            f"rozmiar nieskompresowany to {actual} bajtów"
        )


def write_cut(chunks: Iterable[bytes], dest, threshold: int) -> int:
    """Zapisuje pełne partie, aż rozmiar dojdzie do ``threshold``, i przestaje czytać.

    Zatrzymanie jest na pustej linii po zapisach ruchów albo tuż przed następnym
    ``[Event``. Kolejna partia nie wchodzi do pliku. Zwraca liczbę zapisanych bajtów.
    """
    total = 0
    past = False
    started = False
    seen_movetext = False
    buf = b""
    reported = -1

    def handle(line: bytes) -> bool:
        nonlocal total, past, started, seen_movetext, reported
        body = line.rstrip(b"\r\n")
        is_event = body.startswith(b'[Event "')
        if is_event and past and seen_movetext:
            return True
        dest.write(line)
        total += len(line)
        bucket = total // _REPORT_EVERY
        if bucket != reported and total >= _REPORT_EVERY:
            reported = bucket
            print(f"zapisano {total} bajtów nieskompresowanego PGN", file=sys.stderr)
        if is_event:
            started = True
            seen_movetext = False
        elif started and body and not body.startswith(b"["):
            seen_movetext = True
        if total >= threshold:
            past = True
        return bool(past and seen_movetext and body == b"")

    for chunk in chunks:
        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            if handle(raw + b"\n"):
                return total
    if buf:
        handle(buf)
    return total


def iter_zst_chunks(stream, size: int = 1 << 20) -> Iterator[bytes]:
    """Rozpakowuje zstd ze strumienia. Wczesne zamknięcie nie czyta reszty archiwum."""
    import zstandard as zstd

    reader = zstd.ZstdDecompressor().stream_reader(stream)
    try:
        while True:
            block = reader.read(size)
            if not block:
                break
            yield block
    finally:
        try:
            reader.close()
        except zstd.ZstdError:
            pass


def cut_zst_stream(stream, dest, threshold: int) -> int:
    """Rozpakowuje ``stream`` i ucina zapis na granicy partii."""
    return write_cut(iter_zst_chunks(stream), dest, threshold)


def assert_game_file(path: Path) -> None:
    """Plik zaczyna się od partii i kończy znakiem nowej linii."""
    with path.open("rb") as fh:
        if not fh.read(16).startswith(b'[Event "'):
            raise SystemExit("BŁĄD: plik nie zaczyna się od partii [Event")
        fh.seek(-1, os.SEEK_END)
        if fh.read(1) != b"\n":
            raise SystemExit("BŁĄD: ucięcie nie skończyło się na granicy linii")


def parser_game_count(path: Path, limit: int | None = None) -> int:
    """Ile partii wczyta parser z etapu 1. ``limit`` przerywa po tylu partiach."""
    count = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for _game in iter_games(fh):
            count += 1
            if limit is not None and count >= limit:
                break
    return count


def configured_url() -> str:
    load_dotenv(ROOT / ".env")
    return os.environ.get("PGN_URL") or PGN_URL


def configured_threshold(full: bool) -> tuple[int, str]:
    load_dotenv(ROOT / ".env")
    if full:
        raw = os.environ.get("FULL_MIN_BYTES") or str(FULL_MIN_BYTES)
        return int(raw), "FULL_MIN_BYTES"
    raw = os.environ.get("DEV_MAX_BYTES") or str(DEV_MAX_BYTES)
    return int(raw), "DEV_MAX_BYTES"


def download_to(url: str, dest: Path, threshold: int, threshold_name: str, force: bool = False) -> int:
    """Ściąga ``url`` do ``dest``. Za krótki strumień podnosi ``ThresholdError``."""
    if dest.exists() and not force and dest.stat().st_size >= threshold:
        print(
            f"pomijam pobieranie, {dest.name} ma {dest.stat().st_size} bajtów "
            f"(próg {threshold_name} = {threshold})",
            file=sys.stderr,
        )
        return dest.stat().st_size

    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": "partie-lichess-course/1.0 (educational; partial zst read)"}
    print(f"pobieram {url} do progu {threshold_name} = {threshold} bajtów", file=sys.stderr)
    try:
        with requests.get(url, stream=True, timeout=(30, 300), headers=headers) as resp:
            resp.raise_for_status()
            resp.raw.decode_content = False
            with partial.open("wb") as fh:
                total = cut_zst_stream(resp.raw, fh, threshold)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    if total < threshold:
        partial.unlink(missing_ok=True)
        raise ThresholdError(threshold_name, threshold, total)
    partial.replace(dest)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pobiera wycinek PGN Lichess z września 2026.")
    parser.add_argument("--full", action="store_true", help="próg FULL_MIN_BYTES zamiast próbki 50 MB")
    parser.add_argument("--force", action="store_true", help="pobierz ponownie, nawet gdy plik już spełnia próg")
    parser.add_argument("--upload", action="store_true", help="po pobraniu wyślij plik do HDFS (nadpisanie)")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--url", default=None)
    args = parser.parse_args(argv)

    url = args.url or configured_url()
    threshold, name = configured_threshold(args.full)
    dest = args.output or (FULL_PATH if args.full else SAMPLE_PATH)
    try:
        nbytes = download_to(url, dest, threshold, name, force=args.force)
    except ThresholdError as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 1

    assert_game_file(dest)
    limit = 1 if args.full else None
    games = parser_game_count(dest, limit=limit)
    if games < 1:
        print("BŁĄD: parser z etapu 1 nie wczytał żadnej partii", file=sys.stderr)
        return 1
    counted = "początek pliku, 1 partia" if args.full else f"{games} partii"
    print(f"zapisano {dest} ({nbytes} bajtów); parser wczytał {counted}")

    if args.upload:
        from src.hdfs_io import HDFS_FULL, HDFS_SAMPLE, upload_pgn

        upload_pgn(dest, HDFS_FULL if args.full else HDFS_SAMPLE, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
