# forgejo-renovate-digest

Sends a daily summary email of all pull requests opened in the last 24 hours in a Forgejo repository. Intended for use with Renovate bot to keep track of dependency update PRs.

## Requirements

- Python 3.10+
- A Forgejo API token with read access to the target repository
- An SMTP server

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your values:

   | Variable        | Description                                             |
   |-----------------|---------------------------------------------------------|
   | `FORGEJO_URL`   | Your Forgejo instance URL                               |
   | `FORGEJO_TOKEN` | API token — see `<instance>/user/settings/applications` |
   | `FORGEJO_REPO`  | Repository in `owner/repo` format                       |
   | `SMTP_HOST`     | SMTP server hostname                                    |
   | `SMTP_PORT`     | SMTP port (default: `587`)                              |
   | `SMTP_USER`     | SMTP username                                           |
   | `SMTP_PASSWORD` | SMTP password                                           |
   | `SMTP_TLS`      | Use STARTTLS — `true` or `false` (default: `true`)      |
   | `EMAIL_FROM`    | Sender address                                          |
   | `EMAIL_TO`      | Recipient address                                       |

3. **Run**

   ```bash
   python main.py
   ```

   The script loads `.env` automatically.

## Example output

**Subject:** `[myorg/myrepo] PR Summary — 3 PRs`

```text
Daily PR Summary for myorg/myrepo
Generated: 2026-03-22 08:00 UTC
3 PRs opened in the last 24 hours.

  #42 Update ghcr.io/paperless-ngx/paperless-ngx to v2.20.13
    URL: https://forgejo.example.com/myorg/myrepo/pulls/42

  #43 Update docker.io/library/postgres to v16.4
    URL: https://forgejo.example.com/myorg/myrepo/pulls/43

  #44 Update docker.io/library/redis to v7.4.2
    URL: https://forgejo.example.com/myorg/myrepo/pulls/44
```
