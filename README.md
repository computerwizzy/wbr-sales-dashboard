# WBR Sales dashboard

`index.html` is a self-contained sales dashboard for the
"Invoices 21-22-23-24-25-26" tab of the Google Sheet in `.env`.

**It is live:** every time the page opens (and every 10 minutes while open) it
downloads the sheet's CSV export straight from Google and recomputes everything
in the browser. New rows in the sheet appear on the next read. The sheet must
stay shared as "anyone with the link can view" for this to work.

If the live read fails, the page falls back to a snapshot embedded at build time.

## Refresh the fallback snapshot

    python3 build.py

This downloads the tab as CSV (`sheet.csv`) and rewrites `index.html`. Use
`python3 build.py --offline` to rebuild from the last download. Python 3 only,
no packages needed. A GitHub Actions workflow (`.github/workflows/refresh.yml`)
does this nightly so the fallback never gets stale.

## Files

- `template.html` — page layout, charts, styles, and the cleaning rules in
  JavaScript (TEST rows dropped, canceled orders separated, day/month-swapped
  dates repaired, product types grouped). Edit this file, then rebuild.
- `build.py` — downloads the CSV and injects it at the `/*__DATA__*/` marker.
- `index.html` — generated output. Do not edit by hand.
- `.env` — `SHEET_URL` / `SHEET_ID` / `SHEET_GID` of the source sheet (not committed).
