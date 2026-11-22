#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
if [[ ! -f .env.deploy || ! -f .env.production ]]; then
    echo '请先运行 sudo bash deploy/install.sh。' >&2
    exit 1
fi
args=(--project-name bsign --env-file .env.deploy -f compose.yaml)
if grep -qx 'BSIGN_PROXY_MODE=caddy' .env.deploy; then
    args+=(-f compose.https.yaml)
elif ! grep -qx 'BSIGN_PROXY_MODE=external' .env.deploy; then
    echo '.env.deploy 中的代理模式无效。' >&2
    exit 1
fi
exec docker compose "${args[@]}" "$@"
