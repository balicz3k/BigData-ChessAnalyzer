#!/usr/bin/env bash
# Instaluje Dockera i wtyczkę Compose na Ubuntu/Debianie z pakietów dystrybucji
# (docker.io, docker-compose-v2) i dodaje Twojego użytkownika do grupy docker.
# Użycie: sudo scripts/install_docker.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "BŁĄD: skrypt wymaga uprawnień roota. Uruchom: sudo scripts/install_docker.sh" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
  echo "BŁĄD: nie wiem, którego użytkownika dodać do grupy docker." >&2
  echo "       Uruchom przez sudo ze zwykłego konta (nie jako root)." >&2
  exit 1
fi

if ! command -v apt-get > /dev/null; then
  echo "BŁĄD: brak apt-get. Skrypt obsługuje tylko Ubuntu/Debiana. Zainstaluj Dockera ręcznie." >&2
  exit 1
fi

apt-get update
apt-get install -y docker.io docker-compose-v2

systemctl enable --now docker
usermod -aG docker "$TARGET_USER"

echo
docker --version
docker compose version
echo "Test działania demona:"
docker run --rm hello-world | head -3

echo
echo "GOTOWE. Użytkownik $TARGET_USER jest w grupie docker, ale grupa zadziała dopiero po"
echo "WYLOGOWANIU I ZALOGOWANIU (albo restarcie komputera). Potem zrestartuj Cursora."
