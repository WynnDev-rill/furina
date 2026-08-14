#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


INTENT_GUARD = r'''from __future__ import annotations

import re
from difflib import SequenceMatcher

_NEGATION = re.compile(
    r"\b(?:jangan|jgn|tidak\s+usah|tak\s+usah|gak\s+usah|nggak\s+usah|ga\s+usah|dont|don't|do\s+not)\b",
    re.I,
)
_DISCUSSION_PREFIX = re.compile(
    r"^\s*(?:menurut(?:mu|\s+kamu)?|kenapa|mengapa|bagaimana\s+cara|gimana\s+cara|apa\s+yang\s+terjadi|"
    r"kalau|jika|misalnya|contoh(?:nya)?|anggap|bayangkan|seandainya|tadi\b|kemarin\b|barusan\b|"
    r"aku\s+tadi\b|saya\s+tadi\b|aku\s+pernah\b|saya\s+pernah\b|ceritakan|jelaskan|bahas)\b",
    re.I,
)
_META_PHRASE = re.compile(
    r"\b(?:artinya\s+apa|maksudnya\s+apa|menurutmu|menurut\s+kamu|apa\s+pendapatmu|"
    r"apa\s+yang\s+akan\s+terjadi|what\s+happens|what\s+would\s+happen|why\b|kenapa\b|mengapa\b)\b",
    re.I,
)
_REQUEST_PREFIX = re.compile(
    r"^\s*(?:tolong|coba|mohon|please|bisa(?:kah)?|boleh(?:kah)?|dapatkah|can\s+you|could\s+you|would\s+you)\b",
    re.I,
)
_ACTION_WORDS = (
    "buka", "bukain", "bukakan", "open", "jalankan", "launch",
    "cari", "carikan", "search", "find", "ketik", "ketikkan", "tulis", "tuliskan", "isi", "isikan",
    "tekan", "klik", "click", "tap", "scroll", "geser", "swipe", "pilih", "select",
    "kirim", "send", "balas", "reply", "hapus", "delete", "remove", "uninstall", "install",
    "aktifkan", "matikan", "nyalakan", "putar", "play", "pause", "download", "unduh", "upload", "unggah",
    "atur", "set", "kembali", "back", "home", "recents",
)
_ACTION_RE = re.compile(r"\b(?:" + "|".join(re.escape(x) for x in _ACTION_WORDS) + r")\b", re.I)


def _clean(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def _request_shaped(text: str) -> bool:
    clean = _clean(text)
    return bool(_REQUEST_PREFIX.search(clean) and _ACTION_RE.search(clean))


def conversation_frame(text: str) -> bool:
    """True when text is clearly talking *about* an action, not requesting it."""
    clean = _clean(text)
    if not clean:
        return False
    if _NEGATION.search(clean):
        return True
    if _request_shaped(clean):
        return False
    if _DISCUSSION_PREFIX.search(clean) or _META_PHRASE.search(clean):
        return True
    # Bare questions are chat-first unless shaped as an actual request.
    if "?" in clean:
        return True
    return False


def strong_device_request(text: str) -> bool:
    """Conservative deterministic fallback. Semantic routing remains primary."""
    clean = _clean(text)
    if not clean or conversation_frame(clean):
        return False
    if _REQUEST_PREFIX.search(clean) and _ACTION_RE.search(clean):
        return True
    # Direct imperative: an action token must appear at the beginning.
    return bool(re.match(r"^\s*(?:" + "|".join(re.escape(x) for x in _ACTION_WORDS) + r")\b", clean, re.I))


def valid_action_span(text: str, span: str) -> bool:
    source = _clean(text)
    candidate = _clean(span).strip(" .,!?:;\"'`“”‘’")
    if len(candidate) < 3 or candidate not in source:
        return False
    tokens = re.findall(r"[\w-]+", candidate, flags=re.UNICODE)
    for token in tokens:
        low = token.casefold()
        if low in _ACTION_WORDS:
            return True
        if len(low) >= 4:
            if max(SequenceMatcher(None, low, word).ratio() for word in _ACTION_WORDS) >= 0.78:
                return True
    return False


def committed_device_intent(text: str, obj: dict, steps: list[dict], confidence: float) -> bool:
    """Independent post-parser gate before anything may reach AndroidAgent."""
    if conversation_frame(text):
        return False
    if not steps and not strong_device_request(text):
        return False
    speech_act = str(obj.get("speech_act") or "").strip().lower()
    explicit = obj.get("explicit_device_action") is True
    span = str(obj.get("action_span") or "")

    # RC34 parser contract: device requires an explicit command/request plus
    # an exact user-text action span. This stops app-name mentions from becoming authority.
    if speech_act in {"command", "request"} and explicit and confidence >= 0.55:
        return valid_action_span(text, span)

    # Compatibility fallback if a backend omitted the new metadata. Keep it
    # intentionally stricter than the primary path.
    return bool(not speech_act and confidence >= 0.80 and strong_device_request(text))
'''


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC34 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC34 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    companion = core / "companion.py"
    direct = core / "direct_control.py"
    version = core / "version.py"
    for path in (companion, direct, version):
        if not path.is_file():
            raise SystemExit(f"missing RC34 source: {path}")

    (core / "intent_guard.py").write_text(INTENT_GUARD, encoding="utf-8")

    c = companion.read_text(encoding="utf-8")
    if "from .intent_guard import committed_device_intent, conversation_frame, strong_device_request\n" not in c:
        c = rep(
            c,
            "from .direct_control import DirectDeviceControl, DirectResult\n",
            "from .direct_control import DirectDeviceControl, DirectResult\nfrom .intent_guard import committed_device_intent, conversation_frame, strong_device_request\n",
            "companion intent guard import",
        )

    classify = r'''    def classify(self, text: str) -> Intent:
        text = text.strip()
        if not text:
            return Intent("chat", text, 1.0)

        # Clear discussion/report/hypothetical frames are chat before any app
        # inventory or LLM output gets a chance to widen them into device work.
        if conversation_frame(text):
            self.store.log_event("intent_chat_frame", {"text": text[:240]})
            return Intent("chat", text, 1.0, [], False)

        apps = self._installed_apps()
        anchors = self._app_anchors(text, apps)
        fallback_steps = self._fallback_device_steps(text, apps) if strong_device_request(text) else []
        app_context = [
            {"label": str(x.get("label") or "")[:80], "package": str(x.get("package") or "")[:180]}
            for x in apps[:220]
        ]
        routed_text = router_view(text)
        prompt = f"""
Pahami maksud pesan pengguna secara semantik. Default ke CHAT jika ada ambiguitas.
Nama aplikasi hanya konteks/target; menyebut aplikasi TIDAK berarti meminta perangkat bertindak.

Pesan pengguna:
{routed_text}

Aplikasi terpasang:
{json.dumps(app_context, ensure_ascii=False)[:12000]}

Output JSON tunggal:
{{
  "mode":"chat|device",
  "speech_act":"command|request|question|discussion|report|hypothetical|quote",
  "explicit_device_action":false,
  "action_span":"kutipan PERSIS dari pesan user yang meminta aksi; kosong jika chat",
  "goal":"maksud lengkap pengguna",
  "confidence":0.0,
  "steps":[
    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","field_role":"search|message|input","direction":"forward|backward"}}
  ]
}}

Aturan penting:
- device HANYA bila user benar-benar meminta Furina melakukan tindakan Android sekarang.
- Percakapan tentang aplikasi, laporan masa lalu, pertanyaan penjelasan, hipotesis, contoh, kutipan perintah, dan keluhan adalah chat.
- "WhatsApp lagi lambat menurutmu kenapa?" = chat.
- "Tadi aku buka WhatsApp lalu chat Ariel" = chat/report.
- "Kalau aku bilang 'buka WhatsApp', kamu bakal apa?" = chat/hypothetical.
- "Jangan buka WhatsApp" = chat; tidak ada aksi.
- "Bisa buka WhatsApp?" = device/request.
- "Tolong bukain WhatsApp" = device/request.
- action_span harus merupakan substring persis dari pesan user dan memuat kata aksi yang diminta.
- Untuk mode chat: explicit_device_action=false, action_span="", steps=[].
- Untuk mode device: speech_act harus command/request dan explicit_device_action=true.
- Pertahankan semua sub-tugas device. Pisahkan type dan send. Jangan menambah aksi.
""".strip()

        errors: list[str] = []
        for json_mode in (True, False):
            try:
                raw = self.llm.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Kamu intent classifier Android konservatif. App mention bukan permission. "
                                "Jika ragu, pilih chat. Output satu objek JSON valid saja."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=620,
                    temperature=0.0,
                    json_mode=json_mode,
                    role="intent",
                )
                obj = _first_json_object(raw)
                if not isinstance(obj, dict):
                    raise ValueError("semantic parser tidak menghasilkan objek JSON")
                mode = str(obj.get("mode") or "").strip().lower()
                if mode not in {"chat", "device"}:
                    raise ValueError(f"mode semantic tidak valid: {mode!r}")
                try:
                    confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.5) or 0.5)))
                except Exception:
                    confidence = 0.5

                if mode == "chat":
                    # Structural override is allowed only for a very explicit
                    # imperative and only when the parser itself is uncertain.
                    if fallback_steps and confidence < 0.35:
                        self.store.log_event(
                            "semantic_chat_overridden_by_explicit_request",
                            {"text": text[:240], "steps": len(fallback_steps), "confidence": confidence},
                        )
                        return Intent("device", text, 0.72, fallback_steps, self._requires_screen(fallback_steps))
                    goal = str(obj.get("goal") or text).strip() or text
                    return Intent("chat", goal, confidence, [], False)

                steps = self._normalize_semantic_steps(obj.get("steps"), apps)
                if not committed_device_intent(text, obj, steps, confidence):
                    self.store.log_event(
                        "semantic_device_rejected",
                        {
                            "text": text[:240],
                            "confidence": confidence,
                            "speech_act": str(obj.get("speech_act") or "")[:40],
                            "explicit": obj.get("explicit_device_action") is True,
                            "anchors": anchors[:4],
                        },
                    )
                    return Intent("chat", text, confidence, [], False)

                if any(str(step.get("type") or "") == "unknown" for step in steps):
                    self.store.log_event(
                        "semantic_intent_deferred_to_planner",
                        {"text": text[:240], "steps": len(steps)},
                    )
                    steps = []
                return Intent("device", text, confidence, steps, True if not steps else self._requires_screen(steps))
            except Exception as exc:
                errors.append(f"{'json' if json_mode else 'plain'}:{str(exc)[:220]}")

        # Provider/parser failure is chat-first. Only a structurally explicit
        # request may recover into device mode; an app-name anchor alone never can.
        if fallback_steps:
            self.store.log_event(
                "semantic_intent_structural_fallback",
                {"text": text[:240], "steps": len(fallback_steps), "errors": errors[-2:]},
            )
            return Intent("device", text, 0.72, fallback_steps, self._requires_screen(fallback_steps))

        if strong_device_request(text):
            self.store.log_event(
                "semantic_intent_unresolved_explicit_request",
                {"text": text[:240], "errors": errors[-2:]},
            )
            return Intent("device", text, 0.20, [], True)

        self.store.log_event(
            "semantic_intent_error_chat_fallback",
            {"text": text[:240], "anchors": anchors[:4], "errors": errors[-2:]},
        )
        return Intent("chat", text, 0.0, [], False)
'''
    c = block(c, "    def classify(self, text: str) -> Intent:\n", "    def try_direct_intent(self, intent: Intent) -> DirectResult:\n", classify, "companion classify")
    companion.write_text(c, encoding="utf-8")

    d = direct.read_text(encoding="utf-8")
    if "from .intent_guard import conversation_frame\n" not in d:
        d = rep(
            d,
            "from .prospective import extract_prospectives\n",
            "from .prospective import extract_prospectives\nfrom .intent_guard import conversation_frame\n",
            "direct intent guard import",
        )
    d = rep(
        d,
        '''        raw = " ".join(str(text or "").split())
        if not raw:
            return DirectResult(False)

        # Android Bridge owns scheduling. No Termux daemon is required after
''',
        '''        raw = " ".join(str(text or "").split())
        if not raw:
            return DirectResult(False)
        if conversation_frame(raw):
            self.store.log_event("direct_control_chat_guard", {"text": raw[:240]})
            return DirectResult(False)

        # Android Bridge owns scheduling. No Termux daemon is required after
''',
        "direct chat guard",
    )
    direct.write_text(d, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc33"', 'VERSION = "1.0.0-rc34"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (core / "intent_guard.py", companion, direct, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = [
        (companion, "semantic_device_rejected"),
        (companion, "semantic_intent_error_chat_fallback"),
        (companion, 'role="intent"'),
        (direct, "direct_control_chat_guard"),
        (version, 'VERSION = "1.0.0-rc34"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC34 incomplete: " + ", ".join(missing))
    if "semantic_intent_device_fallback" in companion.read_text(encoding="utf-8"):
        raise SystemExit("RC34 stale app-anchor fail-open masih aktif")
    print("Furina Core RC34 chat-first intent commitment gate: OK")


if __name__ == "__main__":
    main()
