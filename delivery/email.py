"""
Render the digest template and send it as an HTML email via SMTP.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from delivery.renderer import render_digest
import config


def send_digest(newsletters: list[dict], tweets: list[dict], date: str, papers: list[dict] | None = None, quote: dict | None = None) -> None:
    if not config.DIGEST_RECIPIENTS:
        print("No DIGEST_RECIPIENTS configured — skipping email send.")
        return

    html = render_digest(newsletters, tweets, date, papers=papers, quote=quote)
    print(f"      Rendered HTML size: {len(html):,} bytes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"News Digest — {date}"
    msg["From"] = config.SMTP_EMAIL
    msg["To"] = ", ".join(config.DIGEST_RECIPIENTS)
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print("      Connecting to SMTP (SSL port 465)...")
    with smtplib.SMTP_SSL(config.SMTP_HOST, 465, context=ctx, timeout=30) as server:
        print("      Logging in...")
        server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
        print("      Sending...")
        server.sendmail(config.SMTP_EMAIL, config.DIGEST_RECIPIENTS, msg.as_string())

    print(f"      Digest emailed to: {', '.join(config.DIGEST_RECIPIENTS)}")
