#!/usr/bin/env python3
"""Sprawdza połączenie z lokalnym MongoDB po TLS (z plikiem CA) i uwierzytelnienie SCRAM.

Czyta LOCAL_MONGO_URI i LOCAL_MONGO_CA ze zmiennych środowiska albo z pliku .env.
Kod wyjścia 0 oznacza: połączenie z tls=True i weryfikacją certyfikatu działa,
a użytkownik jest uwierzytelniony.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimalny parser .env (KEY=VALUE). Zmienne już ustawione w środowisku wygrywają."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fail(message: str) -> int:
    print(f"BŁĄD: {message}", file=sys.stderr)
    return 1


def main() -> int:
    load_dotenv(ROOT / ".env")
    uri = os.environ.get("LOCAL_MONGO_URI", "")
    ca = os.environ.get("LOCAL_MONGO_CA", "")

    if not uri:
        return fail("LOCAL_MONGO_URI jest pusty. Uzupełnij .env (wzór w .env.example).")
    if not ca:
        return fail("LOCAL_MONGO_CA jest pusty. Wskaż plik CA, np. certs/ca.pem.")
    if "tlsallowinvalidcertificates" in uri.lower():
        return fail("URI zawiera tlsAllowInvalidCertificates. To jest zabronione: weryfikacja certyfikatu musi działać.")

    ca_path = Path(ca)
    if not ca_path.is_absolute():
        ca_path = ROOT / ca_path
    if not ca_path.is_file():
        return fail(f"plik CA {ca_path} nie istnieje. Uruchom scripts/gen_certs.sh.")

    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        return fail("brak pakietu pymongo. Zainstaluj zależności: pip install -r requirements.txt.")

    client = MongoClient(uri, tls=True, tlsCAFile=str(ca_path), serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        status = client.admin.command("connectionStatus")
    except PyMongoError as exc:
        return fail(f"połączenie TLS z lokalnym MongoDB nie powiodło się: {exc}")
    finally:
        client.close()

    users = status.get("authInfo", {}).get("authenticatedUsers", [])
    if not users:
        return fail("połączenie TLS działa, ale klient nie jest uwierzytelniony (brak użytkownika w URI).")

    print(f"OK: TLS z weryfikacją certyfikatu (CA: {ca_path.name}), uwierzytelniony jako: "
          f"{', '.join(u['user'] for u in users)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
