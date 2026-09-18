#!/usr/bin/env python3
"""Rebuild dashboard.html from the Google Sheet listed in .env.

Usage:  python3 build.py            # download sheet, clean, render dashboard.html
        python3 build.py --offline  # reuse the last downloaded sheet.xlsx

Needs: python3 with openpyxl (pip install openpyxl).
"""
import sys, os, re, json, datetime as dt, collections, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "sheet.xlsx")
TEMPLATE = os.path.join(HERE, "template.html")
OUT = os.path.join(HERE, "dashboard.html")
TAB = "Invoices 21-22-23-24-25-26"

MON = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12,
       'ENE':1,'ABR':4,'AGO':8,'SET':9,'DIC':12}

def read_env():
    env = {}
    with open(os.path.join(HERE, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def sheet_id(env):
    if env.get("SHEET_ID"): return env["SHEET_ID"]
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", env.get("SHEET_URL", ""))
    if not m: sys.exit("No SHEET_ID or SHEET_URL found in .env")
    return m.group(1)

def download(sid):
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx"
    print("Downloading", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(XLSX, "wb") as f:
        f.write(r.read())
    print("Saved", XLSX, os.path.getsize(XLSX), "bytes")

def num(v):
    if isinstance(v, bool): return 0.0
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        s = v.replace("$", "").replace(",", "").strip()
        try: return float(s)
        except ValueError: return 0.0
    return 0.0

def text(v):
    return "" if v is None else str(v).strip()

def type_group(t):
    t = t.upper()
    if t.startswith("NEW WHEEL"): return "Wheels"
    if t.startswith("NEW TIRE"): return "New tires"
    if t.startswith("USED TIRE"): return "Used tires"
    if t.startswith("PACKAGE"): return "Packages"
    if t.startswith("ACCESSOR"): return "Accessories"
    if t.startswith("LABOR") or t.startswith("CUSTOM PAINT"): return "Labor"
    return "Other"

def channel_name(c):
    c = c.upper()
    if "SHOPIFY" in c: return "Shopify"
    if "EBAY" in c: return "eBay"
    if "AMAZON" in c: return "Amazon"
    return c.title() if c else "Unknown"

def status_class(s):
    s = s.upper()
    if s.startswith("CANCEL"): return "canceled"
    if s.startswith("TEST"): return "test"
    if s.startswith("FRAUD") or s.startswith("CHARGEBACK") or s.startswith("LOST"): return "loss"
    if s.startswith("RMA"): return "rma"
    if s.startswith("RETURN") or s.startswith("REFUND") or s.startswith("PARTIALLY REFUNDED") or "RETURN" in s: return "return"
    return "ok"

def seller_name(s):
    s = s.upper().replace(" ", "")
    if not s or s.startswith("GASTADO"): return ""
    s = s.replace("JAMIE", "JAIME")
    parts = sorted(p.title() for p in s.split("/") if p)
    return "/".join(parts)

def resolve_day(date_val, month_num, year):
    """Day of month from the DATE cell; MONTH/YEAR columns are authoritative."""
    if isinstance(date_val, dt.datetime):
        if date_val.month == month_num: return date_val.day, "ok"
        if date_val.day == month_num: return date_val.month, "swapped"
        return min(date_val.day, 28), "mismatch"
    s = text(date_val)
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a == month_num and 1 <= b <= 31: return b, "ok"
        if b == month_num and 1 <= a <= 31: return a, "swapped"
        return min(b, 28) if 1 <= b <= 31 else 1, "mismatch"
    return 1, "missing"

def clean():
    import openpyxl, warnings
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb[TAB]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [text(h) for h in rows[0]]
    diag = collections.Counter()
    out = []
    for r in rows[1:]:
        d = dict(zip(hdr, r))
        if not any(c not in (None, "") for c in r): continue
        year = d.get("YEAR")
        if not isinstance(year, (int, float)): diag["skip: no YEAR (summary rows)"] += 1; continue
        year = int(year)
        mon = MON.get(text(d.get("MONTH")).upper()[:3])
        inv = text(d.get("INVOICE"))
        if not mon:
            if num(d.get("VENTA")) != 0: diag["skip: no MONTH but has VENTA"] += 1
            else: diag["skip: no MONTH (empty pre-filled rows)"] += 1
            continue
        day, how = resolve_day(d.get("DATE"), mon, year)
        diag["date " + how] += 1
        try: date = dt.date(year, mon, day)
        except ValueError: date = dt.date(year, mon, 1); diag["date clamped"] += 1
        ch = text(d.get("CANAL DE VENTA")); st = text(d.get("STATUS")); ty = text(d.get("TYPE")); fu = text(d.get("FULFILLMENT"))
        if "TEST" in (ch.upper(), st.upper(), ty.upper(), fu.upper()):
            diag["skip: TEST rows"] += 1; continue
        sc = status_class(st)
        if sc == "ok" and (ty.upper() == "CANCELED" or fu.upper() == "CANCELED"): sc = "canceled"
        prod = text(d.get("PRODUCT")).replace("\n", " ")
        prod = re.sub(r"\s+", " ", prod)
        out.append([
            date.isoformat(), inv, channel_name(ch), fu.title() if fu else "—", st.upper() or "—", sc,
            type_group(ty), ty.upper() or "—", prod[:110],
            round(num(d.get("QTY")), 2), round(num(d.get("VENTA")), 2), round(num(d.get("COSTO")), 2),
            round(num(d.get("SHIPPING")), 2), round(num(d.get("FEE")), 2), round(num(d.get("PROFIT")), 2),
            seller_name(text(d.get("SELLER"))), round(num(d.get("RETURN COST")), 2),
            text(d.get("PAYMENT TYPE")).upper(),
        ])
    out.sort(key=lambda r: (r[0], r[1]))
    return out, diag

def render(rows, diag, sid):
    if not os.path.exists(TEMPLATE): sys.exit(f"Missing {TEMPLATE}")
    tpl = open(TEMPLATE, encoding="utf-8").read()
    meta = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sheetUrl": f"https://docs.google.com/spreadsheets/d/{sid}/edit",
        "tab": TAB,
        "rows": len(rows),
        "excluded": {k: v for k, v in diag.items() if k.startswith("skip")},
        "dates": {k: v for k, v in diag.items() if k.startswith("date")},
        "cols": ["date","invoice","channel","fulfillment","status","statusClass","typeGroup","type","product",
                 "qty","sales","cost","shipping","fee","profit","seller","returnCost","payment"],
    }
    payload = "const RAW = " + json.dumps(rows, separators=(",", ":"), ensure_ascii=False) + ";\nconst META = " + json.dumps(meta, ensure_ascii=False) + ";"
    payload = payload.replace("</", "<\\/")
    if "/*__DATA__*/" not in tpl: sys.exit("template.html has no /*__DATA__*/ placeholder")
    html = tpl.replace("/*__DATA__*/", payload)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"Wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB, {len(rows)} rows)")

if __name__ == "__main__":
    env = read_env(); sid = sheet_id(env)
    if "--offline" not in sys.argv or not os.path.exists(XLSX): download(sid)
    rows, diag = clean()
    print("Diagnostics:")
    for k, v in sorted(diag.items()): print(f"  {k}: {v}")
    print(f"Clean rows: {len(rows)}  first={rows[0][0]} last={rows[-1][0]}")
    tot = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in rows:
        if r[5] != "canceled": t = tot[r[0][:4]]; t[0] += r[10]; t[1] += r[14]; t[2] += 1
    for y in sorted(tot): print(f"  {y}: sales={tot[y][0]:,.0f} profit={tot[y][1]:,.0f} lines={tot[y][2]}")
    if os.path.exists(TEMPLATE): render(rows, diag, sid)
    else: print("template.html not found yet; skipped render")
