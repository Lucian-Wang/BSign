"""Generate production configuration without reading secrets as shell code."""
import argparse
import base64
import os
from pathlib import Path
import re
import secrets


def configure(root, domain, email, admin_email, external):
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
        raise ValueError('域名应为 sign.example.com，不含协议、端口或路径。')
    for value in (email, admin_email):
        if not re.fullmatch(r'[^\s@=\x00-\x1f]+@[^\s@=\x00-\x1f]+\.[^\s@=\x00-\x1f]+', value):
            raise ValueError('请输入有效邮箱。')
    public = root / '.env.deploy'
    private = root / '.env.production'
    mode = 'external' if external else 'caddy'
    expected = f'DOMAIN={domain}\nACME_EMAIL={email}\nBSIGN_PROXY_MODE={mode}\n'
    if public.exists() or private.exists():
        if not public.is_file() or not private.is_file():
            raise ValueError('配置文件不完整，请恢复 .env.deploy 和 .env.production 后重试。')
        if public.read_text() != expected:
            raise ValueError('已有部署配置与参数不同。请使用原参数更新；迁移域名参照部署文档。')
        values = dict(line.split('=', 1) for line in private.read_text().splitlines() if line and not line.startswith('#'))
        if values.get('BSIGN_ORIGIN') != 'https://' + domain or values.get('BSIGN_ADMIN_EMAIL') != admin_email:
            raise ValueError('已有站点来源或管理员邮箱与参数不一致，请核对配置。')
        if len(base64.b64decode(values.get('BSIGN_MASTER_KEY', ''), validate=True)) != 32:
            raise ValueError('已有主密钥无效；请恢复备份，禁止自动替换。')
        return False
    token = secrets.token_urlsafe(32)
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    # Both files use literal KEY=value lines. Never source them in a shell.
    # The private file is read using Compose's env_file format: raw.
    content = (f'BSIGN_ORIGIN=https://{domain}\nBSIGN_ADMIN_EMAIL={admin_email}\n'
               f'BSIGN_MASTER_KEY={key}\nBSIGN_BOOTSTRAP_TOKEN={token}\n'
               'RESEND_API_KEY=\nRESEND_FROM=\n')
    for path, text in ((private, content), (public, expected)):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--domain', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--admin-email', required=True)
    parser.add_argument('--behind-proxy', action='store_true')
    args = parser.parse_args()
    try:
        fresh = configure(Path(__file__).resolve().parents[1], args.domain.lower(), args.email, args.admin_email.lower(), args.behind_proxy)
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print('已生成独立的生产密钥和部署配置。' if fresh else '已校验现有配置；密钥和数据保持不变。')
