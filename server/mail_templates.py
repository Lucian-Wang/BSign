"""Self-contained transactional emails: no trackers or remote image dependencies."""
from html import escape


def verification_mail(code, purpose, language, origin):
    zh = language == 'zh'
    registration = purpose == 'register'
    title = ('验证邮箱，开始使用 BSign' if registration else '重置你的 BSign 密码') if zh else ('Verify your email for BSign' if registration else 'Reset your BSign password')
    intro = ('感谢选择 BSign 必签。请在注册页面输入以下验证码，完成邮箱验证并创建账户。' if registration else '我们收到了你的密码重置请求。请在找回密码页面输入以下验证码，并设置新密码。') if zh else ('Thank you for choosing BSign. Enter this code on the registration page to verify your email and create your account.' if registration else 'We received a request to reset your password. Enter this code on the password recovery page and choose a new password.')
    label = '邮箱验证码' if zh else 'EMAIL VERIFICATION CODE'
    expiry = '10 分钟内有效 · 仅限本次操作使用' if zh else 'Expires in 10 minutes · For this request only'
    safety = '请勿将验证码提供给任何人。BSign 工作人员不会向你索取验证码或密码。' if zh else 'Do not share this code. BSign staff will never ask for your verification code or password.'
    ignore = '如果这不是你的操作，请忽略本邮件，无需采取任何行动。' if zh else 'If you did not request this email, you can safely ignore it. No action is needed.'
    cta = ('返回注册页面' if registration else '返回找回密码页面') if zh else ('Continue registration' if registration else 'Continue password recovery')
    url = origin.rstrip('/') + ('/?action=register' if registration else '/#recover')
    footer = 'BSign 必签 · 文档签章工作台' if zh else 'BSign · Your document signing workspace'
    auto = '这是一封账户安全通知邮件，请勿直接回复。' if zh else 'This is an automated account security email. Please do not reply.'
    html = f'''<!doctype html><html lang="{'zh-CN' if zh else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f3f6ef;color:#183c32;font-family:Arial,'Microsoft YaHei',sans-serif"><div style="display:none;max-height:0;overflow:hidden">{escape(title)} · {escape(expiry)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:36px 16px"><table role="presentation" width="560" cellspacing="0" cellpadding="0" style="width:100%;max-width:560px">
<tr><td style="background:#194b3c;padding:26px 32px;border-radius:16px 16px 0 0;color:#fff"><strong style="font-size:26px;letter-spacing:-1px">BSign</strong><span style="margin-left:12px;color:#dce9c4;font-size:13px">必签</span><div style="margin-top:10px;font-size:11px;letter-spacing:2px;color:#dce9c4">ACCOUNT SECURITY</div></td></tr>
<tr><td style="background:#fff;padding:32px;border:1px solid #e2e9db;border-top:0;border-radius:0 0 16px 16px"><h1 style="font-size:23px;line-height:1.5;margin:0 0 18px">{escape(title)}</h1><p style="font-size:14px;line-height:1.9;margin:0 0 24px;color:#526c60">{escape(intro)}</p>
<div style="background:#f3f7e9;border:1px solid #dce6cb;border-radius:12px;text-align:center;padding:22px 10px"><div style="font-size:11px;letter-spacing:1px;color:#5e7568">{escape(label)}</div><div style="font-family:Consolas,monospace;font-size:36px;font-weight:bold;letter-spacing:8px;margin:14px 0">{escape(code)}</div><div style="font-size:12px;color:#5e7568">{escape(expiry)}</div></div>
<p style="font-size:13px;line-height:1.9;margin:22px 0;color:#526c60">{escape(safety)}</p><a href="{escape(url, quote=True)}" style="display:inline-block;padding:13px 22px;background:#194b3c;color:#fff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:bold">{escape(cta)} →</a>
<p style="font-size:12px;line-height:1.8;color:#78897e;border-top:1px solid #edf0e7;padding-top:22px;margin-top:26px">{escape(ignore)}</p></td></tr>
<tr><td align="center" style="padding:22px 12px;font-size:11px;line-height:1.9;color:#78897e">{escape(footer)}<br>{escape(auto)}</td></tr></table></td></tr></table></body></html>'''
    text = '\n\n'.join([title, intro, label + ': ' + code, expiry, safety, cta + ': ' + url, ignore, footer, auto])
    return {'subject': title + ' | BSign', 'html': html, 'text': text}
