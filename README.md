# BSign / 必签 · 标准版

可自托管的中英文 PDF 盖章与签名工具。选择 PDF，导入公章或手写签名，拖动定位后导出。此仓库仅包含标准版，不含专业版远程合同、支付、短信、实名核验或生产部署配置。

## 功能

- PDF、JPG、PNG 本地导入；印章、签名、日期和文字叠加。
- 印章按企业分类保存；尺寸、透明度、旋转、骑缝章和手机操作。
- 手机扫码手写签名；账号和印章隔离、加密存储。
- RSA P12/PFX 证书导入、私有 CA 证书签发与 PDF 完整性验证。
- A4、300 DPI 图像化导出：原文文字层和原有数字签名不会保留。

## 本地启动

需要 Python 3.11+。已附浏览器运行依赖，直接启动无需 Node.js。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
Copy-Item .env.example .env
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

将两个输出分别填入 `.env` 的 `BSIGN_MASTER_KEY` 与 `BSIGN_BOOTSTRAP_TOKEN`。
设置自己的 `BSIGN_ADMIN_EMAIL`。注册和密码恢复需要配置 `RESEND_API_KEY` 与经过验证的 `RESEND_FROM`；不配置时发送验证码返回服务不可用，不跳过邮箱验证。

```powershell
python -m server.init_ca
python -m server.run
```

打开 `http://127.0.0.1:8090`。首次管理员设置打开 `http://127.0.0.1:8090/#setup=你的随机令牌`；完成后清空环境中的引导令牌并重启。管理员只管理用户，使用印章请另外注册普通账号。

Linux/macOS 使用 `source .venv/bin/activate`，用 `cp .env.example .env` 复制配置，其余 Python 命令相同。

## 自托管

启动入口 `server.run:app` 同时提供 API 与静态页面。生产部署请在 HTTPS 反向代理后运行，设置 `BSIGN_ORIGIN` 为实际站点来源；API 只绑定回环地址，反向代理覆盖客户端传入的 `X-Real-IP`。为 Word 转换预留至少 90 秒代理超时。仅静态部署无法使用账号及印章库。

数据位于 `BSIGN_DATA`，不要放进网站静态目录。主密钥必须持久保存，变更会导致旧印章和证书无法解密。数据库使用 SQLite WAL，在线备份请使用 SQLite backup API，并另行安全备份主密钥。不要将 `.env`、数据库或证书提交到 Git。

PDF 和图片文档不上传；保存的印章、手机签名和托管证书会传给本部署服务器。运营者掌握加密密钥。私有 CA/自签证书不证明身份，不提供公开可信链、吊销、时间戳或法律身份认证。导出文件的适用性由使用者确认。

## 可选 Word 转换

`server/word_converter.py` 是独立服务，主程序通过 `/run/bsign-converter/converter.sock` 调用。默认不启动；PDF/图片不受影响。Linux 上安装 LibreOffice Writer 与所需字体后，参照 `deploy/word-converter.service.example` 创建独立低权限用户、独立临时目录与服务。保持网络隔离，不给转换进程数据库、密钥或应用环境变量。转换中使用临时目录并在结束时清理。

## 开发与验证

```powershell
npm ci
npm run check
npm run build:certificate
npm run prepare:deploy
python -m unittest discover -s tests -p "test_*.py"
```

测试使用临时数据库、随机密钥与模拟邮件，不向真实邮箱发信。覆盖账号隔离、CSRF、印章加密、管理员权限、邮箱验证码及恢复流程。部署静态资源前运行 `prepare:deploy` 更新缓存标识。

源代码使用 ISC 许可，依赖许可见 `THIRD_PARTY_NOTICES.md`。本副本不包含原站用户数据、密钥、证书或 Git 历史，也不会自动发布到 GitHub。
