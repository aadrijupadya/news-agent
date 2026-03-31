# news-agent

A personal daily news digest that pulls from newsletters and AI research papers, formats everything into a clean HTML email, and delivers it every morning automatically via GitHub Actions.

## What it does

Every morning at **5am PST (1pm UTC)**, the pipeline:

1. **Fetches** newsletters from a dedicated Gmail inbox via IMAP
2. **Selects** the top HuggingFace AI papers using Claude Haiku
3. **Generates** a quote of the day using Claude Haiku
4. **Renders** a styled HTML digest
5. **Emails** it to configured recipients and saves `output/index.html`

## Sources

| Source | Sender | Window |
|---|---|---|
| The Flyover | `news@editor.jointheflyover.com` | Today |
| TLDR Newsletter | `dan@tldrnewsletter.com` | Today |
| HuggingFace Daily Papers | `daily_papers_digest@notifications.huggingface.co` | Yesterday (arrives 6pm PST) |
| Stocks & Income | `stocks-income@mail.beehiiv.com` | Today |

## Project structure

```
ingestion/      Gmail IMAP fetching
processing/     HTML cleaning (incl. Beehiiv rich HTML), HF papers, quote
delivery/       Jinja2 rendering, SMTP email, static HTML output
main.py         Production entry point
dry_run.py      Local testing — does not mark emails as read, skips email send
```

## Running locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
python dry_run.py      # preview only
python main.py         # full run (sends email, marks emails read)
```

## Environment variables

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|---|---|
| `GMAIL_EMAIL` | Gmail address of the digest inbox |
| `GMAIL_APP_PASSWORD` | Gmail App Password (requires 2FA) |
| `SMTP_EMAIL` / `SMTP_PASSWORD` | Sender credentials for outbound email |
| `DIGEST_RECIPIENTS` | Comma-separated list of recipient emails |
| `ANTHROPIC_API_KEY` | Used for HF paper selection and quote of the day |

## GitHub Actions setup

Secrets must be added at **repo → Settings → Secrets and variables → Actions**:

`GMAIL_EMAIL`, `GMAIL_APP_PASSWORD`, `SMTP_EMAIL`, `SMTP_PASSWORD`, `DIGEST_RECIPIENTS`, `ANTHROPIC_API_KEY`

Trigger a manual run anytime via **Actions → Daily Digest → Run workflow**.
