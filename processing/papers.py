"""
Parse HuggingFace Daily Papers email and use Claude to select and summarize
the 3-5 most interesting papers for a non-specialist tech audience.
"""

import hashlib
import json
import os
import re
from pathlib import Path

import anthropic
import requests

import config

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Matches lines like: "Paper Title Here (42 ▲)" or "Paper Title Here (42 ▲),"
_PAPER_LINE_RE = re.compile(r"([A-Z][^\n(]{10,}?)\s*\((\d+)\s*(?:▲|↑|▲)\)", re.UNICODE)

_PROMPT = """\
You are a research assistant helping a tech-savvy but non-specialist reader \
understand today's most interesting AI papers.

Below is a list of papers from HuggingFace Daily Papers with their upvote counts.

Select the 3-5 most interesting or impactful papers — consider both upvotes and \
significance of the topic. For each selected paper, write exactly 2 sentences: \
the first explains what the paper does, the second explains why it matters or \
what's novel about it. Be concrete, not vague.

Papers:
{papers}

Respond ONLY as a JSON array, no preamble, in this exact format:
[
  {{"title": "...", "summary": "..."}},
  ...
]"""


_QUOTE_PROMPT = """\
Generate a single thought-provoking quote for today's morning digest. \
It should be from a real, notable person — a scientist, philosopher, entrepreneur, \
writer, or historical figure. Choose someone whose ideas are genuinely interesting.

Respond ONLY as JSON: {"quote": "...", "author": "...", "context": "..."}
Where context is one short phrase describing who they are (e.g. "physicist & Nobel laureate")."""

_WORD_PROMPT = """\
Generate a single "Word of the Day" for a smart, curious general audience.
Choose an uncommon but useful English word (not obscure to the point of unusable).

Respond ONLY as JSON:
{"word": "...", "meaning": "...", "example": "..."}
"""

_HISTORY_FILE = "history.json"
_MAX_HISTORY = 500
_PROMPT_HISTORY_WINDOW = 50


def _history_url() -> str:
    """
    Return a URL to fetch persisted history from, if available.

    Priority:
      1) DIGEST_HISTORY_URL env var
      2) raw.githubusercontent.com/<repo>/gh-pages/history.json (in Actions)
    """
    explicit = os.getenv("DIGEST_HISTORY_URL", "").strip()
    if explicit:
        return explicit
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        return ""
    return f"https://raw.githubusercontent.com/{repo}/gh-pages/{_HISTORY_FILE}"


def _history_path() -> Path:
    """Return local history file path inside OUTPUT_DIR."""
    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / _HISTORY_FILE


def _load_history() -> dict:
    """
    Load history from local file if present; else bootstrap from remote URL.

    Storage is intentionally minimal:
      {"quotes": ["<sha1>", ...], "words": ["<lowercase-word>", ...]}
    """
    path = _history_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {"quotes": [], "quote_pairs": [], "words": []}
            payload.setdefault("quotes", [])
            payload.setdefault("quote_pairs", [])
            payload.setdefault("words", [])
            return payload
        except Exception:
            return {"quotes": [], "quote_pairs": [], "words": []}

    remote = _history_url()
    if remote:
        try:
            resp = requests.get(remote, timeout=5)
            if resp.ok:
                payload = resp.json()
                if isinstance(payload, dict):
                    payload.setdefault("quotes", [])
                    payload.setdefault("quote_pairs", [])
                    payload.setdefault("words", [])
                    return payload
        except Exception:
            pass
    return {"quotes": [], "quote_pairs": [], "words": []}


def _save_history(history: dict) -> None:
    """Persist de-duplicated bounded history to OUTPUT_DIR/history.json."""
    quotes = list(dict.fromkeys(history.get("quotes", [])))[:_MAX_HISTORY]
    quote_pairs = list(dict.fromkeys(history.get("quote_pairs", [])))[:_MAX_HISTORY]
    words = list(dict.fromkeys(history.get("words", [])))[:_MAX_HISTORY]
    payload = {"quotes": quotes, "quote_pairs": quote_pairs, "words": words}
    _history_path().write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _quote_key(quote: dict) -> str:
    """Return stable hash key for quote de-duplication."""
    core = f"{quote.get('quote', '').strip()}|{quote.get('author', '').strip()}".lower()
    return hashlib.sha1(core.encode("utf-8")).hexdigest()


