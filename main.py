"""
Forgejo Daily PR Summary Emailer
Fetches all PRs opened today in a given repo and sends a summary email via SMTP.
Configuration is read from a .env file or environment variables.
"""

import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import os

import requests
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    """Return the value of a required environment variable, exiting if absent."""
    value = os.getenv(name, "").strip()
    if not value:
        print(f"ERROR: Missing required config: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def get_config() -> dict:
    """Load and return all configuration from environment variables."""
    return {
        "forgejo_url": require_env("FORGEJO_URL").rstrip("/"),
        "forgejo_token": require_env("FORGEJO_TOKEN"),
        "repo": require_env("FORGEJO_REPO"),  # format: owner/repo
        "smtp_host": require_env("SMTP_HOST"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": require_env("SMTP_USER"),
        "smtp_password": require_env("SMTP_PASSWORD"),
        "email_from": require_env("EMAIL_FROM"),
        "email_to": require_env("EMAIL_TO"),
        "smtp_tls": os.getenv("SMTP_TLS", "true").lower() != "false",
    }


def fetch_prs_last_24h(forgejo_url: str, token: str, repo: str) -> list[dict]:
    """Fetch all PRs opened in the last 24 hours via the Forgejo API."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    prs_recent = []
    page = 1

    while True:
        url = f"{forgejo_url}/api/v1/repos/{repo}/pulls"
        params = {
            "state": "open",
            "type": "pulls",
            "page": page,
            "limit": 50,
        }
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 404:
            print(f"ERROR: Repository '{repo}' not found on {forgejo_url}", file=sys.stderr)
            sys.exit(1)
        if response.status_code == 401:
            print("ERROR: Invalid or missing Forgejo token.", file=sys.stderr)
            sys.exit(1)
        response.raise_for_status()

        prs = response.json()
        if not prs:
            break

        for pr in prs:
            created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            if created_at >= since:
                prs_recent.append(pr)
            else:
                # PRs are returned newest-first; stop once we pass the 24h window
                return prs_recent

        page += 1

    return prs_recent


def build_email(prs: list[dict], repo: str, forgejo_url: str) -> tuple[str, str]:
    """Return (plain_text, html) email bodies."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(prs)
    subject_count = f"{count} PR{'s' if count != 1 else ''}"

    # --- Plain text ---
    lines = [
        f"Daily PR Summary for {repo}",
        f"Generated: {now_str}",
        f"{subject_count} opened in the last 24 hours.",
        "",
    ]
    if prs:
        for pr in prs:
            lines.append(f"  #{pr['number']} {pr['title']}")
            lines.append(f"    URL: {pr['html_url']}")
            lines.append("")
    else:
        lines.append("No pull requests were opened in the last 24 hours.")

    plain = "\n".join(lines)

    # --- HTML ---
    if prs:
        rows = ""
        for pr in prs:
            rows += f"""
            <tr>
              <td style='padding:12px 16px;border-bottom:1px solid #eee;vertical-align:top;'>
                <a href='{pr["html_url"]}'
                   style='font-weight:bold;color:#0969da;text-decoration:none;'>
                  #{pr["number"]} {pr["title"]}
                </a>
              </td>
            </tr>"""
        table = f"<table style='width:100%;border-collapse:collapse;'>{rows}</table>"
    else:
        table = "<p style='color:#555;'>No pull requests were opened in the last 24 hours.</p>"

    html = f"""
    <html>
    <body style='font-family:sans-serif;max-width:700px;margin:0 auto;padding:24px;'>
      <h2 style='margin-bottom:4px;'>Daily PR Summary</h2>
      <p style='color:#555;margin-top:0;'>
        <strong>{repo}</strong> &mdash; {now_str}
      </p>
      <p><strong>{subject_count}</strong> opened in the last 24 hours.</p>
      {table}
      <p style='color:#aaa;font-size:11px;margin-top:24px;'>
        Generated from <a href='{forgejo_url}/{repo}/pulls'>{forgejo_url}/{repo}/pulls</a>
      </p>
    </body>
    </html>
    """

    return plain, html


def send_email(cfg: dict, subject: str, plain: str, html: str) -> None:
    """Build and send the summary email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["email_from"]
    msg["To"] = cfg["email_to"]
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    print(f"Connecting to SMTP server {cfg['smtp_host']}:{cfg['smtp_port']} ...")
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
        if cfg["smtp_tls"]:
            server.starttls()
        server.login(cfg["smtp_user"], cfg["smtp_password"])
        server.sendmail(cfg["email_from"], cfg["email_to"], msg.as_string())

    print(f"Email sent to {cfg['email_to']}")


def main() -> None:
    """Fetch PRs from the last 24 hours and send the summary email."""
    cfg = get_config()
    repo = cfg["repo"]

    print(f"Fetching PRs opened in the last 24 hours in {repo} ...")
    prs = fetch_prs_last_24h(cfg["forgejo_url"], cfg["forgejo_token"], repo)
    print(f"Found {len(prs)} PR(s) opened in the last 24 hours.")

    count = len(prs)
    plural = 's' if count != 1 else ''
    subject = f"[{repo}] PR Summary — {count} PR{plural}"

    plain, html = build_email(prs, repo, cfg["forgejo_url"])
    send_email(cfg, subject, plain, html)


if __name__ == "__main__":
    main()
