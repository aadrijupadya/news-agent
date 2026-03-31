"""
Clean raw newsletter HTML before rendering.

- Strips invisible unicode spacers, tracking links, ads, sponsor blocks,
  and boilerplate (polls, trivia, daily quote).
- Preserves article links as "text (url)" for the renderer.
- Keeps ➤ bullets, section headers, and market data intact.
- Stocks & Income (Beehiiv): builds sanitized ``body_html`` (images + limited tags)
  and plain ``clean_text`` for fallback.
"""

import re
import unicodedata
from bs4 import BeautifulSoup, Tag


_AD_CLASS_RE = re.compile(
    r"(sponsor|advertisement|promo|unsubscribe|footer|nav|header|"
    r"tracking|pixel|beacon|utm_|optout|manage.pref)",
    re.IGNORECASE,
)

_DROP_TAGS = {
    "script", "style", "noscript", "iframe", "img",
    "head", "nav", "footer", "header",
}

# Paragraph-level blocks to drop entirely (match on first ~80 chars)
_SKIP_PARA_RE = re.compile(
    r"^(flying together with our sponsor|"
    r"today'?s .{1,40}(?:section|report) is brought to you|"
    r"enjoy reading .{1,30}\?|"
    r"click here to share|"
    r"have you ever|"
    r"yesterday'?s results|"
    r"daily quote|"
    r"today'?s trivia|"
    r"wisdom surfaces|"
    r"ladies and gentlemen.*most.clicked|"
    r"find support and relief|"
    r"bloating, irregularity|"
    r"over 50 and feeling|"
    r"who would have thought|"
    r"amazon prime members|"
    r"if you spend a good amount on amazon|"
    r"this card could put|"
    r"get approved|"
    r"see what you could get)",
    re.IGNORECASE,
)

_TRACKING_RE = re.compile(
    r"(utm_|/c/[a-zA-Z0-9_-]{10,}|click\.|email\.|track\.|go\.)",
    re.IGNORECASE,
)


def _is_ad_node(tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    attrs = tag.attrs or {}
    for attr in ("class", "id"):
        val = attrs.get(attr, "")
        if isinstance(val, list):
            val = " ".join(val)
        if val and _AD_CLASS_RE.search(val):
            return True
    return False


def _is_tracking_link(href: str) -> bool:
    if not href.startswith("http"):
        return True
    return bool(_TRACKING_RE.search(href))


def _strip_invisible(text: str) -> str:
    """Remove lines that consist entirely of invisible/formatting unicode chars."""
    result = []
    for line in text.splitlines():
        visible = [c for c in line.strip()
                   if unicodedata.category(c) not in ("Cf", "Zs", "Cc")]
        if visible:
            result.append(line)
        else:
            result.append("")   # preserve blank line structure
    return "\n".join(result)


def _strip_junk_paragraphs(text: str) -> str:
    """Drop paragraphs that match known sponsor/ad/boilerplate patterns."""
    paragraphs = text.split("\n\n")
    kept = []
    for para in paragraphs:
        first_line = para.strip().splitlines()[0] if para.strip() else ""
        if _SKIP_PARA_RE.match(first_line[:120]):
            continue
        kept.append(para)
    return "\n\n".join(kept)


def clean_newsletter_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()

    for tag in soup.find_all(True):
        if _is_ad_node(tag):
            tag.decompose()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not text:
            a.decompose()
        elif _is_tracking_link(href):
            a.replace_with(text)
        else:
            a.replace_with(f"{text} ({href})")

    raw = soup.get_text(separator="\n")
    raw = _strip_invisible(raw)

    # Collapse runs of blank lines to single blank line
    lines = [l.strip() for l in raw.splitlines()]
    collapsed = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                collapsed.append("")
            prev_blank = True
        else:
            collapsed.append(line)
            prev_blank = False

    text = "\n".join(collapsed).strip()
    text = _strip_junk_paragraphs(text)
    return text


def clean_newsletter(newsletter: dict) -> dict:
    from processing.beehiiv_clean import clean_stocks_income_html, is_stocks_income_newsletter

    if newsletter.get("html") and is_stocks_income_newsletter(newsletter):
        body_html = clean_stocks_income_html(newsletter["html"])
        plain = BeautifulSoup(body_html, "lxml").get_text(separator="\n")
        plain = _strip_invisible(plain)
        lines = [ln.strip() for ln in plain.splitlines()]
        collapsed: list[str] = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    collapsed.append("")
                prev_blank = True
            else:
                collapsed.append(line)
                prev_blank = False
        clean = "\n".join(collapsed).strip()
        return {**newsletter, "clean_text": clean, "body_html": body_html}
    if newsletter.get("html"):
        clean = clean_newsletter_html(newsletter["html"])
    else:
        clean = (newsletter.get("text") or "").strip()
    return {**newsletter, "clean_text": clean}
