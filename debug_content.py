"""Dump cleaned newsletter text to see what we're working with."""
from ingestion.gmail import fetch_newsletters
from processing.cleaner import clean_newsletter

newsletters = fetch_newsletters(mark_seen=False)
for n in newsletters:
    cleaned = clean_newsletter(n)
    print(f"=== {n['sender']} — {n['subject']} ===\n")
    print(cleaned["clean_text"])
    print("\n" + "="*80 + "\n")
