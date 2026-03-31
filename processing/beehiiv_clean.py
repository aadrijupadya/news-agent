"""
Sanitize Beehiiv / Stocks & Income HTML for in-digest rendering.

Keeps a small allowlist of tags, resolves https image URLs (incl. srcset / lazy
data-src), and drops scripts, iframes, and tracking-heavy links.
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag

import config

_AD_CLASS_RE = re.compile(
    r"(sponsor|advertisement|promo|unsubscribe|footer|nav|header|"
    r"tracking|pixel|beacon|utm_|optout|manage.pref)",
    re.IGNORECASE,
)

_TRACKING_RE = re.compile(
    r"(utm_|/c/[a-zA-Z0-9_-]{10,}|click\.|email\.|track\.|go\.)",
    re.IGNORECASE,
)


def _is_tracking_link(href: str) -> bool:
    if not href.startswith("http"):
        return True
    return bool(_TRACKING_RE.search(href))

_DECOMPOSE_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "meta",
        "link",
        "head",
        "button",
        "form",
        "input",
        "textarea",
        "select",
        "object",
        "embed",
    }
)

_ALLOWED_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "span",
        "strong",
        "b",
        "em",
        "i",
        "a",
        "img",
        "h1",
        "h2",
        "h3",
        "h4",
        "blockquote",
        "ul",
        "ol",
        "li",
        "figure",
        "figcaption",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "tr",
        "td",
        "th",
    }
)

_DISCLAIMER_HINTS = ("not financial advice", "do your own research", "past performance")


def is_stocks_income_newsletter(newsletter: dict) -> bool:
    """True if this message is the Stocks & Income Beehiiv digest."""
    sender = (newsletter.get("sender") or "").lower()
    return config.STOCKS_INCOME_SENDER.lower() in sender


def _is_ad_tag(tag: Tag) -> bool:
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


def _normalize_https_url(url: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return None
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("https://"):
        return u
    return None


def _img_resolved_src(tag: Tag) -> str | None:
    """Pick a usable https URL from src, data-src, or srcset."""
    for attr in ("src", "data-src", "data-original"):
        got = _normalize_https_url(tag.get(attr) or "")
        if got:
            return got
    ss = tag.get("srcset") or ""
    if not ss:
        return None
    candidates: list[str] = []
    for part in ss.split(","):
        chunk = part.strip().split()
        if not chunk:
            continue
        u = _normalize_https_url(chunk[0])
        if u:
            candidates.append(u)
    return candidates[-1] if candidates else None


def _mark_disclaimer_paragraphs(soup: BeautifulSoup) -> None:
    for p in soup.find_all("p"):
        t = p.get_text().lower()
        if any(h in t for h in _DISCLAIMER_HINTS) and len(t) < 400:
            p["class"] = "si-disclaimer"


def clean_stocks_income_html(html: str) -> str:
    """
    Return a sanitized HTML fragment safe to embed in the digest (trusted after
    this pass; still wrapped in a scoped div in the renderer).
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in list(soup.find_all(_DECOMPOSE_TAGS)):
        tag.decompose()

    for tag in soup.find_all(True):
        if _is_ad_tag(tag):
            tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.name not in _ALLOWED_TAGS:
            tag.unwrap()

    for a in list(soup.find_all("a")):
        href = _normalize_https_url(a.get("href") or "")
        if not href or _is_tracking_link(href):
            a.unwrap()
            continue
        a.attrs = {
            "href": href,
            "target": "_blank",
            "rel": "noopener noreferrer",
        }

    for img in list(soup.find_all("img")):
        src = _img_resolved_src(img)
        if not src:
            img.decompose()
            continue
        alt = (img.get("alt") or "")[:500]
        img.attrs = {"src": src, "alt": alt, "loading": "lazy"}

    for tag in soup.find_all(True):
        if tag.name in ("a", "img"):
            continue
        tag.attrs = {}

    _mark_disclaimer_paragraphs(soup)

    # Drop empty elements that add noise
    for tag in list(soup.find_all(["p", "div", "span"])):
        if isinstance(tag, Tag) and not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    body = soup.find("body")
    root: Tag | BeautifulSoup = body if body else soup
    # NavigableString nodes between tags
    parts: list[str] = []
    for child in getattr(root, "children", []):
        if isinstance(child, NavigableString):
            if str(child).strip():
                parts.append(str(child))
        elif isinstance(child, Tag):
            parts.append(str(child))
    fragment = "".join(parts).strip()
    if not fragment:
        fragment = root.decode_contents().strip()
    return fragment