def _parse_json_response(text: str) -> dict:
    """Parse Claude JSON response, stripping markdown fences if present."""
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def get_quote_of_the_day() -> dict:
    """
    Return non-repeating {"quote": str, "author": str, "context": str} and persist
    minimal quote history.
    """
    history = _load_history()
    seen = set(history.get("quotes", []))
    seen_pairs = [s for s in history.get("quote_pairs", []) if isinstance(s, str) and s.strip()]
    exclusion = ""
    if seen_pairs:
        exclusion = "Avoid reusing these recent quote/author pairs:\n" + "\n".join(
            f"- {pair}" for pair in seen_pairs[-_PROMPT_HISTORY_WINDOW:]
        )
    prompt = _QUOTE_PROMPT + ("\n\n" + exclusion if exclusion else "")
    for _ in range(4):
        try:
            message = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=220,
                messages=[{"role": "user", "content": prompt}],
            )
            candidate = _parse_json_response(message.content[0].text)
            if not candidate.get("quote") or not candidate.get("author"):
                continue
            key = _quote_key(candidate)
            if key in seen:
                continue
            history.setdefault("quotes", []).append(key)
            history.setdefault("quote_pairs", []).append(
                f"{candidate.get('quote', '').strip()} — {candidate.get('author', '').strip()}"
            )
            _save_history(history)
            return candidate
        except Exception:
            continue
    return {}


def get_word_of_the_day() -> dict:
    """
    Return non-repeating {"word": str, "meaning": str, "example": str} and persist
    minimal word history.
    """
    history = _load_history()
    seen = {w.strip().lower() for w in history.get("words", []) if isinstance(w, str)}
    avoid_words = ", ".join(sorted(seen)[-50:])
    prompt = _WORD_PROMPT + (f"\nAvoid these words: {avoid_words}" if avoid_words else "")
    for _ in range(4):
        try:
            message = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=220,
                messages=[{"role": "user", "content": prompt}],
            )
            candidate = _parse_json_response(message.content[0].text)
            word = str(candidate.get("word", "")).strip()
            if not word:
                continue
            key = word.lower()
            if key in seen:
                continue
            history.setdefault("words", []).append(key)
            _save_history(history)
            return {
                "word": word,
                "meaning": str(candidate.get("meaning", "")).strip(),
                "example": str(candidate.get("example", "")).strip(),
            }
        except Exception:
            continue
    return {}


def parse_papers_from_html(html_body: str) -> list[dict]:
    """
    Parse paper titles and upvote counts from HF email HTML.
    The title is in an <a> tag; upvote count is in a nearby text node
    formatted as '(NUMBER' with the ▲ in a separate element.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_body, "lxml")
    papers = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        # Get all text in the parent element to find the upvote count
        parent = a.parent
        if not parent:
            continue
        parent_text = parent.get_text(separator=" ")

        # Look for "(NUMBER" pattern anywhere after the title
        title_pos = parent_text.find(title)
        after = parent_text[title_pos + len(title):] if title_pos >= 0 else parent_text
        m = re.search(r"\(\s*(\d+)", after)
        if m:
            upvotes = int(m.group(1))
            if upvotes > 0:
                papers.append({"title": title, "upvotes": upvotes})

    # Deduplicate by title, keep highest upvotes
    seen = {}
    for p in papers:
        if p["title"] not in seen or p["upvotes"] > seen[p["title"]]:
            seen[p["title"]] = p["upvotes"]

    return sorted(
        [{"title": t, "upvotes": u} for t, u in seen.items()],
        key=lambda p: p["upvotes"],
        reverse=True,
    )


def select_and_summarize(papers: list[dict]) -> list[dict]:
    """Call Claude to pick the top papers and write summaries."""
    if not papers:
        return []

    papers_text = "\n".join(
        f"- {p['title']} ({p['upvotes']} upvotes)" for p in papers
    )

    message = _client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": _PROMPT.format(papers=papers_text)}],
    )

    import json
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def process_hf_papers(newsletter: dict) -> list[dict]:
    """
    Given a HuggingFace newsletter dict, return a list of selected
    paper dicts: [{"title": str, "summary": str}, ...]
    """
    html_body = newsletter.get("html", "")
    if not html_body:
        return []
    papers = parse_papers_from_html(html_body)
    if not papers:
        return []
    return select_and_summarize(papers)


def is_hf_papers(newsletter: dict) -> bool:
    sender = newsletter.get("sender", "").lower()
    subject = newsletter.get("subject", "").lower()
    return (
        "huggingface" in sender
        or "daily_papers" in sender
        or "daily papers" in subject
        or "huggingface" in subject
    )
