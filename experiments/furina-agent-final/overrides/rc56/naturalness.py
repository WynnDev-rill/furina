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

_GENERIC_TAILS = [
    re.compile(r"(?:\n|\s)*(?:kalau|jika) (?:kamu )?mau,? aku bisa (?:membantu|bantu)[^.?!]*(?:[.?!])?\s*$", re.I),
    re.compile(r"(?:\n|\s)*(?:ada )?(?:yang )?(?:bisa|ingin|mau|pengen) (?:aku bantu|kubantu|dibicarakan|kamu bicarakan)[^.!?]*\?\s*$", re.I),
    re.compile(r"(?:\n|\s)*ada (?:yang|sesuatu) (?:pengen|ingin|mau) (?:dibicarakan|kamu bicarakan)[^.!?]*\?\s*$", re.I),
    re.compile(r"(?:\n|\s)*(?:kalau|jika) (?:kamu )?berubah pikiran,? (?:beri tahu|bilang|kabari)(?: aku)?(?: saja)?[.!?]*\s*$", re.I),
    re.compile(r"(?:\n|\s)*aku (?:akan )?ada di sini (?:kalau|jika) (?:kamu )?(?:butuh|membutuhkan)[^.?!]*(?:[.?!])?\s*$", re.I),
]

_CANNED_DECLINE = re.compile(
    r"^\s*(?:oke|ok|baik|baiklah|ya|iya)[,.! ]+(?:kalau|jika) (?:kamu )?berubah pikiran,? "
    r"(?:beri tahu|bilang|kabari)(?: aku)?(?: saja)?[.!?]*\s*$",
    re.I,
)

_IDENTITY_AMBIGUOUS_OPEN = re.compile(
    r"^\s*(?:hidup\?\s*)?(?:h+m+[,!. ]*)?(?:itu )?pertanyaan (?:yang )?(?:agak )?ambigu[,!.:\s]+",
    re.I,
)


def _strip_generic_tails(text: str) -> str:
    out = text
    for rx in _GENERIC_TAILS:
        out = rx.sub("", out)
    return out.strip()


def _sentence_cap(text: str, *, max_sentences: int, max_chars: int) -> str:
    if len(text) <= max_chars:
        pieces = re.split(r"(?<=[.!?])\s+", text.strip())
        if len(pieces) <= max_sentences:
            return text.strip()
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = " ".join(p for p in pieces[:max_sentences] if p.strip()).strip()
    if not kept:
        kept = text.strip()
    if len(kept) > max_chars:
        cut = kept[:max_chars].rstrip()
        # Prefer a natural boundary rather than chopping a word.
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0].rstrip(" ,;:")
        kept = cut
        if kept and kept[-1] not in ".!?":
            kept += "."
    return kept


def _clean_segment(text: str, *, technical: bool, profile: str) -> str:
    out = text
    if _CANNED_DECLINE.fullmatch(out.strip()):
        return "Hm. Ya sudah."
    for rx, repl in _LEADING:
        out = rx.sub(repl, out, count=1)
    for rx, repl in _REPLACEMENTS:
        if technical and rx.pattern in {r"\bhal tersebut\b", r"\bhal ini\b"}:
            continue
        out = rx.sub(repl, out)
    if profile == "IDENTITY":
        out = _IDENTITY_AMBIGUOUS_OPEN.sub("", out, count=1)
    out = _strip_generic_tails(out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([,.!?;:])", r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    if out.count("—") >= 3:
        out = out.replace(" — ", ", ")
    return out.strip()


def naturalize(
    text: str,
    *,
    technical: bool = False,
    profile: str = "",
    user_text: str = "",
) -> str:
    """Cheap deterministic guard against recurring assistant-like phrasing.

    It never invokes a second model. Code fences are preserved. Length caps only
    apply to conversational response profiles where long output itself is a
    failure mode.
    """
    raw = str(text or "")
    if not raw.strip():
        return raw

    parts = re.split(r"(```[\s\S]*?```)", raw)
    cleaned: list[str] = []
    has_code = False
    for part in parts:
        if part.startswith("```"):
            has_code = True
            cleaned.append(part)
        else:
            cleaned.append(_clean_segment(part, technical=technical, profile=profile))
    out = "".join(cleaned).strip() or raw.strip()

    if not technical and not has_code:
        if profile == "REFLEX":
            out = _sentence_cap(out, max_sentences=2, max_chars=220)
        elif profile == "IDENTITY":
            out = _sentence_cap(out, max_sentences=4, max_chars=560)
        elif profile == "CASUAL":
            out = _sentence_cap(out, max_sentences=6, max_chars=900)
        elif profile == "CLOSE":
            out = _sentence_cap(out, max_sentences=8, max_chars=1300)

    return out.strip() or raw.strip()
