#!/usr/bin/env python3
"""Space-A collector.

Visits every AMC passenger-terminal page listed in terminals.json, finds the
current 72-hour schedule and roll-call report PDFs, extracts their text
(pdftotext, with Tesseract OCR for image-only slides), parses departures and
past roll calls, merges them with the running history, and writes an
encrypted bundle (site/data.json) that only the planner's users can open.

Env vars:
  SPACEA_USERS       "user:password" pairs, one per line (or comma separated)
  SPACEA_MASTER_KEY  long random string; lets the collector re-open the last
                     bundle to keep roll-call history between runs
  SPACEA_PLAIN=1     also write data/payload.json unencrypted (local testing)
"""
import base64, gzip, hashlib, json, os, re, subprocess, sys, tempfile, time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse import parse_72hr, parse_rollcall, parse_30day, last_updated  # noqa: E402
from locations import resolve, place, gazetteer, US_STATES, COUNTRIES, COUNTRY_ALIASES  # noqa: E402

ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
HISTORY_DAYS = 120
KDF_ITER = 310000

SKIP_FILE = re.compile(r"GRAM|PET|ADVICE|FORM|LETTER|ORDER|TOTE|PARKING|MILCONNECT|HEAD TAX|BROCHURE|PAMPHLET|"
                       r"EBOLA|EML|VISITOR|POLICY|4515|MEMO|BAGGAGE|ARRIVAL INFO|SMOOTH MOVE|STAMP|FAQ|DOCUMENT|EARLY BIRD|RAD\b", re.I)


def classify(fname):
    f = fname.upper()
    if SKIP_FILE.search(f):
        return None
    if re.search(r"ROLL|\b7 ?D(AY)?S?\b|7DAY|UTILIZATION|24[- ]?H(OU)?R", f):
        return "rc"
    if re.search(r"30 ?DAY|MONTHLY|\bPE\b|_PE_|ROTATOR|PATRIOT", f):
        return "30"
    if re.search(r"72|FORECAST|PIMS|FLIGHT SCHEDULE|SPACE-A FLIGHT", f):
        return "72"
    if re.search(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\b.*\b20\d\d\b", f):
        return "30"   # e.g. "KUWAIT NOVEMBER 2026" monthly rotator
    return None


def get(url, **kw):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
            print("   HTTP", r.status_code, url, file=sys.stderr)
            if r.status_code in (403, 404):
                return None
        except requests.RequestException as e:
            print("   error", e, url, file=sys.stderr)
        time.sleep(2 + attempt * 3)
    return None


def find_docs(page_url):
    r = get(page_url)
    if not r:
        return [], "page unreachable"
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup
    docs, seen = [], set()
    for a in main.find_all("a", href=True):
        href = a["href"].strip()
        if not re.search(r"\.pdf", href, re.I):
            continue
        if href.startswith("//Portals"):
            href = href[1:]
        url = urljoin("https://www.amc.af.mil/", href).replace("amc.usaf.afpims.mil", "www.amc.af.mil")
        fname = unquote(url.split("?")[0].rsplit("/", 1)[-1])
        kind = classify(fname)
        if kind and url not in seen:
            seen.add(url)
            docs.append({"kind": kind, "url": url, "file": fname})
    return docs, None


def pdf_text(content):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "f.pdf")
        open(p, "wb").write(content)
        txt = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout
        pages = max(1, txt.count("\f"))
        letters = len(re.findall(r"[A-Za-z]", txt))
        if letters / pages >= 60:
            return txt, "text"
        # image-only slides -> OCR each page
        subprocess.run(["pdftoppm", "-r", "200", "-png", p, os.path.join(td, "pg")], capture_output=True)
        out = []
        for img in sorted(f for f in os.listdir(td) if f.startswith("pg")):
            o = subprocess.run(["tesseract", os.path.join(td, img), "-", "--psm", "6",
                                "-c", "preserve_interword_spaces=1"], capture_output=True, text=True).stdout
            out.append(o)
        return "\n\f".join(out), "ocr"


