"""
Shared Jinja2 rendering + content block parsing.

Two parsers:
  - parse_tldr()    for TLDR newsletter (category headers, headline+summary+link)
  - parse_flyover() for Flyover (section labels, ➤ bullets, market data, headlines)
  - Stocks & Income (Beehiiv): sanitized HTML fragment in body_html
"""

import re

import markupsafe
from jinja2 import Environment, FileSystemLoader, select_autoescape

import config

_TEMPLATE_DIR = __file__.replace("renderer.py", "templates")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)

_LINK_RE = re.compile(r'(.+?)\s+\((https?://[^\)]+)\)')

# TLDR category headers are ALL CAPS, 2+ words, sometimes with &
_ALLCAPS_RE = re.compile(r'^[A-Z][A-Z\s,&\-]{8,}$')
# "(X minute read)" or "(X min read)" suffix on TLDR headlines
_READ_TIME_RE = re.compile(r'\s*\(\d+\s+min(?:ute)?\s+read\)\s*$', re.IGNORECASE)

_TLDR_CATEGORY_CONNECTORS = frozenset(
    {"and", "or", "the", "a", "an", "of", "in", "to", "for", "vs", "as", "at", "&"}
)


def _is_tldr_category_header(line: str) -> bool:
    """
    True for TLDR section titles: ALL CAPS blocks or compact title-case lines
    (e.g. 'Big Tech and Startups', 'Programming, Design & Data Science').
    Excludes lines that look like stories (read time, inline link).
    """
    if _READ_TIME_RE.search(line) or _LINK_RE.search(line):
        return False
    if _ALLCAPS_RE.match(line) and len(line) > 6:
        return True
    raw_words = line.split()
    if len(raw_words) < 2 or len(line) < 12 or len(line) > 100:
        return False
    if line.endswith("."):
        return False
    content = [w.strip(",") for w in raw_words if w.strip(",") and w.strip(",") not in _TLDR_CATEGORY_CONNECTORS]
    if not (2 <= len(content) <= 12):
        return False
    for w in content:
        if not w[0].isupper():
            return False
    # Longer lines need tighter word count so we do not grab sentence-y blurbs
    if len(line) > 72 and len(content) > 6:
        return False
    return True

_FLYOVER_SECTION_RE = [
    (re.compile(r"flyover podcast", re.I),               "Flyover Podcast"),
    (re.compile(r"march madness", re.I),                 "March Madness"),
    (re.compile(r"today'?s rotator|most-clicked", re.I), "Most Clicked"),
    (re.compile(r"whatever happened to", re.I),          "Whatever Happened To…"),
]

_SKIP_LINE_RE = re.compile(
    r"^(previous week|bitcoin, gold, silver|clicking the link will take you|"
    r"flying together|brought to you by|see here the amazing|"
    r"no strings attached|tune in here|show me the answer|"
    r"good morning|on this day in).*$",
    re.IGNORECASE,
)

_DATE_LINE_RE = re.compile(
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),\s",
    re.IGNORECASE,
)


def _render_inline(text: str) -> markupsafe.Markup:
    """Escape and turn 'text (url)' patterns into <a> tags."""
    def replace_link(m):
        t = markupsafe.escape(m.group(1))
        u = markupsafe.escape(m.group(2))
        return f'<a href="{u}" target="_blank">{t}</a>'
    escaped = str(markupsafe.escape(text))
    return markupsafe.Markup(_LINK_RE.sub(replace_link, escaped))


# ── TLDR parser ────────────────────────────────────────────────────────────────

