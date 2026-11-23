"""Parsers for AMC 72-hour schedules and Space-A roll-call reports.

Both work on the text produced by `pdftotext -layout` (or OCR text laid out
the same way). Every terminal formats its slides differently, so the parsers
are deliberately tolerant: they look for date headers, roll-call times, a
seats token (e.g. 20T, 0F, TBD, T-19) and destination text, and they attach
destination lines that sit above/below a time row (multi-stop missions).
"""
import re
from datetime import date, datetime

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
MON_RE = r"(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUNE?|JULY?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)"
DAYS_RE = r"(MON|TUES?|WED(?:NES)?|THU(?:RS)?|FRI|SAT(?:UR)?|SUN)(?:DAY)?"

DATE_DMY = re.compile(r"\b(\d{1,2})\s*[- ]?\s*" + MON_RE + r"\b\.?,?\s*(\d{4}|\d{2}(?!\d))?", re.I)
DATE_MDY = re.compile(r"\b" + MON_RE + r"\.?\s+(\d{1,2})(?:ST|ND|RD|TH)?\b,?\s*(\d{4})?", re.I)

TIME_START = re.compile(r"^\s*\*?\s*(\d{1,2}:\d{2}|\d{4})\s*(?:L|Z|HRS|LOCAL)?\b(?!\s*(?:/|-\s*\d))", re.I)
SEATS_END = re.compile(
    r"(?:^|\s)(TBD|T\s?-\s?\d{1,3}|F\s?-\s?\d{1,3}|\d{1,3}\s?[TF]\b|\d{1,3}\s?(?:SEATS)?)\s*\**\s*$", re.I)

NOISE = re.compile(
    r"ALL FLIGHTS|SUBJECT TO|SEATS?\s*[:=]|SEAT RELEASE|TENTATIVE|ROLL\s*CALL|^\s*CALL\s*$|DESTINATION|"
    r"IMMIGRATION|PASSENGER|TRAVELERS?\b|ORDERS|CHECK[- ]?IN|NOTE\b|NOTICE|UPDATED|LAST UPDATED|"
    r"NO (?:SCHEDULED|DEPARTURES|FLIGHTS|OUTBOUND|REMAINING|ROLL|SPACE)|ARRIVING|PICK-UP|REMARKS|"
    r"ALL TIMES|ADVERTISE|SIGN[- ]?UP|PLEASE|CONTACT|EMAIL|WWW\.|HTTP|EFFECTIVE|INFORMATION|"
    r"PROHIBITED|PATRIOT EXPRESS|DEPARTURES|ARRIVALS|\bBEGINS\b|DUTY|MUST|REQUIRE|PRE-BOOKED|"
    r"^\s*[-*•=_\s]+\s*$|^\s*ROLL\s*$|^\s*SPACE\s*A\s*$|FUEL STOP|SPACE A TRAVEL ONLY|TIME IS FOR|LOCAL TIME|EST\b|CST\b|UTC|ZULU",
    re.I)


def _year_for(mon, day, ref):
    best = None
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            d = date(y, mon, day)
        except ValueError:
            continue
        if best is None or abs((d - ref).days) < abs((best - ref).days):
            best = d
    return best


def find_date(text, ref):
    """Find a calendar date in a string. Returns a date or None."""
    t = text.upper()
    for rx, order in ((DATE_DMY, "dmy"), (DATE_MDY, "mdy")):
        m = rx.search(t)
        if not m:
            continue
        if order == "dmy":
            day, mon, yr = m.group(1), m.group(2), m.group(3)
        else:
            mon, day, yr = m.group(1), m.group(2), m.group(3)
        mon_n = MONTHS.get(mon[:3].upper())
        try:
            day_n = int(day)
        except ValueError:
            continue
        if not mon_n or not 1 <= day_n <= 31:
            continue
        if yr:
            y = int(yr)
            if y < 100:
                y += 2000
            if not 2000 <= y <= 2100:
                continue
            try:
                return date(y, mon_n, day_n)
            except ValueError:
                continue
        return _year_for(mon_n, day_n, ref)
    return None