def stop_list(raw_stops):
    res = []
    for s in raw_stops:
        p = resolve(s)
        if p:
            res.append({"key": p["key"], "raw": s, "name": p["name"], "region": p["region"], "country": p["country"],
                        "known": p["known"]})
    return res


# ------------------------------------------------------------------ crypto
def _kdf(secret, salt):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITER).derive(secret.encode())


def slot_id(name):
    return hashlib.sha256(("spacea-slot:" + name.strip().lower()).encode()).hexdigest()[:16]


def b64(b):
    return base64.b64encode(b).decode()


def encrypt_bundle(payload, users, master):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = gzip.compress(json.dumps(payload, separators=(",", ":")).encode())
    # stable data key (derived from the master key) so "keep me signed in" survives refreshes
    dk = hashlib.sha256(("spacea-data-key:" + master).encode()).digest() if master else os.urandom(32)
    iv = os.urandom(12)
    ct = AESGCM(dk).encrypt(iv, raw, None)
    slots = []
    creds = list(users.items()) + ([("__master__", master)] if master else [])
    for u, pw in creds:
        salt, wiv = os.urandom(16), os.urandom(12)
        kek = _kdf(u.strip().lower() + "\n" + pw, salt)
        slots.append({"id": slot_id(u), "salt": b64(salt), "iv": b64(wiv), "wk": b64(AESGCM(kek).encrypt(wiv, dk, None))})
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": KDF_ITER, "slots": slots, "iv": b64(iv), "ct": b64(ct)}


def decrypt_bundle(bundle, user, pw):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    sid = slot_id(user)
    for s in bundle["slots"]:
        if s["id"] != sid:
            continue
        kek = _kdf(user.strip().lower() + "\n" + pw, base64.b64decode(s["salt"]))
        dk = AESGCM(kek).decrypt(base64.b64decode(s["iv"]), base64.b64decode(s["wk"]), None)
        raw = AESGCM(dk).decrypt(base64.b64decode(bundle["iv"]), base64.b64decode(bundle["ct"]), None)
        return json.loads(gzip.decompress(raw))
    raise ValueError("no slot")


def parse_users(s):
    users = {}
    for part in re.split(r"[\n,]+", s or ""):
        if ":" in part:
            u, pw = part.split(":", 1)
            if u.strip() and pw:
                users[u.strip()] = pw.strip()
    return users


# ------------------------------------------------------------------ main
def load_previous(master):
    p = os.path.join(SITE, "data.json")
    plain = os.path.join(DATA, "payload.json")
    if master and os.path.exists(p):
        try:
            return decrypt_bundle(json.load(open(p)), "__master__", master)
        except Exception as e:
            print("could not open previous bundle:", e, file=sys.stderr)
    if os.path.exists(plain):
        return json.load(open(plain))
    return {}


