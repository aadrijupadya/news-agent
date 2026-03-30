"""
Process newsletters and tweets for the digest.

Newsletters: clean HTML and pass through as-is (no LLM call).
Tweets: group by account, keep original posts only.
"""

from processing.cleaner import clean_newsletter


def process_newsletters(newsletters: list[dict]) -> list[dict]:
    """Clean newsletter HTML and set 'summary' to the cleaned text."""
    result = []
    for n in newsletters:
        cleaned = clean_newsletter(n)
        result.append({**cleaned, "summary": cleaned["clean_text"]})
    return result


