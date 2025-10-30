#!/usr/bin/env bash
set -euo pipefail
ENV_FILE=/var/www/sitefixer/backend/.env
if [ -f "$ENV_FILE" ]; then echo "$ENV_FILE existiert"; exit 0; fi
cp /var/www/sitefixer/backend/.env.example "$ENV_FILE"
sed -i "s/CHANGE_ME_STRONG/$(openssl rand -hex 24)/g" "$ENV_FILE"
sed -i "s/CHANGE_ME_LONG_RANDOM/$(openssl rand -hex 32)/g" "$ENV_FILE"
