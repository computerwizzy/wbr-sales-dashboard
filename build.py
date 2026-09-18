#!/usr/bin/env python3
"""Rebuild index.html from the Google Sheet listed in .env.

The page reads the sheet live in the browser; this script only refreshes the
embedded fallback snapshot (used when the live read fails) and the page shell.

Usage:  python3 build.py            # download the sheet tab as CSV, render index.html
        python3 build.py --offline  # reuse the last downloaded sheet.csv

Needs: python3 only (standard library).
"""
import sys, os, re, json, datetime as dt, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "sheet.csv")
TEMPLATE = os.path.join(HERE, "template.html")
OUT = os.path.join(HERE, "index.html")
TAB = "Invoices 21-22-23-24-25-26"
DEFAULT_GID = "874835443"   # gid of the invoices tab

def read_env():
    env = {}
    path = os.path.join(HERE, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("SHEET_URL", "SHEET_ID", "SHEET_GID"):
        if os.environ.get(k): env[k] = os.environ[k]
    return env

def sheet_id(env):
    if env.get("SHEET_ID"): return env["SHEET_ID"]
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", env.get("SHEET_URL", ""))
    if not m: sys.exit("No SHEET_ID or SHEET_URL found in .env (or the environment)")
    return m.group(1)

def download(sid, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    print("Downloading", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    text = data.decode("utf-8-sig")
    if "DATE" not in text[:500] or "VENTA" not in text[:500]:
        sys.exit("The download does not look like the invoices tab (no DATE/VENTA header). Is the sheet still shared with anyone who has the link?")
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Saved {CSV} ({len(data)/1024:.0f} KB, {text.count(chr(10))} lines)")

def render(sid, gid):
    if not os.path.exists(TEMPLATE): sys.exit(f"Missing {TEMPLATE}")
    tpl = open(TEMPLATE, encoding="utf-8").read()
    csv_text = open(CSV, encoding="utf-8").read()
    meta = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sheetId": sid, "gid": gid,
        "sheetUrl": f"https://docs.google.com/spreadsheets/d/{sid}/edit?gid={gid}",
        "tab": TAB,
    }
    payload = "const SNAPSHOT_CSV = " + json.dumps(csv_text, ensure_ascii=False) + ";\nconst META = " + json.dumps(meta, ensure_ascii=False) + ";"
    payload = payload.replace("</", "<\\/")
    if "/*__DATA__*/" not in tpl: sys.exit("template.html has no /*__DATA__*/ placeholder")
    open(OUT, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", payload))
    print(f"Wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")

if __name__ == "__main__":
    env = read_env(); sid = sheet_id(env); gid = env.get("SHEET_GID") or DEFAULT_GID
    if "--offline" not in sys.argv or not os.path.exists(CSV): download(sid, gid)
    render(sid, gid)
