"""Połączenia Mongo i metadane importu. Hasła zostają w ``.env``, nigdy w kodzie.

Lokalne Mongo: TLS i plik CA, bez ``tlsAllowInvalidCertificates``.
Atlas: tylko gdy ``ATLAS_URI`` jest ustawione. Agregaty nie mają innej bazy zapasowej.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_NAME = "chess"


def load_dotenv(path: Path | None = None) -> None:
    """Minimalny parser ``.env``. Zmienne już ustawione w środowisku wygrywają."""
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _reject_insecure(uri: str, label: str) -> None:
    if "tlsallowinvalidcertificates" in uri.lower():
        raise SystemExit(
            f"BŁĄD: {label} zawiera tlsAllowInvalidCertificates. "
            "Weryfikacja certyfikatu musi działać."
        )


def _ca_path() -> Path:
    load_dotenv()
    ca = os.environ.get("LOCAL_MONGO_CA", "").strip()
    if not ca:
        raise SystemExit("BŁĄD: LOCAL_MONGO_CA jest pusty. Wskaż plik CA, np. certs/ca.pem.")
    path = Path(ca)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise SystemExit(f"BŁĄD: plik CA {path} nie istnieje. Uruchom scripts/gen_certs.sh.")
    return path


def local_uri() -> str:
    load_dotenv()
    uri = os.environ.get("LOCAL_MONGO_URI", "").strip()
    if not uri:
        raise SystemExit("BŁĄD: LOCAL_MONGO_URI jest pusty. Uzupełnij .env (wzór w .env.example).")
    _reject_insecure(uri, "LOCAL_MONGO_URI")
    return uri


def require_atlas_uri() -> str:
    """Puste ``ATLAS_URI`` jest błędem. Nie podstawiamy lokalnej bazy."""
    load_dotenv()
    uri = os.environ.get("ATLAS_URI", "").strip()
    if not uri:
        raise SystemExit(
            "BŁĄD: ATLAS_URI jest pusty. Agregaty idą tylko do Atlasu "
            "i nie zapisuję ich w innym miejscu."
        )
    _reject_insecure(uri, "ATLAS_URI")
    return uri


def local_client():
    from pymongo import MongoClient

    return MongoClient(
        local_uri(),
        tls=True,
        tlsCAFile=str(_ca_path()),
        serverSelectionTimeoutMS=8000,
    )


def atlas_client():
    from pymongo import MongoClient

    return MongoClient(require_atlas_uri(), serverSelectionTimeoutMS=15000)


def record_import(client, pipeline: str, **fields) -> None:
    """Zastępuje jeden dokument ``import_runs`` dla danego pipeline."""
    col = client[DB_NAME]["import_runs"]
    col.create_index("pipeline", unique=True)
    col.update_one(
        {"pipeline": pipeline},
        {"$set": {**fields, "pipeline": pipeline, "finished_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