HEADER_SKIP = re.compile(r"UPDATED|AS OF|LAST|EFFECTIVE|CHECK|SIGN|BEGINS|\bAT\b|CAO|CURRENT|VALID|THRU|THROUGH|NLT|PRIOR", re.I)


def is_day_header(line, ref):
    if HEADER_SKIP.search(line):
        return None
    if TIME_START.match(line):
        return None
    d = find_date(line, ref)
    if not d:
        return None
    rest = re.sub(DAYS_RE, " ", line.upper())
    rest = DATE_DMY.sub(" ", rest)
    rest = DATE_MDY.sub(" ", rest)
    rest = re.sub(r"DEPARTURES?(?: FROM)?:?.*", " ", rest)
    letters = re.sub(r"[^A-Z]", "", rest)
    if len(letters) > 12:
        return None
    return d


def norm_time(t):
    t = t.replace(":", "")
    if len(t) == 3:
        t = "0" + t
    hh, mm = int(t[:2]), int(t[2:])
    if hh > 23 or mm > 59:
        return None
    return "%02d:%02d" % (hh, mm)


def parse_seats(tok):
    if not tok:
        return None, None
    t = tok.upper().replace(" ", "")
    if t == "TBD":
        return None, "TBD"
    m = re.match(r"([TF])-?(\d+)$", t) or re.match(r"(\d+)([TF])$", t)
    if m:
        a, b = m.groups()
        if a.isdigit():
            return int(a), b
        return int(b), a
    m = re.match(r"(\d+)(SEATS)?$", t)
    if m:
        return int(m.group(1)), None
    return None, None


def _dest_text(line):
    s = line
    s = SEATS_END.sub(" ", s)
    s = TIME_START.sub(" ", s)
    s = re.sub(r"\s{2,}", "  ", s).strip(" *-")
    return s


def _looks_like_place(s):
    if not s or NOISE.search(s):
        return False
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) < 3 or len(s) > 70:
        return False
    if re.search(r"\d{3,}", s):
        return False
    # sentences (lots of lowercase words) are notes, not places
    words = s.split()
    if len(words) > 8:
        return False
    return True


def parse_72hr(text, ref=None):
    """Return list of departures: dict(date, roll_call, stops[], seats, seat_status, raw)."""
    ref = ref or date.today()
    lines = text.splitlines()
    flights = []
    mode = "dep"
    cur_date = None
    block = []  # (idx, line)

    def flush():
        if cur_date and mode == "dep" and block:
            flights.extend(_rows_from_block(block, cur_date))

    for i, raw in enumerate(lines):
        line = raw.rstrip()
        up = line.upper()
        if not line.strip():
            continue
        if re.search(r"\bARRIVALS?\b", up) and not TIME_START.match(line):
            flush(); block = []; mode = "arr"; cur_date = is_day_header(line, ref) or cur_date
            continue
        if re.search(r"\bDEPARTURES?\b", up) and not TIME_START.match(line):
            flush(); block = []; mode = "dep"
            d = is_day_header(line, ref)
            if d:
                cur_date = d
            continue
        d = is_day_header(line, ref)
        if d:
            # repeated date line inside the same block (Spangdahlem prints it twice)
            if d != cur_date or block:
                flush(); block = []
            cur_date = d
            continue
        if re.search(r"ALL FLIGHTS|SUBJECT TO CHANGE", up):
            flush(); block = []
            continue
        block.append((i, line))
    flush()
    # de-duplicate
    seen, out = set(), []
    for f in flights:
        k = (f["date"], f["roll_call"], tuple(f["stops"]))
        if k not in seen:
            seen.add(k); out.append(f)
    return out


