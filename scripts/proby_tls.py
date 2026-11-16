#!/usr/bin/env python3
"""Cztery próby połączenia z lokalną MongoDB: pokazują, że bez TLS, bez naszego CA
albo bez hasła się nie da, a z kompletem ustawień tak.

Adres i plik CA bierze z .env. Hasła ani adresu nie wypisuje.
Uruchomienie: .venv/bin/python scripts/proby_tls.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import MongoClient  # noqa: E402

from src.mongo_io import _ca_path, local_uri  # noqa: E402


def without_password(uri: str) -> str:
    """Ten sam adres, ale bez użytkownika i hasła."""
    parts = urlsplit(uri)
    host = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def attempt(label: str, uri: str, **options) -> None:
    client = MongoClient(uri, serverSelectionTimeoutMS=4000, **options)
    try:
        count = client["chess"]["aggregates"].count_documents({})
        print(f"{label:<28} OK, aggregates: {count} dokumentów")
    except Exception as exc:  # pokazujemy tylko typ i pierwszą linię błędu
        message = str(exc).splitlines()[0].split(" (configured")[0].split(", full error")[0]
        print(f"{label:<28} ODMOWA: {type(exc).__name__}: {message}")
    finally:
        client.close()


def main() -> int:
    uri, ca = local_uri(), str(_ca_path())
    attempt("1. bez TLS", uri, tls=False)
    attempt("2. TLS bez naszego CA", uri, tls=True)
    attempt("3. TLS + CA, bez hasła", without_password(uri), tls=True, tlsCAFile=ca)
    attempt("4. TLS + CA + hasło (SCRAM)", uri, tls=True, tlsCAFile=ca)
    return 0


if __name__ == "__main__":
    sys.exit(main())
