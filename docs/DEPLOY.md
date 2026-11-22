# 线上部署指南

推荐使用 Ubuntu 24.04 LTS 或 Debian 12/13，至少 2 GB 内存、10 GB 可用磁盘，能够访问 Docker 镜像仓库、Docker 软件源和 PyPI。脚本需要 root/sudo。已附浏览器依赖，无需安装 Node.js。

## 1. 准备域名与服务器

1. 将自己的域名（以下示例为 `sign.example.com`）A 记录指向服务器公网 IPv4。配置 AAAA 时也必须指向本服务器可用的 IPv6；不要保留错误 AAAA。
2. 在云安全组和系统防火墙放行 TCP 80、443；保留自己的 SSH 端口。应用的 8090 端口只绑定回环地址，无需对公网放行。
3. 首次部署建议 DNS 直接指向服务器，不开启 CDN 代理。
4. 确认服务器是否已有宝塔、Nginx 或 Apache 占用 80/443：有则使用下方“已有网站服务器”方案。

## 2. 新服务器：一条命令安装

先把本仓库下载到服务器。以 GitHub 仓库为例：

```bash
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/Lucian-Wang/BSign.git /opt/BSign
cd /opt/BSign
sudo bash deploy/install.sh --domain sign.example.com --email ops@example.com
```

请替换为自己的域名、邮箱。`--email` 用于 HTTPS 证书联系邮箱，同时默认作为管理员邮箱；可额外使用 `--admin-email admin@example.com` 单独指定管理员。

仓库未推送到 GitHub 前，可直接上传整个源码目录到 `/opt/BSign`，然后执行相同安装命令。不要上传原站数据库、密钥或个人 `.env`。

脚本会安装 Docker Engine/Compose（已安装则复用，要求 Compose 2.30+）、生成独立随机主密钥和管理员引导令牌、构建应用、初始化本部署私有 CA、启动容器，并通过 Caddy 申请和续期 HTTPS 证书。它不会修改已有防火墙规则或停止其他网站。若不希望自动安装 Docker，加 `--skip-docker-install`。

完成后打开 `https://sign.example.com`。脚本会显示管理员首次设置链接。自动证书申请依赖 DNS 正确解析以及 80/443 可达；失败时脚本会明确报错，不将 HTTPS 未完成视为部署成功。

## 3. 已有宝塔 / Nginx 网站服务器

不要让 Caddy 与现有网站抢占端口，使用：

```bash
cd /opt/BSign
sudo bash deploy/install.sh --domain sign.example.com --email ops@example.com --behind-proxy
```

脚本只启动 `127.0.0.1:8090` 应用。接着在宝塔创建 `sign.example.com` 站点，申请并启用 SSL、强制 HTTPS，将站点反向代理到 `http://127.0.0.1:8090`。

Nginx 配置参照 `deploy/nginx.conf.example`，放入已有 HTTPS `server` 中。必须保留 `Host $host`，覆盖 `X-Real-IP $remote_addr`，设置 90 秒超时和关闭请求缓冲。不要对 `/api/` 缓存，不要另外配置静态 `location` 覆盖应用路径。检查配置后重载：

```bash
sudo nginx -t && sudo systemctl reload nginx
curl --fail https://sign.example.com/api/health
```

应返回 `{"ok":true}`。宝塔站点的 PHP、伪静态无需启用。应用服务由 Docker 管理，不再额外配置 Python 项目守护进程。HTTPS 由原面板负责续期。

## 4. 管理员与邮箱注册

安装时创建两个权限为 600 的文件：

| 文件 | 内容 |
| --- | --- |
| `.env.deploy` | 域名、证书邮箱、代理模式 |
| `.env.production` | 站点来源、管理员邮箱、主密钥、引导令牌、邮件配置 |
| `data/bsign.db` | SQLite 数据库及其 WAL/SHM 文件，属主 10001:10001 |
| Docker 卷 `bsign_caddy_data` | Caddy 证书及续期状态（自动 HTTPS 模式） |

这些文件留在服务器，不提交 Git。`.env.production` 使用每行 `KEY=value` 的字面格式，**不要给值加引号，也不要用 `source` 执行这个文件**。即使密码或密钥包含 `$`，也按原值填写；Compose 使用 raw 模式读取。

普通用户注册和密码恢复必须配置 Resend。先在 Resend 验证自己的发信域名，再编辑：

```bash
sudo nano .env.production
```

填写：

```dotenv
RESEND_API_KEY=填写自己的API密钥
RESEND_FROM=BSign <noreply@your-domain.com>
```

重新创建应用容器使新环境生效：

```bash
sudo bash deploy/compose.sh up -d --force-recreate app
```

不配置邮件时首页可以访问，管理员仍可通过引导链接设置，但普通用户注册无法获得验证码。不会自动关闭邮箱验证。

