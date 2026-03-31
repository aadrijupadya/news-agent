"""
Write the digest as static HTML for web hosting / GitHub Pages.

Writes ``index.html`` (always the latest run) and ``digest-YYYY-MM-DD.html``
for that calendar day so each date has a stable URL; same-day re-runs overwrite
the dated file and refresh ``index.html``.
"""

from datetime import date
from pathlib import Path

from delivery.renderer import render_digest
import config


def write_webpage(
    newsletters: list[dict],
    tweets: list[dict],
    display_date: str,
    papers: list[dict] | None = None,
    quote: dict | None = None,
    word: dict | None = None,
    run_date: date | None = None,
) -> str:
    """
    Render the digest and write ``index.html`` plus a dated archive file.

    Args:
        newsletters: processed newsletter dicts
        tweets:        processed tweet summary dicts
        display_date:  human-readable date string (shown in the digest)
        papers:        optional HuggingFace paper summaries
        quote:         optional quote-of-the-day dict
        word:          optional word-of-the-day dict
        run_date:      calendar day for the archive filename; defaults to today

    Returns:
        Absolute path to ``index.html``.
    """
    html = render_digest(newsletters, tweets, display_date, papers=papers, quote=quote, word=word)

    day = run_date or date.today()
    slug = day.isoformat()

    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    dated_path = out_dir / f"digest-{slug}.html"
    index_path = out_dir / "index.html"

    dated_path.write_text(html, encoding="utf-8")
    index_path.write_text(html, encoding="utf-8")

    print(f"Static page written to: {index_path}")
    print(f"Archive copy written to: {dated_path}")
    return str(index_path.resolve())
