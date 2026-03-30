# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal daily news digest agent. It fetches newsletters from a dedicated Gmail inbox (IMAP) and posts from specific X/Twitter accounts (Apify), processes them with Claude (strip ads, summarize, preserve TLDRs), then outputs an HTML email + static web page. Runs via GitHub Actions at 6am daily.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full digest pipeline
python main.py

# Run with a local .env file
cp .env.example .env   # then fill in values
python main.py

# Lint
ruff check .

# Format
ruff format .

# Tests
pytest
pytest tests/test_specific.py::test_name
```

## Architecture

```
ingestion/      — data fetching
  gmail.py      — IMAP connection, fetch unread newsletter emails
  twitter.py    — Apify client, fetch posts from configured X accounts

processing/     — Claude-powered transformation
  cleaner.py    — strip ads, boilerplate, tracking links from newsletter HTML
  summarizer.py — summarize articles/threads; preserve TLDR-style content as-is

delivery/       — output generation
  email.py      — build HTML email and send via SMTP
  webpage.py    — write static HTML file to OUTPUT_DIR

config.py       — all settings loaded from environment variables via python-dotenv
main.py         — orchestrator: ingestion → processing → delivery
.env.example    — template for required environment variables
output/         — generated static HTML pages (gitignored)
```

## Key Config Points

- All secrets are read from environment variables (see `.env.example`).
- `TWITTER_ACCOUNTS` and `DIGEST_RECIPIENTS` are comma-separated strings parsed into lists in `config.py`.
- `GMAIL_APP_PASSWORD` must be a Gmail App Password, not the account password — requires 2FA enabled.
- GitHub Actions secrets should mirror every key in `.env.example`.
