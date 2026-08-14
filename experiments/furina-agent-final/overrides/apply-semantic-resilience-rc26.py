#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC26 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC26 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-semantic-resilience-rc26.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    companion = core / "companion.py"
    agent = core / "agent.py"
    chat = core / "chat_surface.py"
    version = core / "version.py"
    for path in (companion, agent, chat, version):
        if not path.is_file():
            raise SystemExit(f"missing RC26 source: {path}")

    c = companion.read_text(encoding="utf-8")

    resolver = '''    @staticmethod
    def _app_keys(label: str, package: str = "") -> set[str]:
        raw = str(label or "").strip()
        parts: list[str] = []
        token = ""
        for ch in raw:
            if not ch.isalnum():
                if token:
                    parts.append(token)
                    token = ""
                continue
            if token and ch.isupper() and token[-1].islower():
                parts.append(token)
                token = ch
            else:
                token += ch
        if token:
            parts.append(token)

        normalized_parts = ["".join(ch.casefold() for ch in part if ch.isalnum()) for part in parts]
        normalized_parts = [part for part in normalized_parts if part]
        keys: set[str] = set(normalized_parts)
        if normalized_parts:
            keys.add("".join(normalized_parts))
            initials = "".join(part[0] for part in normalized_parts if part)
            if len(initials) >= 2:
                for size in range(2, min(4, len(initials)) + 1):
                    keys.add(initials[:size])
        package_tail = str(package or "").rsplit(".", 1)[-1]
        package_key = "".join(ch.casefold() for ch in package_tail if ch.isalnum())
        if package_key:
            keys.add(package_key)
        return {key for key in keys if key}

    @classmethod
    def _resolve_app_hint(cls, hint: str, apps: list[dict]) -> str:
        wanted = "".join(ch for ch in str(hint or "").casefold() if ch.isalnum())
        if not wanted:
            return ""
        best_score = 0.0
        best_package = ""
        tied = False
        for app in apps:
            package = str(app.get("package") or "")
            if not package:
                continue
            keys = cls._app_keys(str(app.get("label") or ""), package)
            if wanted in keys:
                score = 1.0
            elif len(wanted) <= 3:
                score = 0.0
            else:
                score = 0.0
                for key in keys:
                    if len(key) < 3:
                        continue
                    if wanted in key or key in wanted:
                        score = max(score, 0.90)
                    else:
                        score = max(score, SequenceMatcher(None, wanted, key).ratio())
            if score > best_score + 0.02:
                best_score, best_package, tied = score, package, False
            elif score > 0 and abs(score - best_score) <= 0.02 and package != best_package:
                tied = True
        threshold = 0.98 if len(wanted) <= 3 else 0.62
        return best_package if best_score >= threshold and not tied else ""

    @classmethod
    def _app_anchors(cls, text: str, apps: list[dict]) -> list[str]:
        tokens: list[str] = []
        current = ""
        for ch in str(text or "").casefold():
            if ch.isalnum():
                current += ch
            elif current:
                tokens.append(current)
                current = ""
        if current:
            tokens.append(current)
        token_set = set(tokens)
        compact = "".join(tokens)
        matches: list[str] = []
        for app in apps:
            package = str(app.get("package") or "")
            if not package:
                continue
            keys = cls._app_keys(str(app.get("label") or ""), package)
            found = False
            for key in keys:
                if len(key) <= 3:
                    found = key in token_set
                else:
                    found = key in token_set or key in compact
                if found:
                    break
            if found and package not in matches:
                matches.append(package)
        return matches
'''
    c = block(
        c,
        "    @staticmethod\n    def _resolve_app_hint(hint: str, apps: list[dict]) -> str:\n",
        "    @classmethod\n    def _normalize_semantic_steps",
        resolver,
        "generic app resolver",
    )

    classify = '''    def classify(self, text: str) -> Intent:
        text = text.strip()
        if not text:
            return Intent("chat", text, 1.0)
        apps = self._installed_apps()
        anchors = self._app_anchors(text, apps)
        app_context = [
            {"label": str(x.get("label") or "")[:80], "package": str(x.get("package") or "")[:180]}
            for x in apps[:220]
        ]
        routed_text = router_view(text)
        prompt = f"""
Pahami maksud pesan pengguna secara semantik. Jangan mengandalkan daftar frasa tetap.
Tentukan apakah pengguna sedang mengobrol atau meminta tindakan nyata pada perangkat Android, lalu pecah tindakan perangkat menjadi langkah konseptual berurutan.

Pesan pengguna (pertahankan seluruh maksud, termasuk typo, singkatan, bahasa kasual/campuran):
{routed_text}

Aplikasi terpasang:
{json.dumps(app_context, ensure_ascii=False)[:12000]}

Output JSON tunggal:
{{
  "mode":"chat|device",
  "goal":"maksud lengkap pengguna tanpa membuang sub-tugas",
  "confidence":0.0,
  "steps":[
    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","field_role":"search|message|input","direction":"forward|backward"}}
  ]
}}

Aturan:
- Pahami makna, bukan ejaan literal. Typo/singkatan tidak boleh mengubah perintah perangkat menjadi chat bila maksudnya jelas.
- Untuk mode device, pertahankan SEMUA sub-tugas dan urutannya.
- Untuk open_app, package hanya boleh berasal dari daftar aplikasi terpasang. Jika tidak yakin, isi app dan kosongkan package; resolver lokal akan mencocokkannya.
- search harus membuka UI pencarian, mengisi query, dan submit.
- Jika hasil pencarian perlu dibuka sebelum langkah berikutnya, tambahkan select sebelum type/tindakan lanjutan.
- type mengisi field pada konteks saat itu. Pesan/chat/reply/comment memakai field_role=message; form umum memakai input.
- send adalah aksi eksternal terakhir. Pisahkan type dan send; jangan menganggap mengetik berarti sudah terkirim.
- Jika satu langkah tidak dapat diwakili dengan pasti, gunakan unknown daripada menghapus sub-tugas tersebut.
- Jika pengguna hanya bertanya atau meminta penjelasan, mode=chat dan steps=[].
- Jangan menambah tindakan yang tidak diminta.
""".strip()

        errors: list[str] = []
        # Most providers support JSON mode, but internal routing must not depend
        # on it. Retry once without response_format if the first parse is unusable.
        for json_mode in (True, False):
            try:
                raw = self.llm.chat(
                    [
                        {"role": "system", "content": "Kamu semantic intent parser Android internal. Output satu objek JSON valid saja."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=560,
                    temperature=0.0,
                    json_mode=json_mode,
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
                    # Trust a confident semantic chat classification. If the
                    # parser itself is unsure while an installed app is clearly
                    # referenced, defer to the Android planner instead of
                    # silently converting an execution request into chat.
                    if confidence < 0.40 and anchors:
                        self.store.log_event(
                            "semantic_intent_low_confidence_device_fallback",
                            {"text": text[:240], "anchors": anchors[:4], "confidence": confidence},
                        )
                        return Intent("device", text, confidence, [], True)
                    goal = str(obj.get("goal") or text).strip() or text
                    return Intent("chat", goal, confidence, [], False)

                steps = self._normalize_semantic_steps(obj.get("steps"), apps)
                if any(str(step.get("type") or "") == "unknown" for step in steps):
                    # An unknown semantic step means the compact executor cannot
                    # prove the full plan. Keep the original goal and let the
                    # state-aware planner reason from the live UI instead.
                    self.store.log_event(
                        "semantic_intent_deferred_to_planner",
                        {"text": text[:240], "steps": len(steps)},
                    )
                    steps = []
                return Intent("device", text, confidence, steps, True if not steps else self._requires_screen(steps))
            except Exception as exc:
                errors.append(f"{'json' if json_mode else 'plain'}:{str(exc)[:220]}")

        # Never fail-open into ordinary chat merely because the parser/provider
        # had a transient problem. A reference to an actually installed app is
        # strong device context and is derived generically from labels/packages,
        # including camel-case acronyms such as WhatsApp -> WA or YouTube -> YT.
        if anchors:
            self.store.log_event(
                "semantic_intent_device_fallback",
                {"text": text[:240], "anchors": anchors[:4], "errors": errors[-2:]},
            )
            return Intent("device", text, 0.25, [], True)

        self.store.log_event("semantic_intent_error", {"text": text[:240], "errors": errors[-2:]})
        return Intent("chat", text, 0.0, [], False)
'''
    c = block(
        c,
        "    def classify(self, text: str) -> Intent:\n",
        "    def try_direct_intent(self, intent: Intent) -> DirectResult:\n",
        classify,
        "resilient semantic classify",
    )
    companion.write_text(c, encoding="utf-8")

    a = agent.read_text(encoding="utf-8")
    a = rep(
        a,
        '''        steps = self._compile_semantic_sequence(semantic_steps or [], apps)
        if not steps:
            steps = self._compile_ui_sequence(goal, contract, apps)
        if not steps:
            return None, None, False
''',
        '''        steps = self._compile_semantic_sequence(semantic_steps or [], apps)
        if not steps:
            # RC25 removed the legacy goal compiler when replacing the semantic
            # compiler block. Do not call a method that no longer exists. An
            # empty/unsupported semantic plan is a normal signal to continue
            # through the state-aware step-by-step planner below.
            self.store.log_event("semantic_sequence_deferred", {"goal": str(goal)[:240]})
            return None, None, False
''',
        "missing legacy compiler fallback",
    )
    agent.write_text(a, encoding="utf-8")

    ch = chat.read_text(encoding="utf-8")
    ch = rep(
        ch,
        '''        def _fail(self, widget_id: str) -> None:
            self._update_assistant(widget_id, "Aku tidak bisa menyelesaikan respons itu.")
            self._set_status("")
            self._set_busy(False)
''',
        '''        def _fail(self, widget_id: str) -> None:
            self._update_assistant(widget_id, "Terjadi masalah internal saat memproses tugas. Detail teknis sudah disimpan di log Furina.")
            self._set_status("")
            self._set_busy(False)
''',
        "actionable failure message",
    )
    chat.write_text(ch, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc25"', 'VERSION = "1.0.0-rc26"', "Core version")
    version.write_text(v, encoding="utf-8")

    for path in (companion, agent, chat, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    checks = [
        (companion, "def _app_anchors"),
        (companion, "semantic_intent_device_fallback"),
        (companion, "for json_mode in (True, False)"),
        (agent, "semantic_sequence_deferred"),
        (chat, "Detail teknis sudah disimpan di log Furina"),
        (version, 'VERSION = "1.0.0-rc26"'),
    ]
    missing = [needle for path, needle in checks if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC26 incomplete: " + ", ".join(missing))
    if "steps = self._compile_ui_sequence(goal, contract, apps)" in agent.read_text(encoding="utf-8"):
        raise SystemExit("RC26 stale legacy compiler call still present")
    print("Furina Core RC26 resilient semantic routing + planner fallback: OK")


if __name__ == "__main__":
    main()
