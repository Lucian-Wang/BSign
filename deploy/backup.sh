#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
[[ $EUID -eq 0 ]] || { echo '请使用 sudo 备份。'; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%S)-$$
install -d -m 0700 backups
temp="data/.backup-$stamp.db"
trap 'rm -f -- "$temp"' EXIT
# SQLite backup API includes committed WAL content without stopping the app.
python3 - "$temp" <<'PY'
import sqlite3,sys
from pathlib import Path
if not Path('data/bsign.db').is_file():sys.exit('数据库尚未创建。')
with sqlite3.connect('file:data/bsign.db?mode=ro',uri=True) as src, sqlite3.connect(sys.argv[1]) as dest:
    src.backup(dest)
PY
tar -czf "backups/bsign-$stamp.tar.gz" .env.production .env.deploy "$temp"
chmod 0600 "backups/bsign-$stamp.tar.gz"
echo "备份完成：$ROOT/backups/bsign-$stamp.tar.gz（包含解密密钥，请保密并异地保存）"
