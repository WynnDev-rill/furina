from __future__ import annotations

import re


_LEADING = [
    (re.compile(r"^\s*(?:tentu saja|tentu|baiklah)[,!.:\s]+", re.I), ""),
    (re.compile(r"^\s*(?:perlu dicatat bahwa|penting untuk dicatat bahwa)\s+", re.I), ""),
]

_REPLACEMENTS = [
    (re.compile(r"\bperlu dicatat bahwa\b[, ]*", re.I), ""),
    (re.compile(r"\bpenting untuk dicatat bahwa\b[, ]*", re.I), ""),
    (re.compile(r"\bdalam konteks ini\b", re.I), "di sini"),
    (re.compile(r"\bdengan demikian\b", re.I), "jadi"),
    (re.compile(r"\boleh karena itu\b", re.I), "jadi"),
    (re.compile(r"\boleh sebab itu\b", re.I), "jadi"),
    (re.compile(r"\bnamun demikian\b", re.I), "tapi"),
    (re.compile(r"\bpada dasarnya\b", re.I), "intinya"),
    (re.compile(r"\bhal tersebut\b", re.I), "itu"),
    (re.compile(r"\bhal ini\b", re.I), "ini"),
    (re.compile(r"\bmari kita\b", re.I), "kita"),
]

_GENERIC_TAIL = re.compile(
    r"(?:\n|\s)*(?:kalau|jika) (?:kamu )?mau,? aku bisa (?:membantu|bantu)[^.?!]*(?:[.?!])?\s*$",
    re.I,
)


def _clean_segment(text: str, *, technical: bool) -> str:
    out = text
    for rx, repl in _LEADING:
        out = rx.sub(repl, out, count=1)
    for rx, repl in _REPLACEMENTS:
        if technical and rx.pattern in {r"\bhal tersebut\b", r"\bhal ini\b"}:
            continue
        out = rx.sub(repl, out)
    out = _GENERIC_TAIL.sub("", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([,.!?;:])", r"\1", out)
    if out.count("—") >= 3:
        out = out.replace(" — ", ", ")
    return out.strip()


def naturalize(text: str, *, technical: bool = False) -> str:
    """Remove a small set of high-confidence synthetic/formal habits.

    This is intentionally rule-based and conservative: no second model pass,
    no extra API tokens, and fenced code is preserved byte-for-byte.
    """
    raw = str(text or "")
    if not raw.strip():
        return raw
    parts = re.split(r"(```[\s\S]*?```)", raw)
    cleaned: list[str] = []
    for part in parts:
        if part.startswith("```"):
            cleaned.append(part)
        else:
            cleaned.append(_clean_segment(part, technical=technical))
    out = "".join(cleaned).strip()
    return out or raw.strip()
