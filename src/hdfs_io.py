"""Wysłanie PGN do HDFS z nadpisaniem. Drugi raz przy tym samym SHA-256 nic nie dopisuje."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from src.mongo_io import ROOT, local_client, record_import

HDFS_FULL = "/user/chess/raw/lichess_2026-09.pgn"
HDFS_SAMPLE = "/user/chess/raw/lichess_2026-09.sample.pgn"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_du(text: str) -> int | None:
    """Pierwsza liczba z ``hdfs dfs -du``. Pusty wynik znaczy, że pliku nie ma."""
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0].isdigit():
            return int(parts[0])
    return None


def should_skip_upload(previous_sha: str | None, remote_size: int | None, sha: str, nbytes: int) -> bool:
    return previous_sha == sha and remote_size == nbytes


def container_path(local: Path) -> str:
    rel = local.resolve().relative_to(ROOT.resolve())
    return "/opt/projekt/" + rel.as_posix()


def _safe_err(text: str) -> str:
    kept = []
    for line in text.splitlines():
        lower = line.lower()
        if "mongo" in lower or "mongodb://" in lower or "password" in lower:
            kept.append("[pominięto linię z możliwym sekretem]")
        else:
            kept.append(line)
    return "\n".join(kept[-30:])


def hdfs_exec(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "hadoop", "hdfs", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def remote_size(hdfs_path: str) -> int | None:
    proc = hdfs_exec(["dfs", "-du", hdfs_path])
    if proc.returncode != 0:
        return None
    return parse_du(proc.stdout)


def du_human(hdfs_path: str) -> str:
    proc = hdfs_exec(["dfs", "-du", "-h", hdfs_path])
    if proc.returncode != 0:
        raise SystemExit("BŁĄD: hdfs dfs -du -h nie powiódł się:\n" + _safe_err(proc.stderr))
    return proc.stdout.strip()


def cat(hdfs_path: str) -> str:
    proc = hdfs_exec(["dfs", "-cat", hdfs_path])
    if proc.returncode != 0:
        raise SystemExit(f"BŁĄD: hdfs dfs -cat {hdfs_path} nie powiódł się:\n" + _safe_err(proc.stderr))
    return proc.stdout


def upload_pgn(local: Path, hdfs_path: str, source_url: str) -> str:
    """Nadpisuje plik w HDFS. Ten sam SHA-256 i ten sam rozmiar pomijają wysyłkę."""
    nbytes = local.stat().st_size
    digest = sha256_file(local)
    remote = remote_size(hdfs_path)
    client = local_client()
    try:
        prev = client["chess"]["import_runs"].find_one({"pipeline": "hdfs_pgn"})
        prev_sha = prev.get("sha256") if prev else None
        if should_skip_upload(prev_sha, remote, digest, nbytes):
            print(f"HDFS bez zmian: {hdfs_path} ma {nbytes} bajtów, SHA-256 zgodny")
            return "skipped"
        inside = container_path(local)
        proc = hdfs_exec(["dfs", "-mkdir", "-p", str(Path(hdfs_path).parent)])
        if proc.returncode != 0:
            raise SystemExit("BŁĄD: hdfs dfs -mkdir nie powiódł się:\n" + _safe_err(proc.stderr))
        proc = hdfs_exec(["dfs", "-put", "-f", inside, hdfs_path])
        if proc.returncode != 0:
            raise SystemExit("BŁĄD: hdfs dfs -put nie powiódł się:\n" + _safe_err(proc.stderr))
        stored = remote_size(hdfs_path)
        if stored != nbytes:
            raise SystemExit(
                "BŁĄD: próg rozmiaru w HDFS nie został spełniony: "
                f"lokalnie {nbytes} bajtów, w HDFS {stored}"
            )
        record_import(
            client,
            "hdfs_pgn",
            source_url=source_url,
            bytes=nbytes,
            sha256=digest,
            hdfs_path=hdfs_path,
        )
    finally:
        client.close()
    print(f"HDFS nadpisany: {hdfs_path} ({nbytes} bajtów)")
    return "uploaded"
