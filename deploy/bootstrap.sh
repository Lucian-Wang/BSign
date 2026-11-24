#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

revision=24ad0b92517f035688ae6e9e158e91fefafdf686
checksum=1afaebe5331557f328566db39aa9cb3bc1b7a70fe91bbf3f93f9cb3dccccb774
target=/opt/BSign

usage() {
    cat <<'EOF'
用法：sudo bash bsign-install.sh --domain sign.example.com --email ops@example.com
可选参数：--admin-email EMAIL、--behind-proxy、--skip-docker-install
首次安装目录：/opt/BSign
完整说明：https://github.com/Lucian-Wang/BSign/blob/main/docs/DEPLOY.md
EOF
}

die() { printf '%s\n' "$*" >&2; exit 1; }

domain='' contact=''
args=("$@")
while (($#)); do
    case "$1" in
        --domain|--email|--admin-email)
            [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || die "缺少 $1 的值。"
            case "$1" in
                --domain) domain=$2 ;;
                --email) contact=$2 ;;
            esac
            shift 2 ;;
        --behind-proxy|--skip-docker-install) shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数：$1" ;;
    esac
done
[[ -n "$domain" && -n "$contact" ]] || { usage >&2; exit 1; }
[[ $EUID -eq 0 ]] || die '请使用 sudo 运行。'
[[ -r /etc/os-release ]] || die '需要 Ubuntu 或 Debian。'
. /etc/os-release
[[ ${ID:-} == ubuntu || ${ID:-} == debian ]] || die '需要 Ubuntu 或 Debian。'
[[ ! -e "$target" && ! -L "$target" ]] ||
    die "$target 已存在。请按部署指南更新或继续安装。"
for command in curl tar sha256sum; do
    command -v "$command" >/dev/null || die "缺少命令：$command"
done

work=$(mktemp -d /opt/.bsign-install.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
archive=$work/source.tar.gz
curl --fail --silent --show-error --location --proto '=https' \
    --connect-timeout 15 --max-time 600 --retry 2 \
    "https://codeload.github.com/Lucian-Wang/BSign/tar.gz/$revision" -o "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status ||
    die '源码包校验失败，请重新下载入口脚本后再试。'
mkdir "$work/source"
tar -xzf "$archive" -C "$work/source" --strip-components=1 --no-same-owner --no-same-permissions
[[ -f "$work/source/deploy/install.sh" && -f "$work/source/compose.yaml" ]] ||
    die '源码包缺少部署文件。'
mv -T -n -- "$work/source" "$target"
[[ ! -e "$work/source" ]] || die "$target 已存在，未覆盖原有文件。"
if ! bash "$target/deploy/install.sh" "${args[@]}"; then
    printf '源码已保留在 %s。解决上方错误后，可从该目录重新执行 deploy/install.sh。\n' "$target" >&2
    exit 1
fi
