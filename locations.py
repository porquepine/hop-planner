"""Gazetteer of Space-A locations and a normalizer for the messy destination
strings found in AMC schedules ("MIGUIRE FORT DIX, NEW JERSEY", "*Dover Air
Force Base, Delaware*", "JB PEARL HARBOR-HICKAM, HI" ...).

Each place: key -> (name, region code, country, lat, lon, aliases, terminal?)
region code = US state abbreviation for US places, else ISO-ish country code.
Coordinates are approximate (good enough for distance / flight-time estimates).
"""
import re
import difflib

# fmt: off
PLACES = {
 # ---- CONUS: AMC terminals / gateways
 "DOV": ("Dover AFB", "DE", "US", 39.13, -75.47, ["DOVER"], True),
 "CHS": ("JB Charleston", "SC", "US", 32.90, -80.04, ["CHARLESTON AFB", "JB CHARLESTON", "LINDSEY GRAHAM", "JB CHS", "CHARLESTON, SC", "CHARLESTON SC"], True),
 "WRI": ("JB McGuire-Dix-Lakehurst", "NJ", "US", 40.02, -74.59, ["MCGUIRE", "MIGUIRE", "MC GUIRE", "FORT DIX", "FT DIX", "JBMDL", "MDL", "LAKEHURST"], True),
 "ADW": ("JB Andrews", "MD", "US", 38.81, -76.87, ["ANDREWS"], True),
 "BWI": ("BWI Airport (AMC Gateway)", "MD", "US", 39.18, -76.67, ["BWI", "BALTIMORE"], True),
 "NGU": ("NS Norfolk", "VA", "US", 36.94, -76.29, ["NORFOLK", "NGU"], True),
 "SUU": ("Travis AFB", "CA", "US", 38.26, -121.93, ["TRAVIS"], True),
 "TCM": ("JB Lewis-McChord", "WA", "US", 47.14, -122.48, ["MCCHORD", "LEWIS-MCCHORD", "LEWIS MCCHORD", "JBLM", "TCM"], True),
 "SEA": ("Seattle-Tacoma Intl (AMC Gateway)", "WA", "US", 47.45, -122.31, ["SEATTLE", "SEA-TAC", "SEATAC", "SEA TAC"], True),
 "SKA": ("Fairchild AFB", "WA", "US", 47.62, -117.66, ["FAIRCHILD", "SPOKANE"], True),
 "BLV": ("Scott AFB", "IL", "US", 38.55, -89.84, ["SCOTT AFB", "SCOTT AIR", "SCOTT FIELD"], True),
 "IAB": ("McConnell AFB", "KS", "US", 37.62, -97.27, ["MCCONNELL", "WICHITA"], True),
 "LRF": ("Little Rock AFB", "AR", "US", 34.92, -92.15, ["LITTLE ROCK"], True),
 "MCF": ("MacDill AFB", "FL", "US", 27.85, -82.52, ["MACDILL", "TAMPA"], True),
 "NIP": ("NAS Jacksonville", "FL", "US", 30.24, -81.68, ["JACKSONVILLE", "NAS JAX", "JAX"], True),
 "POB": ("Pope AAF / Fort Bragg", "NC", "US", 35.17, -79.01, ["POPE", "FORT BRAGG", "FT BRAGG", "FORT LIBERTY"], True),
 "VPS": ("Eglin AFB", "FL", "US", 30.48, -86.53, ["EGLIN"], True),
 # ---- Texas
 "SKF": ("JBSA-Lackland (Kelly Field)", "TX", "US", 29.38, -98.58, ["LACKLAND", "KELLY", "JBSA", "SAN ANTONIO"], True),
 "NFW": ("NAS JRB Fort Worth", "TX", "US", 32.77, -97.44, ["FORT WORTH", "FT WORTH", "FORTWORTH", "CARSWELL", "NAS JRB FW"], True),
 "DYS": ("Dyess AFB", "TX", "US", 32.42, -99.85, ["DYESS", "ABILENE"], True),
 "BIF": ("Biggs AAF / Fort Bliss", "TX", "US", 31.85, -106.38, ["BIGGS", "FORT BLISS", "FT BLISS", "EL PASO"], True),
 "GRK": ("Robert Gray AAF / Fort Cavazos", "TX", "US", 31.07, -97.83, ["ROBERT GRAY", "GRAY AAF", "FORT HOOD", "FT HOOD", "FORT CAVAZOS", "KILLEEN"], True),
 "EFD": ("Ellington Field (147th ATKW)", "TX", "US", 29.61, -95.16, ["ELLINGTON", "HOUSTON"], True),
 "RND": ("JBSA-Randolph", "TX", "US", 29.53, -98.28, ["RANDOLPH"], True),
 "LBB": ("Reese / Lubbock", "TX", "US", 33.66, -101.82, ["LUBBOCK"], False),
 "SPS": ("Sheppard AFB", "TX", "US", 33.99, -98.49, ["SHEPPARD", "WICHITA FALLS"], True),
 "GDP": ("Goodfellow AFB", "TX", "US", 31.43, -100.40, ["GOODFELLOW", "SAN ANGELO"], False),
 "DLF": ("Laughlin AFB", "TX", "US", 29.36, -100.78, ["LAUGHLIN", "DEL RIO"], False),
 "NQI": ("NAS Kingsville", "TX", "US", 27.51, -97.81, ["KINGSVILLE"], False),
 "NGP": ("NAS Corpus Christi", "TX", "US", 27.69, -97.29, ["CORPUS CHRISTI"], False),
 # ---- Other CONUS frequently seen
 "LTS": ("Altus AFB", "OK", "US", 34.67, -99.27, ["ALTUS"], True),
 "TIK": ("Tinker AFB", "OK", "US", 35.41, -97.39, ["TINKER", "OKLAHOMA CITY"], True),
 "BAD": ("Barksdale AFB", "LA", "US", 32.50, -93.66, ["BARKSDALE", "SHREVEPORT"], True),
 "NBG": ("NAS JRB New Orleans", "LA", "US", 29.83, -90.03, ["NEW ORLEANS", "BELLE CHASSE"], True),
 "MGE": ("Dobbins ARB", "GA", "US", 33.92, -84.52, ["DOBBINS", "MARIETTA", "ATLANTA"], True),
 "WRB": ("Robins AFB", "GA", "US", 32.64, -83.59, ["ROBINS AFB", "WARNER ROBINS"], True),
 "SVN": ("Hunter AAF", "GA", "US", 32.01, -81.15, ["HUNTER AAF", "HUNTER ARMY"], True),
 "SAV": ("Savannah ANGB (165th AW)", "GA", "US", 32.13, -81.20, ["SAVANNAH"], True),
 "MXF": ("Maxwell AFB", "AL", "US", 32.38, -86.36, ["MAXWELL", "MONTGOMERY"], True),
 "CEF": ("Westover ARB", "MA", "US", 42.19, -72.53, ["WESTOVER", "CHICOPEE", "SPRINGFIELD, MA", "SPRINGFIELD MASS"], True),
 "MRB": ("Martinsburg (167th AW)", "WV", "US", 39.40, -77.98, ["MARTINSBURG", "MARTINSUBRG", "SHEPHERD FIELD"], True),
 "CRW": ("McLaughlin ANGB (130th AW)", "WV", "US", 38.37, -81.59, ["CHARLESTON, WV", "CHARLESTON WV", "YEAGER", "MCLAUGHLIN"], True),
 "PIT": ("Pittsburgh ARS", "PA", "US", 40.49, -80.23, ["PITTSBURGH"], True),
 "NUW": ("NAS Whidbey Island", "WA", "US", 48.35, -122.66, ["WHIDBEY"], True),
 "NZY": ("NAS North Island", "CA", "US", 32.70, -117.21, ["NORTH ISLAND", "CORONADO", "SAN DIEGO"], True),
 "RIV": ("March ARB", "CA", "US", 33.88, -117.26, ["MARCH ARB", "MARCH AIR", "RIVERSIDE"], True),
 "BAB": ("Beale AFB", "CA", "US", 39.14, -121.44, ["BEALE"], True),
 "OFF": ("Offutt AFB", "NE", "US", 41.12, -95.91, ["OFFUTT", "OMAHA"], True),
 "LNK": ("Lincoln ANGB (155th ARW)", "NE", "US", 40.85, -96.76, ["LINCOLN"], True),
 "GUS": ("Grissom ARB", "IN", "US", 40.65, -86.15, ["GRISSOM"], True),
 "LSV": ("Nellis AFB", "NV", "US", 36.24, -115.03, ["NELLIS", "LAS VEGAS"], True),
 "HIF": ("Hill AFB", "UT", "US", 41.12, -111.97, ["HILL AFB", "HILL AIR", "OGDEN"], True),
 "LFI": ("JB Langley-Eustis", "VA", "US", 37.08, -76.36, ["LANGLEY", "EUSTIS", "JBLE"], True),
 "FFO": ("Wright-Patterson AFB", "OH", "US", 39.83, -84.05, ["WRIGHT-PATT", "WRIGHT PATT", "WRIGHT PATTERSON", "DAYTON"], True),
 "SZL": ("Whiteman AFB", "MO", "US", 38.73, -93.55, ["WHITEMAN"], True),
 "STJ": ("Rosecrans ANGB (139th AW)", "MO", "US", 39.77, -94.91, ["ROSECRANS", "ST JOSEPH", "SAINT JOSEPH"], True),
 "MEM": ("Memphis ANGB (164th AW)", "TN", "US", 35.04, -89.98, ["MEMPHIS"], True),
 "CYS": ("Cheyenne ANGB (153rd AW)", "WY", "US", 41.16, -104.81, ["CHEYENNE"], True),
 "MSP": ("Minneapolis-St Paul ARS (133rd AW)", "MN", "US", 44.88, -93.22, ["MINNEAPOLIS", "ST PAUL", "SAINT PAUL"], True),
 "SDF": ("Louisville ANGB (123rd AW)", "KY", "US", 38.17, -85.74, ["LOUISVILLE"], True),
 "HOP": ("Campbell AAF / Fort Campbell", "KY", "US", 36.67, -87.49, ["CAMPBELL"], True),
 "SCH": ("Stratton ANGB (109th AW)", "NY", "US", 42.85, -73.93, ["STRATTON", "SCHENECTADY"], True),
 "GTB": ("Wheeler-Sack AAF / Fort Drum", "NY", "US", 44.06, -75.72, ["WHEELER-SACK", "FORT DRUM", "FT DRUM"], True),
 "IAG": ("Niagara Falls ARS", "NY", "US", 43.11, -78.95, ["NIAGARA"], True),
 "PSM": ("Pease ANGB (157th ARW)", "NH", "US", 43.08, -70.82, ["PEASE", "PORTSMOUTH, NH", "PORTSMOUTH NH", "PORTSMOUTH"], True),
 "BGR": ("Bangor ANGB (101st ARW)", "ME", "US", 44.81, -68.83, ["BANGOR"], True),
 "CLT": ("Charlotte ANGB (145th AW)", "NC", "US", 35.21, -80.94, ["CHARLOTTE"], True),
 "SSC": ("Shaw AFB", "SC", "US", 33.97, -80.47, ["SHAW AFB"], False),
 "GSB": ("Seymour Johnson AFB", "NC", "US", 35.34, -77.96, ["SEYMOUR JOHNSON"], True),
 "VAD": ("Moody AFB", "GA", "US", 30.97, -83.19, ["MOODY"], True),
 "BIX": ("Keesler AFB", "MS", "US", 30.41, -88.92, ["KEESLER", "BILOXI"], True),
 "CVS": ("Cannon AFB", "NM", "US", 34.38, -103.32, ["CANNON"], True),
 "HMN": ("Holloman AFB", "NM", "US", 32.85, -106.11, ["HOLLOMAN"], True),
 "ABQ": ("Kirtland AFB", "NM", "US", 35.04, -106.61, ["KIRTLAND", "ALBUQUERQUE"], True),
 "DMA": ("Davis-Monthan AFB", "AZ", "US", 32.17, -110.88, ["DAVIS-MONTHAN", "DAVIS MONTHAN", "TUCSON"], True),
 "LUF": ("Luke AFB", "AZ", "US", 33.54, -112.38, ["LUKE AFB", "PHOENIX"], False),
 "MUO": ("Mountain Home AFB", "ID", "US", 43.04, -115.87, ["MOUNTAIN HOME"], True),
 "RCA": ("Ellsworth AFB", "SD", "US", 44.15, -103.10, ["ELLSWORTH"], True),
 "BVS": ("Hanscom AFB", "MA", "US", 42.47, -71.29, ["HANSCOM", "BOSTON"], True),
 "NKX": ("MCAS Miramar", "CA", "US", 32.87, -117.14, ["MIRAMAR"], False),
 "FTK": ("Godman AAF / Fort Knox", "KY", "US", 37.91, -85.97, ["FORT KNOX", "GODMAN"], False),
 "LSF": ("Lawson AAF / Fort Benning", "GA", "US", 32.34, -84.99, ["LAWSON", "FORT BENNING", "FORT MOORE"], False),
 "NPA": ("NAS Pensacola", "FL", "US", 30.35, -87.32, ["PENSACOLA"], False),
 "NQX": ("NAS Key West", "FL", "US", 24.58, -81.69, ["KEY WEST"], False),
 "PAM": ("Tyndall AFB", "FL", "US", 30.07, -85.58, ["TYNDALL"], False),
 # ---- Alaska / Hawaii / Pacific
 "EDF": ("JB Elmendorf-Richardson", "AK", "US", 61.25, -149.81, ["ELMENDORF", "JBER", "ANCHORAGE"], True),
 "EIL": ("Eielson AFB", "AK", "US", 64.67, -147.10, ["EIELSON", "FAIRBANKS"], True),
 "HIK": ("JB Pearl Harbor-Hickam", "HI", "US", 21.32, -157.92, ["HICKAM", "PEARL HARBOR", "HONOLULU"], True),
 "UAM": ("Andersen AFB, Guam", "GU", "US", 13.58, 144.93, ["ANDERSEN", "GUAM"], True),
 "AWK": ("Wake Island", "UM", "US", 19.28, 166.64, ["WAKE ISLAND", "WAKE"], False),
 "KWA": ("Kwajalein", "MH", "MH", 8.72, 167.73, ["KWAJALEIN"], False),
 "DNA": ("Kadena AB, Okinawa", "JP", "JP", 26.36, 127.77, ["KADENA", "OKINAWA"], True),
 "OKO": ("Yokota AB", "JP", "JP", 35.75, 139.35, ["YOKOTA", "TOKYO"], True),
 "MSJ": ("Misawa AB", "JP", "JP", 40.70, 141.37, ["MISAWA"], True),
 "IWA": ("MCAS Iwakuni", "JP", "JP", 34.14, 132.24, ["IWAKUNI"], True),
 "NJA": ("NAF Atsugi", "JP", "JP", 35.45, 139.45, ["ATSUGI"], False),
 "OSN": ("Osan AB", "KR", "KR", 37.09, 127.03, ["OSAN"], True),
 "KUV": ("Kunsan AB", "KR", "KR", 35.90, 126.62, ["KUNSAN"], True),
 "QPG": ("Paya Lebar AB", "SG", "SG", 1.36, 103.91, ["PAYA LEBAR", "SINGAPORE"], True),
 "NKW": ("Diego Garcia", "IO", "IO", -7.31, 72.41, ["DIEGO GARCIA"], True),
 "DRW": ("Darwin", "AU", "AU", -12.41, 130.88, ["DARWIN"], False),
 "AMB": ("RAAF Amberley", "AU", "AU", -27.64, 152.71, ["AMBERLEY"], False),
 "CHC": ("Christchurch", "NZ", "NZ", -43.49, 172.53, ["CHRISTCHURCH"], False),
 # ---- Europe
 "RMS": ("Ramstein AB", "DE", "DE", 49.44, 7.60, ["RAMSTEIN"], True),
 "SPM": ("Spangdahlem AB", "DE", "DE", 49.97, 6.69, ["SPANGDAHLEM"], True),
 "GHF": ("Wiesbaden AAF", "DE", "DE", 50.05, 8.33, ["WIESBADEN"], False),
 "MHZ": ("RAF Mildenhall", "GB", "GB", 52.36, 0.49, ["MILDENHALL"], True),
 "LKZ": ("RAF Lakenheath", "GB", "GB", 52.41, 0.56, ["LAKENHEATH"], False),
 "FFD": ("RAF Fairford", "GB", "GB", 51.68, -1.79, ["FAIRFORD"], False),
 "ROZ": ("NS Rota", "ES", "ES", 36.64, -6.35, ["ROTA"], True),
 "OZP": ("Moron AB", "ES", "ES", 37.17, -5.62, ["MORON"], False),
 "AVB": ("Aviano AB", "IT", "IT", 46.03, 12.60, ["AVIANO"], True),
 "SIZ": ("NAS Sigonella", "IT", "IT", 37.40, 14.92, ["SIGONELLA"], True),
 "NAP": ("NSA Naples", "IT", "IT", 40.88, 14.29, ["NAPLES", "CAPODICHINO"], True),
 "CHQ": ("NSA Souda Bay", "GR", "GR", 35.53, 24.15, ["SOUDA", "CRETE", "CHANIA"], True),
 "ADA": ("Incirlik AB", "TR", "TR", 37.00, 35.43, ["INCIRLIK"], True),
 "LGS": ("Lajes Field, Azores", "PT", "PT", 38.76, -27.09, ["LAJES", "AZORES"], True),
 "KEF": ("Keflavik", "IS", "IS", 63.99, -22.61, ["KEFLAVIK", "ICELAND"], False),
 "THU": ("Pituffik SB (Thule)", "GL", "GL", 76.53, -68.70, ["THULE", "PITUFFIK"], False),
 "EPPW": ("Powidz AB", "PL", "PL", 52.38, 17.85, ["POWIDZ"], False),
 "CND": ("Mihail Kogalniceanu AB", "RO", "RO", 44.36, 28.49, ["KOGALNICEANU", "MK AB", "CONSTANTA"], False),
 "CRL": ("Chievres AB", "BE", "BE", 50.58, 3.83, ["CHIEVRES"], False),
 "VAR": ("Vilseck / Grafenwoehr", "DE", "DE", 49.69, 11.87, ["GRAFENWOEHR", "VILSECK"], False),
 # ---- Middle East / Africa / Americas
 "BAH": ("NSA Bahrain", "BH", "BH", 26.27, 50.63, ["BAHRAIN", "ISA AB"], True),
 "XJD": ("Al Udeid AB", "QA", "QA", 25.12, 51.32, ["AL UDEID", "UDEID", "QATAR"], True),
 "KWI": ("Kuwait (Cargo City)", "KW", "KW", 29.24, 47.97, ["KUWAIT", "ALI AL SALEM"], True),
 "JIB": ("Camp Lemonnier, Djibouti", "DJ", "DJ", 11.55, 43.15, ["DJIBOUTI", "AMBOULI", "LEMONNIER"], False),
 "NBW": ("NS Guantanamo Bay", "CU", "CU", 19.91, -75.21, ["GUANTANAMO", "GITMO"], True),
 "XPL": ("Soto Cano AB", "HN", "HN", 14.38, -87.62, ["SOTO CANO", "PALMEROLA", "HONDURAS"], True),
 "SJU": ("Puerto Rico (Muniz ANGB)", "PR", "US", 18.44, -66.00, ["PUERTO RICO", "MUNIZ", "SAN JUAN"], False),
 "ASI": ("Ascension Island", "SH", "SH", -7.97, -14.39, ["ASCENSION"], False),
}
# fmt: on

