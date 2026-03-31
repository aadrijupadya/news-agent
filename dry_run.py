"""
Dry run: newsletters only + mocked tweets. Does not mark emails as read.
"""

from datetime import date

from ingestion.gmail import fetch_newsletters
from processing.summarizer import process_newsletters
from processing.papers import (
    get_quote_of_the_day,
    get_word_of_the_day,
    is_hf_papers,
    process_hf_papers,
)
from delivery.renderer import render_digest
from delivery.email import send_digest
from delivery.webpage import write_webpage

MOCK_TWEETS = [
    {
        "account": "sama",
        "posts": [
            {"text": "intelligence too cheap to meter is going to be one of the most transformative things that has ever happened. we are not ready.", "url": "https://twitter.com/sama/status/1", "created_at": "2026-03-29"},
            {"text": "the thing that surprises me most is how quickly people adapt to new capabilities and immediately want 10x more.", "url": "https://twitter.com/sama/status/2", "created_at": "2026-03-29"},
        ],
    },
    {
        "account": "karpathy",
        "posts": [
            {"text": "Cursor/Claude are getting so good that I've started thinking of coding as more of a 'review and steer' activity than a 'write' activity.", "url": "https://twitter.com/karpathy/status/3", "created_at": "2026-03-29"},
        ],
    },
]


def run():
    today = date.today().strftime("%A, %B %-d %Y")
    print(f"=== Dry Run: {today} ===")

    print("\n[1/2] Fetching newsletters...")
    raw_newsletters = fetch_newsletters(mark_seen=False)
    print(f"      {len(raw_newsletters)} newsletter(s) fetched")

    if not raw_newsletters:
        print("No newsletters found. Exiting.")
        return

    print("\n[2/2] Processing + delivering...")
    hf_raw = [n for n in raw_newsletters if is_hf_papers(n)]
    other_raw = [n for n in raw_newsletters if not is_hf_papers(n)]

    newsletters = process_newsletters(other_raw)

    papers = []
    if hf_raw:
        print("      Selecting HuggingFace papers with Claude...")
        for n in hf_raw:
            papers.extend(process_hf_papers(n))
        print(f"      {len(papers)} paper(s) selected")

    print("      Generating quote of the day...")
    quote = get_quote_of_the_day()
    print("      Generating word of the day...")
    word = get_word_of_the_day()

    html = render_digest(newsletters, MOCK_TWEETS, today, papers=papers, quote=quote, word=word)
    print(f"      Rendered OK ({len(html):,} bytes)")

    write_webpage(newsletters, MOCK_TWEETS, today, papers=papers, quote=quote, word=word)

    print("\nDone.")


if __name__ == "__main__":
    run()