def _rows_from_block(block, d):
    times, places = [], []
    for n, (i, line) in enumerate(block):
        m = TIME_START.match(line)
        if m and norm_time(m.group(1)):
            seat_m = SEATS_END.search(line[m.end():])
            dest = _dest_text(line[m.end():]) if True else ""
            times.append({"n": n, "time": norm_time(m.group(1)), "dest": dest if _looks_like_place(dest) else "",
                          "seats": seat_m.group(1) if seat_m else None})
        else:
            seat_m = SEATS_END.search(line)
            dest = _dest_text(line)
            if _looks_like_place(dest) or (seat_m and not dest):
                places.append({"n": n, "dest": dest if _looks_like_place(dest) else "",
                               "seats": seat_m.group(1) if seat_m else None})
    if not times:
        return []
    for t in times:
        t["above"], t["below"] = [], []
    # Destination lines between two time rows: the earlier row takes as many
    # lines below as it has above (multi-line groups are vertically centred);
    # the rest belong above the next row.
    times.sort(key=lambda t: t["n"])
    for idx, t in enumerate(times):
        prev_n = times[idx - 1]["n"] if idx else -10**9
        t["above"] = [p for p in places if prev_n < p["n"] < t["n"] and t["n"] - p["n"] <= 3]
        if idx:
            pt = times[idx - 1]
            want = len(pt["above"]) if (pt["above"] or not pt["dest"]) else 0
            if not pt["dest"] and not pt["above"]:
                want = 1
            take = [p for p in t["above"] if p["n"] - pt["n"] <= want]
            pt["below"] = take
            t["above"] = [p for p in t["above"] if p not in take]
    if times:
        last = times[-1]
        want = max(len(last["above"]), 0 if last["dest"] else 1)
        last["below"] = [p for p in places if last["n"] < p["n"] <= last["n"] + want]
    rows = []
    for t in times:
        stops = [p["dest"] for p in sorted(t["above"], key=lambda p: p["n"]) if p["dest"]]
        if t["dest"]:
            stops.append(t["dest"])
        stops += [p["dest"] for p in sorted(t["below"], key=lambda p: p["n"]) if p["dest"]]
        seats_tok = t["seats"] or next((p["seats"] for p in t["above"] + t["below"] if p["seats"]), None)
        # a bare number with no T/F that is actually part of a place name is unlikely; keep it
        seats, status = parse_seats(seats_tok)
        stops = [re.sub(r"\s{2,}", " ", s).strip(" ,*") for s in stops]
        stops = [s for s in stops if s]
        if not stops:
            continue
        rows.append({"date": d.isoformat(), "roll_call": t["time"], "stops": stops,
                     "seats": seats, "seat_status": status})
    return rows


RC_DATE = re.compile(r"^\s*(\d{1,2}\s*[- ]?\s*" + MON_RE + r"\.?(?:\s*-?\s*\d{2,4})?)\b", re.I)


def _cat(tok):
    t = (tok or "").strip().upper().replace("CAT", "").strip()
    return t if re.fullmatch(r"I{1,3}|IV|V|VI", t) else None


