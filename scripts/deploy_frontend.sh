#!/usr/bin/env bash
set -euo pipefail
cd /var/www/sitefixer/frontend
if [ -f package-lock.json ]; then npm ci; else npm install; fi
npm run build
if systemctl is-active --quiet caddy; then sudo systemctl reload caddy; fi