管理员通过安装脚本显示的 `https://你的域名/#setup=随机令牌` 设置至少 12 位密码。管理员只能管理用户，实际使用印章需要注册普通用户。设置完成后将 `.env.production` 中 `BSIGN_BOOTSTRAP_TOKEN=` 清空，再执行上面的容器重建命令。

`BSIGN_MASTER_KEY` 必须长期保留，不能重生成，否则已有印章和证书无法解密。不要把管理员设置链接、配置文件或包含它们的日志发给别人。

## 5. 日常操作与更新

以下命令均在仓库目录执行。`compose.sh` 自动选择本部署的代理模式：

```bash
sudo bash deploy/compose.sh ps
sudo bash deploy/compose.sh logs --tail=100 app
sudo bash deploy/compose.sh logs --tail=100 caddy # 仅自动 HTTPS 模式
sudo bash deploy/compose.sh restart app
sudo bash deploy/compose.sh down
sudo bash deploy/compose.sh up -d --wait
```

Docker 服务启动时容器自动恢复；`down` 会停止并移除容器，保留 bind 数据目录及具名卷。不要使用 `down -v` 删除证书卷。

更新前先备份，再拉取源码并重新运行**原来的部署命令**：

```bash
sudo bash deploy/backup.sh
sudo git pull --ff-only
sudo bash deploy/install.sh --domain sign.example.com --email ops@example.com
# 原来使用 --behind-proxy 或 --admin-email 的，更新时也带上相同参数。
```

脚本会保留现有密钥、数据库、邮件配置和 CA；已有数据库时还会自动备份。它拒绝使用不同域名或管理员邮箱悄悄覆盖旧配置。更新构建期间旧容器继续运行，替换启动有短暂中断；无自动回滚。启动失败先查看日志，保留数据后再处理。

迁移域名需先备份，然后同步修改 `.env.deploy` 的 `DOMAIN`、`.env.production` 的 `BSIGN_ORIGIN=https://新域名`，确认 DNS/HTTPS 后重新运行安装命令。保留 `BSIGN_MASTER_KEY`；原管理员邮箱保持不变。

## 6. 备份与恢复

```bash
sudo bash deploy/backup.sh
```

输出在 `backups/bsign-时间戳.tar.gz`。使用 SQLite backup API 读取已提交 WAL 内容，适合运行中备份；不要直接复制运行中的单个数据库文件。归档包含数据库与解密密钥，只有 root 可读，需放到受控的异地存储；其泄漏会同时泄漏数据和解密能力。脚本不自动上传或删除旧备份。

恢复到干净的新源码目录（或停机后、已另行备份的旧目录）：

```bash
sudo bash deploy/compose.sh down  # 新目录未部署时跳过
sudo tar -xzf /安全位置/bsign-时间戳.tar.gz -C /opt/BSign
cd /opt/BSign
# 选择刚解压出来的 data/.backup-时间戳.db 的确切文件名，不要使用通配符覆盖
sudo mv -- data/.backup-时间戳.db data/bsign.db
# 仅恢复到已有停机目录时清理原数据库的旧 WAL/SHM
sudo rm -f -- data/bsign.db-wal data/bsign.db-shm
sudo chown -R 10001:10001 data
sudo chmod 700 data
sudo chmod 600 .env.production .env.deploy
sudo bash deploy/install.sh --domain sign.example.com --email ops@example.com
```

恢复时必须用备份内的主密钥，不能用新生成的密钥。Caddy 证书卷不在应用备份内；新机器会重新申请证书，需满足公网 DNS/端口条件并注意证书机构限额。

## 7. 故障排查

| 现象 | 检查 |
| --- | --- |
| 无法下载镜像/依赖 | 服务器能否访问 Docker、PyPI；按自己的网络环境配置代理或可信镜像源后重试 |
| 80/443 被占用 | 使用 `--behind-proxy`，不要停止已有网站 |
| HTTPS 失败 | 域名 A/AAAA、云安全组、系统防火墙、CDN、`logs caddy` |
| 502 / 应用不健康 | `logs app`、`data` 的 UID/GID 10001:10001、主密钥是否有效 |
| Invalid request origin | `BSIGN_ORIGIN` 与实际 HTTPS 域名一致，代理保留 Host，避免 IP/另一个域名访问 |
| 验证码不可用 | Resend API key、已验证发信域名及发件地址；编辑后 force-recreate app |
| 手机扫码访问失败 | 手机能否访问公网域名；不要使用服务器回环地址或仅电脑可访问的内网地址 |

## 8. Word 转换范围

本次一键部署包括 PDF/JPG/PNG、本地盖章、印章库、手机签名、证书签署及验证。**不启动 Word 转换服务**：上传 DOC/DOCX 会提示转换服务不可用。

Word 转换需单独部署 LibreOffice 隔离服务。现有 `deploy/word-converter.service.example` 是手动部署参考；容器方案需额外配置宿主 Unix socket 的只读挂载与一致的组权限，再单独安装、测试 LibreOffice。不要直接在主应用容器内开放转换或将应用环境密钥传给转换进程。若只处理 PDF，无需安装此服务。