def parse_rollcall(text, ref=None):
    """Return list of past departures with seats released/used and lowest category."""
    ref = ref or date.today()
    lines = [l.rstrip() for l in text.splitlines()]
    out = []
    pending = []  # dest-only lines seen just before a date-only row
    consumed = set()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = RC_DATE.match(line)
        if not m:
            s = line.strip()
            if _looks_like_place(s) and re.search(r"[A-Z]{3}", s) and not re.search(r"REPORT|TERMINAL|RELEASE|SELECTED|COMPETED|CATEGORY", s, re.I):
                pending.append((i, s))
            continue
        d = find_date(m.group(1), ref)
        rest = line[m.end():]
        cols = [c.strip() for c in re.split(r"\s{2,}", rest.strip()) if c.strip()]
        if not cols or re.search(r"\bNO\b", cols[0], re.I) and re.search(r"FLIGHT|DEPART|ROLL|SPACE", cols[0], re.I):
            pending = []
            continue
        stops = []
        if cols and re.search(r"[A-Za-z]{3}", cols[0]) and not _cat(cols[0]) and cols[0].upper() not in ("N/A", "-"):
            stops.append(cols.pop(0))
        # attach multi-line destinations above (pending) and below (next lines without a date)
        above = [s for (j, s) in pending if i - j <= 2 and j not in consumed]
        want = len(above) if (above or stops) else 1
        below = []
        for j in range(i + 1, min(i + 1 + want, len(lines))):
            nxt = lines[j].strip()
            if not nxt or RC_DATE.match(lines[j]):
                break
            if _looks_like_place(nxt) and not re.search(r"REPORT|TERMINAL|RELEASE|SELECTED|COMPETED|CATEGORY|Seats", nxt, re.I):
                below.append(nxt); consumed.add(j)
            else:
                break
        stops = above + stops + below
        pending = []
        if not stops:
            continue
        released, rel_status = parse_seats(cols[0]) if cols else (None, None)
        used = None
        if len(cols) > 1 and re.fullmatch(r"\d{1,3}", cols[1]):
            used = int(cols[1])
        lowest = _cat(cols[2]) if len(cols) > 2 else None
        signup = cols[3] if len(cols) > 3 and re.search(r"\d", cols[3]) else None
        out.append({"date": d.isoformat() if d else None, "stops": stops, "released": released,
                    "released_status": rel_status, "used": used, "lowest_cat": lowest, "lowest_signup": signup})
    # roll-call pages often repeat (one slide per day); de-duplicate
    seen, res = set(), []
    for r in out:
        k = (r["date"], tuple(r["stops"]), r["released"], r["used"])
        if k not in seen:
            seen.add(k); res.append(r)
    return res


def last_updated(text, ref=None):
    ref = ref or date.today()
    m = re.search(r"(?:LAST UPDATED|UPDATED|AS OF)[: ]+([^\n]{0,40})", text, re.I)
    if m:
        d = find_date(m.group(1), ref)
        if d:
            return d.isoformat()
    return None


# ---------------------------------------------------------------- 30-day / monthly (Patriot Express) schedules
WEEKDAY_TOK = r"(?:MON|TUE|TUES|WED|THU|THUR|THURS|FRI|SAT|SUN)(?:DAY)?"
DAY_ONLY = re.compile(r"^\s*(\d{1,2})(?:\s*(?:ST|ND|RD|TH))?(?:\s+" + WEEKDAY_TOK + r")?\b(?!\s*[-:/.]\s*\d)", re.I)
DMY_START = re.compile(r"^\s*(\d{1,2})\s*[- ]?\s*" + MON_RE + r"\b\.?,?\s*(\d{4})?(?:\s+" + WEEKDAY_TOK + r")?", re.I)
NOTE_RE = re.compile(r"^\s*\*|SOFA|ONLY\*?$|STATUS TRAVELERS", re.I)


def _header_month(line):
    """'01-30 NOV 2026', 'NOVEMBER 2026', 'DECEMBER 01-31 2026', 'NOV - DEC 2026' -> (month, year)."""
    up = line.upper()
    ym = re.search(r"\b(20\d{2})\b", up)
    mm = re.search(MON_RE, up)
    if not (ym and mm):
        return None
    rest = re.sub(MON_RE, " ", up)
    rest = re.sub(r"\d+|[-–/,.:]", " ", rest)
    rest = re.sub(r"\b(SCHEDULE|MONTHLY|PATRIOT|EXPRESS|PE|DAY|30)\b", " ", rest)
    if len(re.sub(r"[^A-Z]", "", rest)) > 3:
        return None
    return MONTHS[mm.group(1)[:3]], int(ym.group(1))


def _clean_dest(s):
    s = re.sub(r"\s{2,}", " ", s).strip(" ,*-.")
    return s


