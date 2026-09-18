#!/usr/bin/env python3
"""Build the password-protected dashboard (index.html) from the Google Sheet in .env.

Pipeline
  1. download the invoices tab as CSV            -> sheet.csv        (fallback snapshot)
  2. render template.html + snapshot + logo       -> app.html         (the real dashboard, NOT committed)
  3. encrypt app.html with DASH_PASSWORD          -> index.html       (login shell + AES-256-GCM payload)

The page reads the sheet live in the browser after it is unlocked.

Usage:  python3 build.py            # download, render, encrypt
        python3 build.py --offline  # reuse the last downloaded sheet.csv

Needs: python3 and the `cryptography` package (pip install cryptography).
Config: .env (or environment) with SHEET_ID (or SHEET_URL), SHEET_GID, DASH_PASSWORD.
"""
import sys, os, re, json, base64, secrets, datetime as dt, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "sheet.csv")
LOGO = os.path.join(HERE, "assets", "logo.png")
TEMPLATE = os.path.join(HERE, "template.html")
LOGIN = os.path.join(HERE, "login.html")
APP_OUT = os.path.join(HERE, "app.html")
OUT = os.path.join(HERE, "index.html")
TAB = "Invoices 21-22-23-24-25-26"
PBKDF2_ITER = 600_000

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
    for k in ("SHEET_URL", "SHEET_ID", "SHEET_GID", "DASH_PASSWORD"):
        if os.environ.get(k): env[k] = os.environ[k]
    return env

def sheet_id(env):
    if env.get("SHEET_ID"): return env["SHEET_ID"]
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", env.get("SHEET_URL", ""))
    if not m: sys.exit("No SHEET_ID or SHEET_URL found in .env (or the environment)")
    return m.group(1)

def download(sid, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    print("Downloading sheet tab", gid)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    text = data.decode("utf-8-sig")
    if "DATE" not in text[:500] or "VENTA" not in text[:500]:
        sys.exit("The download does not look like the invoices tab (no DATE/VENTA header). Is the sheet still shared with anyone who has the link?")
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Saved sheet.csv ({len(data)/1024:.0f} KB, {text.count(chr(10))} lines)")

def logo_data_uri():
    if not os.path.exists(LOGO): sys.exit(f"Missing {LOGO}")
    return "data:image/png;base64," + base64.b64encode(open(LOGO, "rb").read()).decode()

def render_app(sid, gid):
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
    body = tpl.replace("/*__DATA__*/", payload).replace("__LOGO__", logo_data_uri())
    html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="robots" content="noindex,nofollow">\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    open(APP_OUT, "w", encoding="utf-8").write(html)
    print(f"Wrote app.html ({os.path.getsize(APP_OUT)/1024:.0f} KB) - unencrypted, keep it out of git")
    return html

def encrypt(html, password):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        sys.exit("The `cryptography` package is required: pip install cryptography")
    salt = secrets.token_bytes(16); iv = secrets.token_bytes(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITER).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": PBKDF2_ITER, "salt": b64(salt), "iv": b64(iv), "data": b64(ct)}

def render_login(enc):
    shell = open(LOGIN, encoding="utf-8").read()
    if "__ENC_JSON__" not in shell: sys.exit("login.html has no __ENC_JSON__ placeholder")
    html = shell.replace("__ENC_JSON__", json.dumps(enc)).replace("__LOGO__", logo_data_uri())
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"Wrote index.html ({os.path.getsize(OUT)/1024:.0f} KB) - encrypted, safe to publish")

if __name__ == "__main__":
    env = read_env(); sid = sheet_id(env); gid = env.get("SHEET_GID")
    if not gid: sys.exit("SHEET_GID missing from .env (the gid of the invoices tab, from the sheet URL)")
    password = env.get("DASH_PASSWORD", "")
    if len(password) < 12: sys.exit("DASH_PASSWORD missing or shorter than 12 characters (set it in .env)")
    if "--offline" not in sys.argv or not os.path.exists(CSV): download(sid, gid)
    html = render_app(sid, gid)
    render_login(encrypt(html, password))
