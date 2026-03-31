import os
from dotenv import load_dotenv

load_dotenv()

# --- Gmail / IMAP ---
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")          # dedicated digest inbox address
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # Gmail App Password (not account password)
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_MAILBOX = os.getenv("IMAP_MAILBOX", "INBOX")
# Substring match against the From header (e.g. "Name <stocks-income@mail.beehiiv.com>")
STOCKS_INCOME_SENDER = "stocks-income@mail.beehiiv.com"
NEWSLETTER_SENDERS = [
    s.strip()
    for s in os.getenv(
        "NEWSLETTER_SENDERS",
        "news@editor.jointheflyover.com,dan@tldrnewsletter.com,adrij2005@gmail.com,"
        "daily_papers_digest@notifications.huggingface.co,stocks-income@mail.beehiiv.com",
    ).split(",")
    if s.strip()
]

# --- Claude API (used for HuggingFace paper selection only) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")  # cheap + fast for this task


# --- Email delivery (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")      # sender address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DIGEST_RECIPIENTS = [
    r.strip()
    for r in os.getenv("DIGEST_RECIPIENTS", "").split(",")
    if r.strip()
]

# --- Output ---
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")   # directory for the static HTML page
