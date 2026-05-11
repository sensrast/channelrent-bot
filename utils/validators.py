import re

URL_RE = re.compile(r"^https?://[^\s]+$")
USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
UPI_RE = re.compile(r"^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z]{1,64}$")

def is_url(s): return bool(URL_RE.match(s.strip()))
def is_username(s): return bool(USERNAME_RE.match(s.strip()))
def is_upi(s): return bool(UPI_RE.match(s.strip()))

def parse_int(s, lo=None, hi=None):
    try:
        v = int(s.strip().replace(",",""))
    except Exception:
        return None
    if lo is not None and v < lo: return None
    if hi is not None and v > hi: return None
    return v

def parse_buttons(text, max_buttons=5):
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line: continue
        if " - " not in line: return None
        label, url = line.rsplit(" - ", 1)
        label, url = label.strip(), url.strip()
        if not label or not is_url(url): return None
        rows.append((label, url))
        if len(rows) >= max_buttons: break
    return rows or None

def normalize_channel_link(s):
    s = s.strip()
    if s.startswith("https://t.me/"): s = s[len("https://t.me/"):]
    elif s.startswith("http://t.me/"): s = s[len("http://t.me/"):]
    elif s.startswith("t.me/"): s = s[len("t.me/"):]
    if s.startswith("@"): s = s[1:]
    return s
