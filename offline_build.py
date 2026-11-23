"""Build a payload from saved sample PDFs instead of the live AMC site.
Usage: python3 tests/offline_build.py <samples_dir>
Used to test the parser + planner without network access."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))
import collect  # noqa: E402

SAMPLES = sys.argv[1] if len(sys.argv) > 1 else "samples"
MAP = {  # terminal key -> sample files
    "BWI": [("72", "bwi72.pdf"), ("30", "bwi30.pdf")], "SPM": [("72", "spang72.pdf")], "RMS": [("72", "ram72.pdf"), ("30", "ramstein30.pdf")],
    "WRI": [("72", "mcguire72.pdf")], "NGU": [("72", "norfolk72.pdf"), ("30", "norfolk30.pdf")], "SUU": [("72", "travis72.pdf"), ("rc", "travis_rc.pdf")],
    "ROZ": [("72", "rota72.pdf")], "CHS": [("rc", "chsrc.pdf")], "ADW": [("rc", "andrews_rc.pdf")],
    "EIL": [("rc", "eielson_rc.pdf")], "HIK": [("rc", "hickam_rc.pdf"), ("30", "hickam30.pdf")],
    "SEA": [("30", "sea30.pdf")], "NIP": [("30", "jax30.pdf")], "DNA": [("30", "kadena30.pdf")], "OSN": [("30", "osan30.pdf")],
}


class R:
    def __init__(self, c): self.content = c; self.status_code = 200


def find_docs(page_url):
    t = next(t for t in json.load(open(os.path.join(collect.HERE, "terminals.json"))) if t["page"] == page_url)
    return [{"kind": k, "url": "file://" + os.path.join(SAMPLES, f), "file": f} for k, f in MAP.get(t["key"], [])], None


def get(url, **kw):
    return R(open(url[7:], "rb").read())


collect.find_docs = find_docs
collect.get = get
collect.main()
