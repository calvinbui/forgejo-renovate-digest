# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this does

Single-file Python script (`main.py`) that fetches all pull requests opened or updated in the last 24 hours from a Forgejo repository and sends a summary email via SMTP. Designed for use with Renovate bot to track dependency update PRs.

## Setup and running

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in values
python main.py
```

All configuration is via environment variables (loaded from `.env` by `python-dotenv`). All vars are required except `SMTP_PORT` (default `587`) and `SMTP_TLS` (default `true`). See `.env.example` for the full list.

## Architecture

Everything lives in `main.py` with four functions in a linear pipeline:

1. `get_config()` — loads and validates env vars, exits on missing required vars
2. `fetch_prs_last_24h()` — paginates the Forgejo `/api/v1/repos/{owner}/{repo}/pulls` endpoint sorted by `recentupdate`, stops early once PRs older than 24 hours are encountered
3. `build_email()` — splits PRs into "new" vs "updated" (by `created_at` vs 24h threshold), returns both plain-text and HTML bodies
4. `send_email()` — sends via `smtplib` with optional STARTTLS

The `FORGEJO_REPO` value (`owner/repo` format) is used both as the API path segment and as the display label in the email.
