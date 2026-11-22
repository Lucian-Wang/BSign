#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
trap 'echo "部署未完成（第 $LINENO 行）。查看：sudo bash deploy/compose.sh ps；sudo bash deploy/compose.sh logs --tail=80" >&2' ERR
usage() {
    cat <<'EOF'
用法：sudo bash deploy/install.sh --domain sign.example.com --email ops@example.com [选项]
  --admin-email EMAIL   管理员邮箱，默认等于 --email
  --behind-proxy       已有宝塔/Nginx：仅启动本地 8090 后端，不占用 80/443
  --skip-docker-install 不自动安装 Docker
重复运行相同命令更新应用，保留密钥、配置、数据库和 CA。
EOF
}
domain='' contact='' admin='' external=false skip=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain|--email|--admin-email)
            [[ $# -ge 2 && -n "$2" ]] || { usage; exit 1; }
            case "$1" in
                --domain) domain=$2;;
                --email) contact=$2;;
                --admin-email) admin=$2;;
            esac
            shift 2;;
        --behind-proxy) external=true; shift;;
        --skip-docker-install) skip=true; shift;;
        -h|--help) usage; exit 0;;
        *) usage; exit 1;;
    esac
done
[[ $EUID -eq 0 ]] || { echo '请使用 sudo 运行。' >&2; exit 1; }
[[ -n "$domain" && -n "$contact" ]] || { usage; exit 1; }
admin=${admin:-$contact}
[[ -f /etc/os-release ]] || { echo '需要 Ubuntu 或 Debian 服务器。'; exit 1; }
. /etc/os-release
[[ $ID == ubuntu || $ID == debian ]] || { echo '脚本支持 Ubuntu / Debian；其他系统请手动安装 Docker。'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl python3
if ! command -v docker >/dev/null; then
    [[ $skip == false ]] || { echo '请先安装 Docker Engine 和 Compose 插件。'; exit 1; }
    # Docker's signed official apt repository; do not run a remote shell installer.
    install -m 0755 -d /etc/apt/keyrings
    curl --fail --silent --show-error --location "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
    chmod 0644 /etc/apt/keyrings/docker.asc
    arch=$(dpkg --print-architecture)
    codename=${UBUNTU_CODENAME:-$VERSION_CODENAME}
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' "$arch" "$ID" "$codename" > /etc/apt/sources.list.d/bsign-docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
fi
docker info >/dev/null
version=$(docker compose version --short)
python3 - "$version" <<'PY'
import re,sys
match=re.match(r'v?(\d+)\.(\d+)',sys.argv[1])
if not match or tuple(map(int,match.groups())) < (2,30):
    sys.exit('需要 Docker Compose 2.30+，请升级 docker-compose-plugin。')
PY
if [[ $external == false && ! -f .env.deploy ]] && command -v ss >/dev/null; then
    if ss -H -ltn '( sport = :80 or sport = :443 )' | grep -q .; then
        echo '80/443 已被占用。已有宝塔/Nginx 时请使用 --behind-proxy，详见 docs/DEPLOY.md。' >&2
        exit 1
    fi
fi
config=(--domain "$domain" --email "$contact" --admin-email "$admin")
[[ $external == false ]] || config+=(--behind-proxy)
python3 deploy/configure.py "${config[@]}"
chmod 0600 .env.production .env.deploy
if [[ ! -d data ]]; then
    install -d -o 10001 -g 10001 -m 0700 data
fi
[[ $(stat -c %u data) == 10001 && $(stat -c %g data) == 10001 ]] || {
    echo 'data 目录必须属于 10001:10001，请检查数据目录权限。' >&2; exit 1;
}
if [[ -f data/bsign.db ]]; then
    bash deploy/backup.sh
fi
bash deploy/compose.sh config --quiet
bash deploy/compose.sh build --pull app
if [[ $external == false ]]; then bash deploy/compose.sh pull caddy; fi
bash deploy/compose.sh run --rm --no-deps app python -m server.init_ca
bash deploy/compose.sh up -d --wait --wait-timeout 180
curl --fail --silent --show-error http://127.0.0.1:8090/api/health >/dev/null
if [[ $external == false ]]; then
    if ! curl --fail --silent --show-error --retry 12 --retry-all-errors --retry-delay 5 --max-time 10 "https://$domain/api/health" >/dev/null; then
        echo '后端已启动，但公网 HTTPS 尚未通过。检查 DNS、80/443、防火墙及 Caddy 日志。' >&2
        exit 1
    fi
else
    echo '本地后端已就绪：127.0.0.1:8090。请按 docs/DEPLOY.md 配置已有站点的 HTTPS 反向代理。'
fi
python3 - <<'PY'
from pathlib import Path
v=dict(line.split('=',1) for line in Path('.env.production').read_text().splitlines() if line and not line.startswith('#'))
print('站点：'+v['BSIGN_ORIGIN'])
if v.get('BSIGN_BOOTSTRAP_TOKEN'):
    print('管理员首次设置（保密）：'+v['BSIGN_ORIGIN']+'/#setup='+v['BSIGN_BOOTSTRAP_TOKEN'])
print('注册和密码恢复需在 .env.production 配置 RESEND_API_KEY、RESEND_FROM，然后重建应用容器。')
PY
