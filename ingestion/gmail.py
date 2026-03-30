"""
Fetch unread newsletter emails from Gmail via IMAP.

Returns a list of dicts:
    {
        "uid":      int,
        "subject":  str,
        "sender":   str,
        "date":     str,
        "html":     str | None,   # HTML body, preferred
        "text":     str | None,   # plain-text fallback
    }
"""

import email
import email.policy
import ssl
from datetime import date, timedelta
from email.message import EmailMessage

from imapclient import IMAPClient

import config

# Python 3.14 enforces strict X.509 validation that breaks on real-world CA
# chains (missing key usage extensions). For a personal tool connecting to a
# known host this is acceptable.
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _decode_part(part: EmailMessage) -> str:
    payload = part.get_payload(decode=True)
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _extract_bodies(msg: EmailMessage) -> tuple[str | None, str | None]:
    """Return (html_body, text_body) from a (possibly multipart) message."""
    html, text = None, None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            if ct == "text/html" and html is None:
                html = _decode_part(part)
            elif ct == "text/plain" and text is None:
                text = _decode_part(part)
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            html = _decode_part(msg)
        else:
            text = _decode_part(msg)

    return html, text


def fetch_newsletters(mark_seen: bool = True) -> list[dict]:
    """
    Connect to Gmail, fetch all messages received today in the configured
    mailbox, and return them as structured dicts.

    Args:
        mark_seen: if True, mark fetched messages as \\Seen after retrieval.
    """
    results = []

    # IMAP SINCE date format: "28-Mar-2026"
    today_str     = date.today().strftime("%-d-%b-%Y")
    yesterday_str = (date.today() - timedelta(days=1)).strftime("%-d-%b-%Y")

    # HuggingFace arrives at ~6pm the same day — use yesterday's date at 5am run
    _YESTERDAY_SENDERS = {"daily_papers_digest@notifications.huggingface.co", "adrij2005@gmail.com"}

    with IMAPClient(config.IMAP_HOST, port=config.IMAP_PORT, ssl=True, ssl_context=_SSL_CONTEXT) as client:
        client.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        client.select_folder(config.IMAP_MAILBOX, readonly=not mark_seen)

        # Fetch from each allowed sender with appropriate date window
        all_uids = set()
        for sender in config.NEWSLETTER_SENDERS:
            since = yesterday_str if any(s in sender for s in _YESTERDAY_SENDERS) else today_str
            matched = client.search(["SINCE", since, "FROM", sender])
            all_uids.update(matched)

        if not all_uids:
            return results

        messages = client.fetch(list(all_uids), ["RFC822"])

        for uid, data in messages.items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw, policy=email.policy.default)

            html_body, text_body = _extract_bodies(msg)

            results.append(
                {
                    "uid": uid,
                    "subject": msg.get("Subject", ""),
                    "sender": msg.get("From", ""),
                    "date": msg.get("Date", ""),
                    "html": html_body,
                    "text": text_body,
                }
            )

        if mark_seen and all_uids:
            client.set_flags(list(all_uids), [b"\\Seen"])

    return results


if __name__ == "__main__":
    newsletters = fetch_newsletters(mark_seen=False)
    print(f"Fetched {len(newsletters)} unread email(s)")
    for n in newsletters:
        print(f"  [{n['uid']}] {n['sender']} — {n['subject']} ({n['date']})")
        print(f"         html={len(n['html'] or '')} chars  text={len(n['text'] or '')} chars")