def main():
    today = datetime.now(timezone.utc).date()
    terminals = json.load(open(os.path.join(HERE, "terminals.json")))
    master = os.environ.get("SPACEA_MASTER_KEY", "")
    users = parse_users(os.environ.get("SPACEA_USERS", ""))
    if os.environ.get("CI") and not users:
        sys.exit("SPACEA_USERS secret is empty - add it under Settings > Secrets and variables > Actions")
    prev = load_previous(master)

    flights, rollcalls, planned, status = [], [], [], []
    for t in terminals:
        if not t.get("scrape"):
            continue
        st = {"key": t["key"], "name": t["name"], "docs": [], "error": None, "flights": 0, "rollcalls": 0}
        print("==", t["name"])
        docs, err = find_docs(t["page"])
        st["error"] = err
        for d in docs:
            r = get(d["url"])
            if not r:
                st["docs"].append({**d, "error": "download failed"})
                continue
            try:
                text, method = pdf_text(r.content)
            except Exception as e:
                st["docs"].append({**d, "error": "extract failed: %s" % e})
                continue
            info = {**d, "method": method, "updated": last_updated(text, today)}
            if d["kind"] == "30":
                rows = parse_30day(text, today)
                for f in rows:
                    f.update({"origin": t["key"], "kind": "30day", "roll_call": None, "seats": None,
                              "seat_status": None, "source": d["url"], "stops": stop_list(f["stops"])})
                    f["id"] = hashlib.md5(("30|%s|%s|%s" % (t["key"], f["date"], ",".join(s["key"] for s in f["stops"]))).encode()).hexdigest()[:10]
                planned += [f for f in rows if f["stops"] and not f["cancelled"]]
                info["count"] = len(rows)
                st["planned"] = st.get("planned", 0) + len(rows)
            elif d["kind"] == "72":
                rows = parse_72hr(text, today)
                for f in rows:
                    f["origin"] = t["key"]
                    f["kind"] = "72hr"
                    f["stops"] = stop_list(f["stops"])
                    f["source"] = d["url"]
                    f["id"] = hashlib.md5(("%s|%s|%s|%s" % (t["key"], f["date"], f["roll_call"],
                                           ",".join(s["key"] for s in f["stops"]))).encode()).hexdigest()[:10]
                flights += [f for f in rows if f["stops"]]
                info["count"] = len(rows)
                st["flights"] += len(rows)
                if rows:
                    st["latest_date"] = max(f["date"] for f in rows)
            else:
                rows = parse_rollcall(text, today)
                for rc in rows:
                    rc["origin"] = t["key"]
                    rc["stops"] = stop_list(rc["stops"])
                rollcalls += [rc for rc in rows if rc["stops"] and rc["date"]]
                info["count"] = len(rows)
                st["rollcalls"] += len(rows)
            st["docs"].append(info)
            print("   %-3s %-5s %3d  %s" % (d["kind"], method, info["count"], d["file"]))
        status.append(st)

    # merge roll-call history (and keep a record of scheduled flights we saw)
    hist = {}
    for rc in prev.get("rollcalls", []) + rollcalls:
        k = (rc["origin"], rc["date"], ",".join(s["key"] for s in rc["stops"]), rc.get("released"))
        hist[k] = rc
    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    rc_all = sorted((r for r in hist.values() if r["date"] >= cutoff), key=lambda r: r["date"], reverse=True)

    seen = {}
    for f in prev.get("seen_flights", []) + [
            {"origin": f["origin"], "date": f["date"], "dests": [s["key"] for s in f["stops"]]} for f in flights]:
        seen[(f["origin"], f["date"], ",".join(f["dests"]))] = f
    seen_all = [v for v in seen.values() if v["date"] >= cutoff]

    # 30-day entries that also appear on a 72-hour list are dropped (the 72-hour one has seats/roll call)
    have72 = {(f["origin"], f["date"], s["key"]) for f in flights for s in f["stops"]}
    planned = [p for p in planned if (p["origin"], p["date"], p["stops"][0]["key"]) not in have72]
    upcoming = [f for f in flights + planned if f["date"] >= (today - timedelta(days=1)).isoformat()]
    upcoming.sort(key=lambda f: (f["date"], f["roll_call"] or "99:99"))

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "flights": upcoming,
        "rollcalls": rc_all,
        "seen_flights": seen_all,
        "status": status,
        "terminals": terminals,
        "places": gazetteer(),
        "regions": {"states": US_STATES, "countries": COUNTRIES, "aliases": COUNTRY_ALIASES},
    }
    os.makedirs(SITE, exist_ok=True)
    if os.environ.get("SPACEA_PLAIN") == "1" or not users:
        os.makedirs(DATA, exist_ok=True)
        json.dump(payload, open(os.path.join(DATA, "payload.json"), "w"), indent=1)
        print("wrote data/payload.json (plain, local only)")
    if users:
        bundle = encrypt_bundle(payload, users, master)
        json.dump(bundle, open(os.path.join(SITE, "data.json"), "w"))
        print("wrote site/data.json for %d user(s)" % len(users))
    else:
        print("SPACEA_USERS not set: no encrypted bundle written", file=sys.stderr)
    print("flights: %d  roll calls kept: %d" % (len(upcoming), len(rc_all)))


if __name__ == "__main__":
    main()
