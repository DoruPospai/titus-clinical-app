import re
import unicodedata
from typing import List, Optional

def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )

def normalize_text(text: object) -> str:
    if text is None:
        return ""
    s = str(text)
    s = strip_accents(s).lower()
    s = re.sub(r"[_/|]+", " ", s)
    s = re.sub(r"[^a-z0-9:+\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def normalize_nature(value: object) -> Optional[str]:
    if value is None:
        return None
    txt = str(value).strip()
    low = txt.lower()
    if low == "sympt":
        return "Sympt"
    if low == "signe":
        return "Signe"
    return txt if txt else None

def months_between(dob, today) -> int:
    if dob is None or dob > today:
        return 0
    m = (today.year - dob.year) * 12 + (today.month - dob.month)
    if today.day < dob.day:
        m -= 1
    return max(0, int(m))

def split_synonyms(raw: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[\t,;|]+", raw)
    return [p.strip() for p in parts if p.strip()]

def token_set(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", normalize_text(s)))

def safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return float(default)
        s = str(x).strip().replace(",", ".")
        if not s:
            return float(default)
        return float(s)
    except Exception:
        return float(default)