def parse_30day(text, ref=None):
    """Return list of dict(date, stops[dest], note, cancelled) from monthly / 30-day schedules."""
    ref = ref or date.today()
    hdr = None          # (month, year) from the page header
    rows = []           # {"date": d, "dest": str|None, "note": str|None}
    pending = []        # dates still waiting for a destination
    last = None
    seen_cols = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if "\f" in raw:
            seen_cols = False
        up = line.upper()
        h = _header_month(line)
        if h and not seen_cols:
            hdr = h
            continue
        if h and not DMY_START.match(line) and not DAY_ONLY.match(line):
            hdr = h; seen_cols = False; pending = []
            continue
        if re.search(r"\bDESTINATION", up):
            seen_cols = True
            continue
        if re.search(r"SCHEDULE|PATRIOT EXPRESS|PASSENGER TERMINAL|COMMERCIAL GATEWAY|AIR TERMINAL", up) and not DMY_START.match(line):
            seen_cols = False; pending = []
            continue
        if not seen_cols:
            continue
        if re.search(r"SUBJECT TO CHANGE|SCHEDULE IS BASED|WILL POST|WILL BE|CONTINUE TO FOLLOW|ADDED THE|ORDERS|PERSONNEL|LAST UPDATED", up):
            pending = []
            continue
        # split multi-column rows ("13 NOV 2026  GTMO, CUBA     29 DEC 2026  GTMO, CUBA")
        starts = [m.start() for m in re.finditer(r"(?:(?<=\s)|^)\d{1,2}\s*[- ]?\s*" + MON_RE + r"\b", line, re.I)]
        segs = [line[a:b] for a, b in zip(starts, starts[1:] + [len(line)])] if len(starts) > 1 else [line]
        for seg in segs:
            d, rest = None, seg
            m = DMY_START.match(seg)
            if m:
                mon = MONTHS[m.group(2)[:3].upper()]
                yr = int(m.group(3)) if m.group(3) else (hdr[1] if hdr else None)
                try:
                    d = date(yr, mon, int(m.group(1))) if yr else _year_for(mon, int(m.group(1)), ref)
                except ValueError:
                    d = None
                rest = seg[m.end():]
            elif hdr:
                m = DAY_ONLY.match(seg)
                if m and 1 <= int(m.group(1)) <= 31:
                    try:
                        d = date(hdr[1], hdr[0], int(m.group(1)))
                    except ValueError:
                        d = None
                    rest = seg[m.end():]
            dest = _clean_dest(rest)
            if d:
                if dest and NOTE_RE.search(dest):
                    # a note in the destination column: same destination as the row above
                    if last and last["dest"]:
                        rows.append({"date": d, "dest": last["dest"], "note": dest.strip("* ")})
                        last = rows[-1]
                    continue
                if dest and re.search(r"[A-Za-z]{3}", dest):
                    for pd in pending:
                        rows.append({"date": pd, "dest": dest, "note": None})
                    pending = []
                    rows.append({"date": d, "dest": dest, "note": None}); last = rows[-1]
                else:
                    pending.append(d)
            elif dest and re.search(r"[A-Za-z]{3}", dest) and not NOISE.search(dest.replace("CANCELLED", "")):
                if NOTE_RE.search(dest):
                    if last:
                        last["note"] = dest.strip("* ")
                    continue
                if pending:
                    for pd in pending:
                        rows.append({"date": pd, "dest": dest, "note": None})
                    last = rows[-1]; pending = []
                elif last:
                    rows.append({"date": last["date"], "dest": dest, "note": None}); last = rows[-1]
    out, seen = [], set()
    for r in rows:
        cancelled = bool(re.search(r"\bCANCEL+ED\b", r["dest"], re.I))
        dest = _clean_dest(re.sub(r"\bCANCEL+ED\b", "", r["dest"], flags=re.I))
        k = (r["date"], dest.upper())
        if not dest or k in seen:
            continue
        seen.add(k)
        out.append({"date": r["date"].isoformat(), "stops": [dest], "note": r["note"], "cancelled": cancelled})
    return out
