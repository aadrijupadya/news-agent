"""
Daily news digest pipeline.

  1. Ingest  — fetch newsletters from Gmail (IMAP)
  2. Process — clean HTML
  3. Deliver — send HTML email + write static webpage
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
from delivery.email import send_digest
from delivery.webpage import write_webpage


def run():
    today = date.today().strftime("%A, %B %-d %Y")
    print(f"=== News Digest: {today} ===")

    print("\n[1/3] Fetching newsletters...")
    raw_newsletters = fetch_newsletters(mark_seen=True)
    print(f"      {len(raw_newsletters)} newsletter(s) fetched")

    if not raw_newsletters:
        print("Nothing to send.")
        return

    print("\n[2/3] Processing...")
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

    print("\n[3/3] Sending email + writing static page...")
    send_digest(newsletters, [], today, papers=papers, quote=quote, word=word)
    write_webpage(newsletters, [], today, papers=papers, quote=quote, word=word)

    print("\nDone.")


if __name__ == "__main__":
    run()
