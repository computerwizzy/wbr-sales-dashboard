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
Config: .env (or environment) with SHEET_ID (or SHEET_URL), SHEET_GID, DASH_PASSWORD,
        optional LIVE_URL (Apps Script relay), VIEWERS_JSON ({"MIGUEL":{"password":"...","token":"..."}, ...}) which adds
        per-seller passwords to index.html that open only that seller's lines, and SELLERS_JSON (same shape) which
        instead produces separate sellers/<name>/index.html pages.
"""
import sys, os, re, json, base64, secrets, datetime as dt, urllib.request, csv, io

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
    for k in ("SHEET_URL", "SHEET_ID", "SHEET_GID", "DASH_PASSWORD", "LIVE_URL", "SELLERS_JSON", "VIEWERS_JSON"):
        if os.environ.get(k): env[k] = os.environ[k]
    return env

def sheet_id(env):
    if env.get("SHEET_ID"): return env["SHEET_ID"]
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", env.get("SHEET_URL", ""))
    if not m: sys.exit("No SHEET_ID or SHEET_URL found in .env (or the environment)")
    return m.group(1)

def download(sid, gid, live_url=None):
    url = live_url or f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    print("Downloading via relay" if live_url else f"Downloading sheet tab {gid}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    text = data.decode("utf-8-sig")
    if "DATE" not in text[:500] or "VENTA" not in text[:500]:
        sys.exit("The download does not look like the invoices tab (no DATE/VENTA header). Check LIVE_URL / the relay key, or whether the sheet is still shared." + (f" Got: {text[:80]!r}" if len(text) < 200 else ""))
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Saved sheet.csv ({len(data)/1024:.0f} KB, {text.count(chr(10))} lines)")

def logo_data_uri():
    if not os.path.exists(LOGO): sys.exit(f"Missing {LOGO}")
    return "data:image/png;base64," + base64.b64encode(open(LOGO, "rb").read()).decode()

def render_app(sid, gid, live_url=None, seller=None, csv_text=None, out_path=APP_OUT):
    tpl = open(TEMPLATE, encoding="utf-8").read()
    if csv_text is None: csv_text = open(CSV, encoding="utf-8").read()
    meta = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sheetId": sid, "gid": gid,
        "sheetUrl": f"https://docs.google.com/spreadsheets/d/{sid}/edit?gid={gid}",
        "liveUrl": live_url or "",
        "seller": seller or "",
        "tab": TAB,
    }
    payload = "const SNAPSHOT_CSV = " + json.dumps(csv_text, ensure_ascii=False) + ";\nconst META = " + json.dumps(meta, ensure_ascii=False) + ";"
    payload = payload.replace("</", "<\\/")
    if "/*__DATA__*/" not in tpl: sys.exit("template.html has no /*__DATA__*/ placeholder")
    body = tpl.replace("/*__DATA__*/", payload).replace("__LOGO__", logo_data_uri())
    html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="robots" content="noindex,nofollow">\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    if out_path:
        open(out_path, "w", encoding="utf-8").write(html)
        print(f"Wrote {os.path.basename(out_path)} ({len(html)/1024:.0f} KB) - unencrypted, keep it out of git")
    return html

def encrypt(html, password, salt=None):
    """AES-256-GCM with a PBKDF2 key. Payloads that share a salt can be tried with one derived key."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        sys.exit("The `cryptography` package is required: pip install cryptography")
    salt = salt or secrets.token_bytes(16); iv = secrets.token_bytes(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITER).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"salt": salt, "iv": b64(iv), "data": b64(ct)}

def bundle(payloads):
    """Several encrypted payloads sharing one salt -> the JSON the login page expects."""
    salt = payloads[0]["salt"]; assert all(p["salt"] == salt for p in payloads)
    return {"v": 2, "iter": PBKDF2_ITER, "salt": base64.b64encode(salt).decode(), "payloads": [{"iv": p["iv"], "data": p["data"]} for p in payloads]}

