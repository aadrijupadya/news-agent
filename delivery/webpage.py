"""
Write the digest as a static HTML file for web hosting / GitHub Pages.
"""

import os

from delivery.renderer import render_digest
import config


def write_webpage(newsletters: list[dict], tweets: list[dict], date: str, papers: list[dict] | None = None, quote: dict | None = None) -> str:
    """
    Render the digest and write it to OUTPUT_DIR/index.html.

    Args:
        newsletters: processed newsletter dicts
        tweets:      processed tweet summary dicts
        date:        human-readable date string

    Returns:
        Absolute path to the written file.
    """
    html = render_digest(newsletters, tweets, date, papers=papers, quote=quote)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.OUTPUT_DIR, "index.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Static page written to: {out_path}")
    return out_path