US_STATES = {
 "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS", "CA": "CALIFORNIA", "CO": "COLORADO",
 "CT": "CONNECTICUT", "DE": "DELAWARE", "FL": "FLORIDA", "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO",
 "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS", "KY": "KENTUCKY", "LA": "LOUISIANA",
 "ME": "MAINE", "MD": "MARYLAND", "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA",
 "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA", "NE": "NEBRASKA", "NV": "NEVADA",
 "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK", "NC": "NORTH CAROLINA",
 "ND": "NORTH DAKOTA", "OH": "OHIO", "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA",
 "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS",
 "UT": "UTAH", "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
 "WI": "WISCONSIN", "WY": "WYOMING", "DC": "DISTRICT OF COLUMBIA", "GU": "GUAM", "PR": "PUERTO RICO",
}
COUNTRIES = {
 "DE": "GERMANY", "GB": "UNITED KINGDOM", "ES": "SPAIN", "IT": "ITALY", "GR": "GREECE", "TR": "TURKEY",
 "PT": "PORTUGAL", "IS": "ICELAND", "GL": "GREENLAND", "PL": "POLAND", "RO": "ROMANIA", "BE": "BELGIUM",
 "JP": "JAPAN", "KR": "KOREA", "SG": "SINGAPORE", "AU": "AUSTRALIA", "NZ": "NEW ZEALAND", "BH": "BAHRAIN",
 "QA": "QATAR", "KW": "KUWAIT", "DJ": "DJIBOUTI", "CU": "CUBA", "HN": "HONDURAS", "CO": "COLOMBIA",
 "MH": "MARSHALL ISLANDS", "IO": "DIEGO GARCIA", "SH": "ASCENSION", "US": "UNITED STATES",
 "AE": "UNITED ARAB EMIRATES", "SA": "SAUDI ARABIA", "JO": "JORDAN", "IL": "ISRAEL", "EG": "EGYPT",
 "KE": "KENYA", "PH": "PHILIPPINES", "TH": "THAILAND", "IQ": "IRAQ", "SY": "SYRIA", "NO": "NORWAY",
 "EE": "ESTONIA", "LT": "LITHUANIA", "LV": "LATVIA", "BG": "BULGARIA", "HU": "HUNGARY", "CZ": "CZECHIA",
 "NL": "NETHERLANDS", "FR": "FRANCE", "BR": "BRAZIL", "PE": "PERU", "SV": "EL SALVADOR", "PA": "PANAMA",
 "CA": "CANADA", "MX": "MEXICO", "IN": "INDIA", "UM": "WAKE ISLAND",
}
COUNTRY_ALIASES = {"GER": "DE", "GE": "DE", "GERMANY": "DE", "UK": "GB", "ENGLAND": "GB", "ITA": "IT",
                   "SP": "ES", "SPA": "ES", "JPN": "JP", "ROK": "KR", "SOUTH KOREA": "KR", "REPUBLIC OF KOREA": "KR",
                   "TUR": "TR", "TURKIYE": "TR", "GRC": "GR", "PRT": "PT"}