def parse_tldr(text: str) -> list[dict]:
    """
    Parse TLDR newsletter into blocks:
      {"type": "category",  "text": str}
      {"type": "story",     "headline": str, "summary": str, "url": str|None}

    Structure: category header, then repeating article title (often with min read)
    and summary; blanks between title and summary are optional.
    """
    lines = [l.strip() for l in text.splitlines()]
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line:
            i += 1
            continue

        if _SKIP_LINE_RE.match(line) or _DATE_LINE_RE.match(line):
            i += 1
            continue

        # Category header — ALL CAPS or title-case section line
        if _is_tldr_category_header(line):
            label = line.title() if _ALLCAPS_RE.match(line) else line
            blocks.append({"type": "category", "text": label})
            i += 1
            continue

        # Story headline — may have "(X minute read)" and/or an inline link
        # A headline is a short-ish line that isn't a paragraph
        is_short = len(line) < 120
        has_read_time = bool(_READ_TIME_RE.search(line))
        has_link = bool(_LINK_RE.search(line))

        if is_short and (has_read_time or has_link or (len(line.split()) <= 12 and len(line) > 15)):
            # Extract URL from the headline if present
            url = None
            m = _LINK_RE.search(line)
            if m:
                url = m.group(2)
                headline = _READ_TIME_RE.sub("", m.group(1)).strip()
            else:
                headline = _READ_TIME_RE.sub("", line).strip()

            # Collect following paragraph lines as the summary.
            # TLDR often inserts a blank line between headline and body; treat
            # those as separators to skip, not as "end of summary" before any text.
            i += 1
            summary_lines = []
            while i < len(lines):
                l = lines[i]
                if not l:
                    if summary_lines:
                        i += 1
                        break
                    i += 1
                    continue
                if _is_tldr_category_header(l) or _SKIP_LINE_RE.match(l):
                    break
                # Stop if next line also looks like a headline
                if len(l) < 120 and bool(_READ_TIME_RE.search(l)):
                    break
                summary_lines.append(l)
                i += 1

            summary = " ".join(summary_lines)
            # Extract link from summary if headline had none
            if not url:
                sm = _LINK_RE.search(summary)
                if sm:
                    url = sm.group(2)

            if headline:
                blocks.append({
                    "type": "story",
                    "headline": headline,
                    "summary": summary,
                    "url": url,
                })
            continue

        # Fallback — skip misc lines
        i += 1

    return blocks


def _render_tldr(text: str) -> markupsafe.Markup:
    blocks = parse_tldr(text)
    parts = []
    for block in blocks:
        if block["type"] == "category":
            label = markupsafe.escape(block["text"])
            parts.append(f'<div class="tldr-category"><span>{label}</span></div>')
        elif block["type"] == "story":
            hl = _render_inline(block["headline"])
            summary = _render_inline(block["summary"]) if block["summary"] else ""
            url = markupsafe.escape(block["url"]) if block["url"] else ""
            link_html = (
                f'<a class="story-read-link" href="{url}" target="_blank">Read more →</a>'
                if url else ""
            )
            parts.append(
                f'<div class="tldr-story">'
                f'<div class="tldr-headline">{hl}</div>'
                f'<p class="tldr-summary">{summary}</p>'
                f'{link_html}'
                f'</div>'
            )
    return markupsafe.Markup("\n".join(parts))


# ── Flyover parser ─────────────────────────────────────────────────────────────

def _is_flyover_headline(line: str, prev_blank: bool) -> bool:
    if not prev_blank:
        return False
    if len(line) < 15 or len(line) > 100:
        return False
    if line[0] in ("➤", "▼", "▲", "-", "•"):
        return False
    if _DATE_LINE_RE.match(line):
        return False
    if line.endswith(".") and len(line) > 60:
        return False
    words = line.split()
    if len(words) < 3:
        return False
    return any(w[0].isupper() for w in words if w.isalpha())


def _parse_market_block(lines: list[str], start: int) -> tuple[list[dict], int]:
    stocks = []
    i = start
    while i < len(lines):
        while i < len(lines) and not lines[i]:
            i += 1
        if i >= len(lines):
            break
        direction = lines[i]
        if direction not in ("▼", "▲"):
            break
        up = direction == "▲"
        i += 1

        def next_val():
            nonlocal i
            while i < len(lines) and not lines[i]:
                i += 1
            val = lines[i] if i < len(lines) else ""
            i += 1
            return val

        ticker = next_val()
        name   = next_val()
        price  = next_val()
        change = next_val()
        if ticker:
            stocks.append({"ticker": ticker, "name": name,
                           "price": price, "change": change, "up": up})
    return stocks, i


def _parse_flyover(text: str) -> list[dict]:
    lines = [l.strip() for l in text.splitlines()]
    blocks = []
    i = 0
    prev_blank = True

    while i < len(lines):
        line = lines[i]

        if not line:
            prev_blank = True
            i += 1
            continue

        if _SKIP_LINE_RE.match(line) or _DATE_LINE_RE.match(line):
            i += 1
            continue

        if "Weekly Market Report" in line:
            blocks.append({"type": "section_label", "text": "Markets"})
            i += 1
            stocks, i = _parse_market_block(lines, i)
            if stocks:
                blocks.append({"type": "market", "stocks": stocks})
            prev_blank = True
            continue

        if line in ("▼", "▲"):
            i += 1
            continue

        matched_label = None
        for pattern, label in _FLYOVER_SECTION_RE:
            if pattern.search(line):
                matched_label = label
                break
        if matched_label:
            blocks.append({"type": "section_label", "text": matched_label})
            prev_blank = True
            i += 1
            continue

        if line.startswith("➤"):
            items = []
            while i < len(lines) and lines[i].startswith("➤"):
                items.append(lines[i][1:].strip())
                i += 1
            blocks.append({"type": "bullets", "items": items})
            prev_blank = False
            continue

        if _is_flyover_headline(line, prev_blank):
            blocks.append({"type": "headline", "text": line})
            prev_blank = False
            i += 1
            continue

        para_lines = []
        while i < len(lines):
            l = lines[i]
            if not l:
                break
            if l.startswith("➤") or l in ("▼", "▲"):
                break
            if _SKIP_LINE_RE.match(l):
                i += 1
                continue
            if para_lines and _is_flyover_headline(l, prev_blank=True):
                break
            para_lines.append(l)
            i += 1
        if para_lines:
            blocks.append({"type": "paragraph", "text": " ".join(para_lines)})
        prev_blank = False

    return blocks


