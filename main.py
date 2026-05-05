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
    """Fetch all PRs opened or updated in the last 24 hours via the Forgejo API."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    prs_recent = []
    page = 1

    while True:
        url = f"{forgejo_url}/api/v1/repos/{repo}/pulls"
        params = {
            "state": "open",
            "type": "pulls",
            "sort": "recentupdate",
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
            updated_at = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
            if updated_at >= since:
                prs_recent.append(pr)
            else:
                # PRs are returned by most-recently-updated; stop once we pass the 24h window
                return prs_recent

        page += 1

    return prs_recent


def build_email(prs: list[dict], repo: str, forgejo_url: str) -> tuple[str, str]:
    """Return (plain_text, html) email bodies."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    now_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    all_prs_url = f"{forgejo_url}/{repo}/pulls"

    new_prs = [pr for pr in prs if datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")) >= since]
    updated_prs = [pr for pr in prs if datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")) < since]

    parts = []
    if new_prs:
        n = len(new_prs)
        parts.append(f"{n} new PR{'s' if n != 1 else ''}")
    if updated_prs:
        n = len(updated_prs)
        parts.append(f"{n} updated PR{'s' if n != 1 else ''}")
    summary_str = ", ".join(parts) if parts else "no activity"

    # --- Plain text ---
    lines = [
        f"Daily PR Summary for {repo}",
        f"All PRs: {all_prs_url}",
        f"Generated: {now_str}",
        summary_str,
        "",
    ]
    if new_prs:
        lines.append("New PRs:")
        for pr in new_prs:
            lines.append(f"  #{pr['number']} {pr['title']}")
            lines.append(f"    {pr['html_url']}")
            lines.append("")
    if updated_prs:
        lines.append("Updated PRs:")
        for pr in updated_prs:
            lines.append(f"  #{pr['number']} {pr['title']}")
            lines.append(f"    {pr['html_url']}")
            lines.append("")
    if not prs:
        lines.append("No pull requests were opened or updated in the last 24 hours.")

    plain = "\n".join(lines)

    # --- HTML ---
    def make_rows(pr_list: list[dict]) -> str:
        rows = ""
        for pr in pr_list:
            rows += f"""
            <tr>
              <td style='padding:12px 16px;border-bottom:1px solid #eee;vertical-align:top;'>
                <a href='{pr["html_url"]}'
                   style='font-weight:bold;color:#0969da;text-decoration:none;'>
                  #{pr["number"]} {pr["title"]}
                </a>
              </td>
            </tr>"""
        return rows

    new_section = ""
    if new_prs:
        new_section = f"""
      <h3 style='margin-bottom:4px;'>New</h3>
      <table style='width:100%;border-collapse:collapse;'>{make_rows(new_prs)}</table>"""

    updated_section = ""
    if updated_prs:
        updated_section = f"""
      <h3 style='margin-bottom:4px;'>Updated</h3>
      <table style='width:100%;border-collapse:collapse;'>{make_rows(updated_prs)}</table>"""

    content = new_section + updated_section
    if not prs:
        content = "<p style='color:#555;'>No pull requests were opened or updated in the last 24 hours.</p>"

    html = f"""
    <html>
    <body style='font-family:sans-serif;max-width:700px;margin:0 auto;padding:24px;'>
      <h2 style='margin-bottom:4px;'>Daily PR Summary</h2>
      <p style='margin-top:0;'>
        <a href='{all_prs_url}'>{all_prs_url}</a>
      </p>
      <p style='color:#555;'><strong>{repo}</strong> - {now_str}</p>
      <p>{summary_str}</p>
      {content}
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

    print(f"Fetching PRs opened or updated in the last 24 hours in {repo} ...")
    prs = fetch_prs_last_24h(cfg["forgejo_url"], cfg["forgejo_token"], repo)
    print(f"Found {len(prs)} PR(s) opened or updated in the last 24 hours.")

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    new_count = sum(1 for pr in prs if datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")) >= since)
    upd_count = len(prs) - new_count
    parts = []
    if new_count:
        parts.append(f"{new_count} new PR{'s' if new_count != 1 else ''}")
    if upd_count:
        parts.append(f"{upd_count} updated PR{'s' if upd_count != 1 else ''}")
    subject = f"[{repo}] PR Summary - {', '.join(parts) if parts else 'no activity'}"

    plain, html = build_email(prs, repo, cfg["forgejo_url"])
    send_email(cfg, subject, plain, html)


if __name__ == "__main__":
    main()
