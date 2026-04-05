#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/naviroom.conf"
DST="/etc/nginx/sites-available/naviroom.conf"

if [[ ! -f "$SRC" ]]; then
  echo "Source config not found: $SRC" >&2
  exit 1
fi

echo "Copying: $SRC -> $DST"
sudo cp -f "$SRC" "$DST"

# Ensure it's enabled (idempotent)
if [[ ! -L /etc/nginx/sites-enabled/naviroom.conf ]]; then
  echo "Enabling site: /etc/nginx/sites-enabled/naviroom.conf"
  sudo ln -s "$DST" /etc/nginx/sites-enabled/naviroom.conf
fi

echo "Testing nginx config"
sudo nginx -t

echo "Reloading nginx"
sudo systemctl reload nginx

echo "Done."