def _render_flyover(text: str) -> markupsafe.Markup:
    blocks = _parse_flyover(text)
    parts = []
    for block in blocks:
        btype = block["type"]
        if btype == "headline":
            t = _render_inline(block["text"])
            parts.append(f'<h3 class="story-headline">{t}</h3>')
        elif btype == "paragraph":
            t = _render_inline(block["text"])
            parts.append(f'<p class="story-para">{t}</p>')
        elif btype == "bullets":
            items_html = "".join(
                f'<li>{_render_inline(item)}</li>' for item in block["items"]
            )
            parts.append(f'<ul class="story-bullets">{items_html}</ul>')
        elif btype == "section_label":
            t = markupsafe.escape(block["text"])
            parts.append(f'<div class="section-divider"><span>{t}</span></div>')
        elif btype == "market":
            cards = []
            for s in block["stocks"]:
                direction = "up" if s["up"] else "down"
                arrow = "▲" if s["up"] else "▼"
                ticker = markupsafe.escape(s["ticker"])
                price  = markupsafe.escape(s["price"])
                change = markupsafe.escape(s["change"])
                cards.append(
                    f'<div class="stock-card {direction}">'
                    f'<div class="stock-ticker">{ticker}</div>'
                    f'<div class="stock-price">{price}</div>'
                    f'<div class="stock-change">{arrow} {change}</div>'
                    f'</div>'
                )
            parts.append(f'<div class="stock-grid">{"".join(cards)}</div>')
    return markupsafe.Markup("\n".join(parts))


def _render_stocks_income(newsletter: dict) -> markupsafe.Markup:
    """
    Render Beehiiv Stocks & Income digest from pre-sanitized HTML (images + basic
    typography). Falls back to Flyover-style plain text if body_html is empty.
    """
    html = (newsletter.get("body_html") or "").strip()
    if not html:
        return _render_flyover(newsletter.get("summary", ""))
    return markupsafe.Markup(f'<div class="stocks-income-body">{html}</div>')


# ── Jinja2 filters ─────────────────────────────────────────────────────────────

def _render_body(newsletter: dict) -> markupsafe.Markup:
    """Choose parser based on sender and available fields."""
    sender = newsletter.get("sender", "").lower()
    text = newsletter.get("summary", "")
    if config.STOCKS_INCOME_SENDER.lower() in sender:
        return _render_stocks_income(newsletter)
    if "tldr" in sender:
        return _render_tldr(text)
    return _render_flyover(text)


def _nl2br(value: str) -> markupsafe.Markup:
    escaped = markupsafe.escape(value)
    return markupsafe.Markup(str(escaped).replace("\n", "<br>\n"))


def _display_name(newsletter: dict) -> str:
    sender = newsletter.get("sender", "").lower()
    subject = newsletter.get("subject", "").lower()
    if config.STOCKS_INCOME_SENDER.lower() in sender:
        return "Stocks & Income"
    if "tldr" in sender or "tldr" in subject or "dan@tldrnewsletter" in sender:
        return "TLDR"
    if "flyover" in sender:
        return "The Flyover"
    if "huggingface" in sender or "daily papers" in subject:
        return "HuggingFace"
    # Fallback: strip email angle-bracket format "Name <email>"
    raw = newsletter.get("sender", "")
    m = re.match(r"^([^<]+)", raw)
    return m.group(1).strip() if m else raw


_env.filters["render_body"]   = _render_body
_env.filters["nl2br"]         = _nl2br
_env.filters["display_name"]  = _display_name


def render_digest(newsletters: list[dict], tweets: list[dict], date: str, papers: list[dict] | None = None, quote: dict | None = None) -> str:
    template = _env.get_template("digest.html.j2")
    return template.render(newsletters=newsletters, tweets=tweets, date=date, papers=papers or [], quote=quote or {})
