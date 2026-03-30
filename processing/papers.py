"""
Parse HuggingFace Daily Papers email and use Claude to select and summarize
the 3-5 most interesting papers for a non-specialist tech audience.
"""

import re

import anthropic

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


def get_quote_of_the_day() -> dict:
    """Return {"quote": str, "author": str, "context": str} from Claude Haiku."""
    try:
        message = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": _QUOTE_PROMPT}],
        )
        import json, re
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)
    except Exception:
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
