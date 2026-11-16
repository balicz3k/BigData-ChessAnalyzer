"""Dzieli duży plik PGN na kilka części i wysyła je do jednego katalogu w HDFS.

Po co: Hadoop dzieli plik wejściowy na kawałki (splity) po 128 MB, nie patrząc na
treść. Granica kawałka mogłaby przeciąć partię w połowie. Dlatego sami dzielimy
plik, zawsze tuż przed linią ``[Event "``, a w run_jobs.sh każdy plik części jest
jednym splitem. Każda część to osobny mapper, więc mappery liczą równolegle.

Użycie: ``python -m src.split_pgn --parts 8`` (domyślnie plik z data/ i katalog HDFS
/user/chess/raw/lichess_2026-09). Drugie uruchomienie niczego nie dzieli ani nie
wysyła, jeśli części już są i mają te same rozmiary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.download import FULL_PATH
from src.hdfs_io import upload_parts

PARTS_DIR = FULL_PATH.parent / "parts"
HDFS_PARTS = "/user/chess/raw/lichess_2026-09"
EVENT = b'[Event "'


def part_path(out_dir: Path, index: int) -> Path:
    return out_dir / f"part-{index:03d}.pgn"


def split_pgn(source: Path, out_dir: Path, parts: int) -> list[Path]:
    """Zapisuje ``parts`` plików o podobnym rozmiarze. Cięcie tylko przed ``[Event``."""
    total = source.stat().st_size
    target = total // parts + 1  # docelowy rozmiar jednej części w bajtach
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("part-*.pgn"):
        old.unlink()

    paths = [part_path(out_dir, 0)]
    out = paths[0].open("wb")
    written = 0
    try:
        with source.open("rb") as fh:
            for line in fh:
                # nowa część zaczyna się dopiero od nowej partii
                if line.startswith(EVENT) and written >= target and len(paths) < parts:
                    out.close()
                    paths.append(part_path(out_dir, len(paths)))
                    out = paths[-1].open("wb")
                    written = 0
                out.write(line)
                written += len(line)
    finally:
        out.close()
    return paths


def existing_parts(source: Path, out_dir: Path, parts: int) -> list[Path] | None:
    """Gotowe części z poprzedniego przebiegu albo None, gdy trzeba dzielić od nowa."""
    paths = sorted(out_dir.glob("part-*.pgn"))
    if len(paths) != parts:
        return None
    if sum(p.stat().st_size for p in paths) != source.stat().st_size:
        return None
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dzieli PGN na części po granicach partii i wysyła do HDFS.")
    parser.add_argument("--source", type=Path, default=FULL_PATH)
    parser.add_argument("--parts", type=int, default=8)
    parser.add_argument("--out-dir", type=Path, default=PARTS_DIR)
    parser.add_argument("--hdfs-dir", default=HDFS_PARTS)
    parser.add_argument("--no-upload", action="store_true", help="tylko podział, bez HDFS")
    args = parser.parse_args(argv)

    if not args.source.is_file():
        print(f"BŁĄD: brak pliku {args.source}. Najpierw: python -m src.download --full", file=sys.stderr)
        return 1
    paths = existing_parts(args.source, args.out_dir, args.parts)
    if paths is None:
        paths = split_pgn(args.source, args.out_dir, args.parts)
        print(f"podzielono {args.source.name} na {len(paths)} części w {args.out_dir}")
    else:
        print(f"części już są: {len(paths)} plików w {args.out_dir}")
    for path in paths:
        print(f"  {path.name}  {path.stat().st_size} B")
    if not args.no_upload:
        upload_parts(paths, args.hdfs_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