def render_login(enc, out=OUT, seller=None):
    shell = open(LOGIN, encoding="utf-8").read()
    if "__ENC_JSON__" not in shell: sys.exit("login.html has no __ENC_JSON__ placeholder")
    html = (shell.replace("__ENC_JSON__", json.dumps(enc)).replace("__LOGO__", logo_data_uri())
                 .replace("__SELLER__", f" · {seller.title()}" if seller else "")
                 .replace("__MANUAL__", "../../manual.html" if seller else "manual.html"))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").write(html)
    print(f"Wrote {os.path.relpath(out, HERE)} ({os.path.getsize(out)/1024:.0f} KB) - encrypted, safe to publish")

def seller_csv(csv_text, seller):
    """Keep the header plus the lines whose SELLER cell names this seller (shared MIGUEL/SERGIO lines count for both)."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    hdr = [h.strip().upper() for h in rows[0]]
    i = hdr.index("SELLER")
    keep = [rows[0]] + [r for r in rows[1:] if i < len(r) and seller in [p.strip().upper().replace("JAMIE", "JAIME") for p in r[i].split("/")]]
    buf = io.StringIO(); csv.writer(buf, lineterminator="\r\n").writerows(keep); return buf.getvalue()

def build_sellers(sid, gid, live_url, sellers):
    """One encrypted page per seller at sellers/<name>/index.html, each with its own password and only its own lines."""
    full_csv = open(CSV, encoding="utf-8").read()
    owner_key = None
    if live_url:
        m = re.search(r"[?&]key=([^&]+)", live_url); owner_key = m.group(1) if m else None
    for name, cfg in sellers.items():
        name = name.upper(); pw = cfg.get("password", ""); tok = cfg.get("token", "")
        if len(pw) < 10: print(f"skip {name}: password too short"); continue
        s_live = live_url.replace(owner_key, tok) if (live_url and owner_key and tok) else None
        html = render_app(sid, gid, s_live, seller=name, csv_text=seller_csv(full_csv, name), out_path=None)
        render_login(bundle([encrypt(html, pw)]), out=os.path.join(HERE, "sellers", name.lower(), "index.html"), seller=name)

if __name__ == "__main__":
    env = read_env(); sid = sheet_id(env); gid = env.get("SHEET_GID")
    if not gid: sys.exit("SHEET_GID missing from .env (the gid of the invoices tab, from the sheet URL)")
    password = env.get("DASH_PASSWORD", "")
    if len(password) < 12: sys.exit("DASH_PASSWORD missing or shorter than 12 characters (set it in .env)")
    live_url = env.get("LIVE_URL") or None
    if "--offline" not in sys.argv or not os.path.exists(CSV): download(sid, gid, live_url)
    html = render_app(sid, gid, live_url)
    salt = secrets.token_bytes(16)
    payloads = [encrypt(html, password, salt)]                      # the owner's password opens everything
    viewers = env.get("VIEWERS_JSON")                               # seller passwords open the same page, scoped to their lines
    if viewers:
        try: viewers = json.loads(viewers)
        except json.JSONDecodeError: sys.exit("VIEWERS_JSON is not valid JSON")
        full_csv = open(CSV, encoding="utf-8").read()
        owner_key = None
        if live_url:
            m = re.search(r"[?&]key=([^&]+)", live_url); owner_key = m.group(1) if m else None
        for name, cfg in viewers.items():
            name = name.upper(); pw = cfg.get("password", ""); tok = cfg.get("token", "")
            if len(pw) < 10: sys.exit(f"VIEWERS_JSON: password for {name} is too short")
            if pw == password: sys.exit(f"VIEWERS_JSON: {name} must not use the owner's password")
            s_live = live_url.replace(owner_key, tok) if (live_url and owner_key and tok) else None
            s_html = render_app(sid, gid, s_live, seller=name, csv_text=seller_csv(full_csv, name), out_path=None)
            payloads.append(encrypt(s_html, pw, salt))
            print(f"  viewer {name}: {len(s_html)/1024:.0f} KB payload, own lines only")
    render_login(bundle(payloads))
    sellers = env.get("SELLERS_JSON")
    if sellers:
        try: sellers = json.loads(sellers)
        except json.JSONDecodeError: sys.exit("SELLERS_JSON is not valid JSON")
        build_sellers(sid, gid, live_url, sellers)
