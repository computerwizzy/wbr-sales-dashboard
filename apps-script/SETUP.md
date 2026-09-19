# Making the Google Sheet private (relay setup)

Today the dashboard reads the sheet because the sheet is shared as "anyone with
the link can view". This relay lets you switch the sheet to **Restricted** while
the dashboard keeps reading it live.

## 1. Add the script to the sheet (5 minutes, once)

1. Open the Google Sheet. Menu **Extensions → Apps Script**.
2. Delete whatever is in `Code.gs` and paste the contents of `apps-script/Code.gs`
   from this repo, then replace PASTE_YOUR_PROXY_KEY_HERE with the PROXY_KEY value from `.env`.
3. Click **Deploy → New deployment**. Click the gear next to "Select type" and
   choose **Web app**.
   - Description: `WBR dashboard relay`
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Click **Deploy**, then **Authorize access** and approve with your Google
   account (Google may warn that the app isn't verified: choose Advanced → Go to
   project). 
5. Copy the **Web app URL**. It looks like
   `https://script.google.com/macros/s/AKfycb.../exec`.

## 2. Tell the dashboard to use it

In `.env` add one line (the key is already in `.env` as `PROXY_KEY`):

    LIVE_URL=https://script.google.com/macros/s/AKfycb.../exec?key=<PROXY_KEY>

Then rebuild and publish:

    python3 build.py
    git add index.html && git commit -m "Use the sheet relay" && git push

and store the same value as a GitHub Actions secret so the nightly refresh works:

    gh secret set LIVE_URL --repo computerwizzy/wbr-sales-dashboard --body "<the LIVE_URL value>"

## 3. Lock the sheet

Share → General access → **Restricted**. Add the two people who should edit it.
The dashboard still works because the relay runs as you.

## Changing the key later

Edit `KEY` in the script, **Deploy → Manage deployments → edit → New version**,
update `LIVE_URL` in `.env` and in the GitHub secret, rebuild, push.
