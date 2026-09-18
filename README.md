# WBR Sales dashboard

`index.html` is a self-contained sales dashboard for the
"Invoices 21-22-23-24-25-26" tab of the Google Sheet in `.env`.

**It is live:** every time the page opens (and every 10 minutes while open) it
downloads the sheet's CSV export straight from Google and recomputes everything
in the browser. New rows in the sheet appear on the next read. The sheet must
stay shared as "anyone with the link can view" for this to work.

If the live read fails, the page falls back to a snapshot embedded at build time.

**It is password-protected:** `index.html` is only a login shell plus an
AES-256-GCM encrypted copy of the dashboard (key derived from the password with
PBKDF2, 600k iterations). Without the password the sales data and the sheet link
are unreadable. The password lives in `.env` as `DASH_PASSWORD` (never
committed) and in the repo's Actions secrets. To change it, update both and
rebuild; anyone who ticked "Remember this device" is signed out automatically.

## Refresh the fallback snapshot

    python3 build.py

This downloads the tab as CSV (`sheet.csv`), renders the dashboard to
`app.html` (unencrypted, git-ignored) and encrypts it into `index.html`. Use
`python3 build.py --offline` to rebuild from the last download. Needs Python 3
and `pip install cryptography`. A GitHub Actions workflow (`.github/workflows/refresh.yml`)
does this nightly so the fallback never gets stale.

## Files

- `template.html` — page layout, charts, styles, and the cleaning rules in
  JavaScript (TEST rows dropped, canceled orders separated, day/month-swapped
  dates repaired, product types grouped). Edit this file, then rebuild.
- `login.html` — the password screen; `build.py` injects the encrypted payload.
- `build.py` — downloads the CSV, renders, encrypts.
- `assets/logo.png` — Wheels Below Retail logo, embedded into both pages.
- `index.html` — generated, encrypted output. Do not edit by hand.
- `.env` — `SHEET_ID`, `SHEET_GID`, `DASH_PASSWORD` (not committed; see `.env.example`).
