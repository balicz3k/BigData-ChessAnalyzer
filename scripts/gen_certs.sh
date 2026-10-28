#!/usr/bin/env bash
# Generuje lokalne CA i certyfikat serwera MongoDB w katalogu certs/.
# Wynik (nie trafia do gita): ca.pem, ca.key, server.pem (certyfikat + klucz), server.key.
# Użycie: scripts/gen_certs.sh [--force]
set -euo pipefail

cd "$(dirname "$0")/.."
CERT_DIR=certs
DAYS="${CERT_DAYS:-825}"

if ! command -v openssl > /dev/null; then
  echo "BŁĄD: brak polecenia openssl. Zainstaluj openssl i uruchom skrypt ponownie." >&2
  exit 1
fi

if [ -e "$CERT_DIR/ca.pem" ] && [ "${1:-}" != "--force" ]; then
  echo "BŁĄD: $CERT_DIR/ca.pem już istnieje. Użyj --force, żeby wygenerować wszystko od nowa" >&2
  echo "       (po zmianie CA trzeba zrestartować kontener mongo)." >&2
  exit 1
fi

mkdir -p "$CERT_DIR"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1. Lokalne CA. Rozszerzenia basicConstraints/keyUsage są obowiązkowe: Python 3.13+
#    weryfikuje certyfikaty w trybie ścisłym (VERIFY_X509_STRICT) i bez nich odrzuca CA.
openssl genrsa -out "$CERT_DIR/ca.key" 4096 2> /dev/null
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days "$DAYS" \
  -subj "/O=partie-lichess/CN=partie-lichess lokalne CA" \
  -addext "basicConstraints = critical, CA:TRUE" \
  -addext "keyUsage = critical, keyCertSign, cRLSign" \
  -addext "subjectKeyIdentifier = hash" \
  -out "$CERT_DIR/ca.pem"

# 2. Certyfikat serwera z SAN: localhost, mongo, 127.0.0.1
openssl genrsa -out "$CERT_DIR/server.key" 2048 2> /dev/null
openssl req -new -key "$CERT_DIR/server.key" \
  -subj "/O=partie-lichess/CN=localhost" -out "$tmp/server.csr"
cat > "$tmp/server.ext" << 'EOF'
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
subjectAltName = DNS:localhost, DNS:mongo, IP:127.0.0.1
EOF
openssl x509 -req -in "$tmp/server.csr" -CA "$CERT_DIR/ca.pem" -CAkey "$CERT_DIR/ca.key" \
  -CAcreateserial -CAserial "$tmp/ca.srl" -out "$tmp/server.crt" \
  -days "$DAYS" -sha256 -extfile "$tmp/server.ext" 2> /dev/null

# mongod chce certyfikat i klucz w jednym pliku
cat "$tmp/server.crt" "$CERT_DIR/server.key" > "$CERT_DIR/server.pem"

chmod 600 "$CERT_DIR/ca.key" "$CERT_DIR/server.key"
# Kontener mongo działa jako inny użytkownik i musi przeczytać server.pem z bind mounta.
# To lokalne CA do rozwoju, nie do produkcji.
chmod 644 "$CERT_DIR/ca.pem" "$CERT_DIR/server.pem"

echo "Gotowe. Pliki w $CERT_DIR/: ca.pem, ca.key, server.pem, server.key"
echo "W .env ustaw LOCAL_MONGO_CA=$CERT_DIR/ca.pem"