STATE_MISSPELL = {"MASSACHUTES": "MA", "MASSACHUSSETTS": "MA", "PENNSYLVANNIA": "PA", "CALIF": "CA",
                  "DELEWARE": "DE", "MARYLAN": "MD", "VIRGINA": "VA", "TEX": "TX"}

_NAME_TO_STATE = {v: k for k, v in US_STATES.items()}
_NAME_TO_COUNTRY = {v: k for k, v in COUNTRIES.items()}


def clean(s):
    s = s.upper().replace("–", "-").replace("’", "'")
    s = re.sub(r"[*#()\[\]]", " ", s)
    s = re.sub(r"\bAIR FORCE BASE\b", "AFB", s)
    s = re.sub(r"\bAIR BASE\b", "AB", s)
    s = re.sub(r"\bJOINT BASE\b", "JB", s)
    s = re.sub(r"\bNAVAL AIR STATION\b", "NAS", s)
    s = re.sub(r"\bNAVAL STATION\b", "NS", s)
    s = re.sub(r"\bINTERNATIONAL\b", "INTL", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.-")
    return s


_ALIAS_INDEX = []  # (alias, key) longest first
for _k, _p in PLACES.items():
    for _a in [_p[0].upper()] + _p[5]:
        _ALIAS_INDEX.append((clean(_a), _k))
_ALIAS_INDEX.sort(key=lambda x: -len(x[0]))


def _region_from_text(s):
    """Return (region, country) from the tail of a place string."""
    parts = [p.strip() for p in s.split(",")]
    tail = parts[-1] if len(parts) > 1 else ""
    for cand in [tail, s]:
        c = cand.strip()
        if c in US_STATES:
            return c, "US"
        if c in _NAME_TO_STATE:
            return _NAME_TO_STATE[c], "US"
        if c in STATE_MISSPELL:
            return STATE_MISSPELL[c], "US"
        if c in COUNTRY_ALIASES:
            cc = COUNTRY_ALIASES[c]
            return cc, cc
        if c in _NAME_TO_COUNTRY:
            cc = _NAME_TO_COUNTRY[c]
            return cc, cc
    for name, cc in _NAME_TO_COUNTRY.items():
        if re.search(r"\b%s\b" % re.escape(name), s):
            return cc, cc
    for name, st in _NAME_TO_STATE.items():
        if len(name) > 5 and re.search(r"\b%s\b" % re.escape(name), s):
            return st, "US"
    return None, None


def resolve(raw):
    """Map a raw destination string to a place dict. Unknown places get an
    ad-hoc key so they still show up (and can be matched by state/country)."""
    s = clean(raw)
    if not s:
        return None
    for alias, key in _ALIAS_INDEX:
        if len(alias) >= 4 and re.search(r"(^|[^A-Z])%s([^A-Z]|$)" % re.escape(alias), s):
            return place(key)
    # fuzzy on the part before the comma (handles typos)
    head = s.split(",")[0].strip()
    cands = difflib.get_close_matches(head, [a for a, _ in _ALIAS_INDEX], n=1, cutoff=0.84)
    if cands:
        return place(dict(_ALIAS_INDEX)[cands[0]])
    words = head.split()
    for w in words:
        if len(w) >= 6:
            c = difflib.get_close_matches(w, [a for a, _ in _ALIAS_INDEX if " " not in a], n=1, cutoff=0.84)
            if c:
                return place(dict(_ALIAS_INDEX)[c[0]])
    region, country = _region_from_text(s)
    key = "X-" + re.sub(r"[^A-Z0-9]+", "-", head)[:30].strip("-")
    return {"key": key, "name": raw.strip(" *").title(), "region": region, "country": country,
            "lat": None, "lon": None, "terminal": False, "known": False}


def place(key):
    p = PLACES[key]
    return {"key": key, "name": p[0], "region": p[1], "country": p[2], "lat": p[3], "lon": p[4],
            "terminal": p[6], "known": True}


def gazetteer():
    out = []
    for k in PLACES:
        d = place(k)
        d["aliases"] = PLACES[k][5]
        out.append(d)
    return out
