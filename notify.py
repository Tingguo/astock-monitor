"""Gmail SMTP 发信（复用 Hermes 同款：GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO）。"""

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
MAIL_TO = os.environ.get("MAIL_TO", "")


def send_email(subject: str, body: str) -> None:
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and MAIL_TO):
        raise RuntimeError("未设置 GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("A股回踩低吸盯盘", GMAIL_USER))
    msg["To"] = MAIL_TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [MAIL_TO], msg.as_string())
    print("[OK] 通知邮件已发送")
