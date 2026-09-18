# WBR Sales dashboard

`dashboard.html` is a self-contained sales dashboard built from the
"Invoices 21-22-23-24-25-26" tab of the Google Sheet in `.env`.

## Refresh the data

    python3 build.py

This downloads the sheet as Excel (`sheet.xlsx`), cleans it and rewrites
`dashboard.html`. Use `python3 build.py --offline` to rebuild from the last
download without fetching. Requires Python 3 with `openpyxl`.

Then republish `dashboard.html` (or just open it in a browser).

## Files

- `build.py` — download + cleaning rules (TEST rows dropped, canceled orders
  separated, day/month-swapped dates repaired, product types grouped).
- `template.html` — page layout, charts and styles; `build.py` injects the data
  at the `/*__DATA__*/` marker.
- `dashboard.html` — generated output. Do not edit by hand.
- `.env` — `SHEET_URL` / `SHEET_ID` of the source sheet.
