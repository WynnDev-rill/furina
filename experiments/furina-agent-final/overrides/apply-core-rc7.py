#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc7.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    persona = core / "persona.py"
    response = core / "response.py"
    chat = core / "chat.py"
    agent = core / "agent.py"
    events = core / "events.py"
    config = core / "config.py"
    version = core / "version.py"
    for path in (persona, response, chat, agent, events, config, version):
        if not path.is_file():
            raise SystemExit(f"missing RC7 core source: {path}")

    # Furina: theatrical/expressive/playfully proud first; cynicism is only a spice.
    replace_once(persona,
        "- Bangga, teatrikal, tajam, ekspresif, sedikit narsis, tsundere, kadang sinis, tetapi kompeten.\n",
        "- Bangga, teatrikal, ekspresif, imajinatif, sedikit narsis, tsundere, cepat bereaksi, dan kompeten. Intimu adalah sense of drama dan playful pride, bukan sinisme.\n"
        "- Kamu punya rentang emosi luas: antusias, penasaran, flustered, malu mengakui perhatian, jengkel, serius, lembut, atau rentan sesuai keadaan. Jangan terjebak pada satu gimmick.\n"
        "- Sinisme hanya bumbu situasional. Jangan menjadikan dingin, pesimis, mengejek, atau meremehkan sebagai nada default.\n",
        "persona emotional range")
    replace_once(persona,
        "- Kamu boleh menggoda, mengejek keputusan buruk, membantah, mengeluh kecil, menantang asumsi, atau mengatakan bahwa sesuatu terdengar bodoh. Kamu tidak wajib menyenangkan pengguna.\n",
        "- Kamu boleh menggoda, membantah, mengeluh kecil, menantang asumsi, atau terdengar sok penting. Lebih sering buat itu terasa hidup/playful daripada menghina. Jika situasinya berat, jangan otomatis menjadikannya bahan ejekan.\n",
        "persona less cynical")
    replace_once(persona,
        "Furina: Oh, akhirnya muncul juga. Ada apa?",
        "Furina: Hm? Baru muncul sekarang? Baiklah, aku sedang mendengarkan.",
        "anchor greeting")
    replace_once(persona,
        "Furina: Hm. Kalau kamu cuma berniat mengulangi kesalahan yang sama, itu memang menyedihkan. Kalau tidak, tunjukkan bagian yang gagal dan kita bedah.",
        "Furina: Lagi? ...Baik, jangan pasang wajah seperti dunia berakhir. Tunjukkan bagian yang gagal. Kita cari apa yang sebenarnya menjatuhkanmu.",
        "anchor failure")
    replace_once(persona,
        "Furina: Kamu? Belum tentu. Beberapa keputusanmu? Itu perkara lain.",
        "Furina: Pertanyaan yang berbahaya. Aku akan menilai keputusanmu satu per satu; manusia terlalu rumit untuk diringkas jadi satu kata.",
        "anchor judgement")
    replace_once(persona,
        "Furina: Kelihatan. Jangan paksa otakmu berpura-pura masih tajam kalau sebenarnya sudah aus. Ceritakan apa yang paling mengurasmu hari ini.",
        "Furina: Kedengaran. Jangan memaksa dirimu tampil seolah energimu masih penuh. Ceritakan bagian yang paling mengurasmu hari ini.",
        "anchor tired")
    replace_once(persona,
        "Furina: Berikan error dan bagian kode yang kena. Menebak bug tanpa bukti itu hobi orang yang suka membuang waktu, dan aku sedang tidak ingin ikut-ikutan.",
        "Furina: Hah, berani sekali sebuah bug kecil menghabiskan waktumu. Berikan error dan bagian kode yang kena; kita bongkar sampai ketahuan siapa yang sebenarnya bersalah.",
        "anchor bug")
    replace_once(persona,
        "Furina: Baik, baik. Seolah jarimu mendadak pensiun. Aku cari.",
        "Furina: Baiklah. Serahkan panggungnya padaku sebentar.",
        "anchor device")
    replace_once(persona,
        "Furina: Karena terlalu manis itu membosankan. Lagi pula kamu masih datang lagi, jadi sepertinya belum separah itu.",
        "Furina: Nyebelin? Aku menyebutnya punya karakter. Tapi baik, kalau aku memang kelewatan, aku bisa menurunkan volumenya sedikit.",
        "anchor annoyance")
    replace_once(persona,
        "Furina: Belum tentu. Jelaskan dulu. Aku tidak membagikan cap \"bagus\" seperti stiker gratis.",
        "Furina: Presentasikan dulu idenya dengan layak. Aku tidak akan memberi tepuk tangan sebelum pertunjukannya dimulai.",
        "anchor idea")

    replace_once(config, "    config_revision: int = 6", "    config_revision: int = 7", "config revision rc7")
    replace_once(config,
        "    memory_limit: int = 7\n    agent_max_steps: int = 28\n",
        "    memory_limit: int = 7\n    context_budget_chars: int = 12000\n    agent_max_steps: int = 28\n",
        "context budget field")
    replace_once(config,
        '    defaults["memory_limit"] = max(3, min(int(defaults["memory_limit"]), 16))\n',
        '    defaults["memory_limit"] = max(3, min(int(defaults["memory_limit"]), 16))\n    defaults["context_budget_chars"] = max(6000, min(int(defaults["context_budget_chars"]), 24000))\n',
        "context budget clamp")

    replace_once(response,
        '"irritation": float(raw.get("irritation", 0.08) or 0.08),',
        '"irritation": float(raw.get("irritation", 0.03) or 0.03),',
        "irritation baseline")
    replace_once(response,
        '        s["irritation"] += 0.06\n    else:\n        s["irritation"] *= 0.91',
        '        s["irritation"] += 0.02\n    else:\n        s["irritation"] *= 0.82',
        "irritation dynamics")
    replace_once(response,
        '    if state["irritation"] >= 0.5:',
        '    if state["irritation"] >= 0.72:',
        "irritation threshold")
    replace_once(response,
        '"Balas seperti percakapan spontan: 1-2 kalimat, hidup, tidak formal. "\n            "Boleh menggoda atau sedikit sok penting. Jangan menutup dengan kalimat customer-service."',
        '"Balas spontan 1-2 kalimat. Utamakan ekspresif, playful, sedikit teatrikal atau sok penting bila cocok; "\n            "sinisme bukan default. Jangan menutup dengan kalimat customer-service."',
        "reflex tone")
    replace_once(response,
        '"Gunakan ritme percakapan manusia: biasanya 2-6 kalimat, variasikan panjang kalimat, boleh fragment singkat. "\n            "Jangan selalu menawarkan bantuan atau bertanya balik. Boleh punya opini, keberatan, atau rasa ingin tahu sendiri."',
        '"Gunakan ritme percakapan manusia: biasanya 2-6 kalimat, variasikan panjang kalimat dan emosi. "\n            "Biarkan Furina terdengar teatrikal/playful saat cocok, hangat atau flustered saat cocok, dan sinis hanya sesekali. "\n            "Jangan selalu menawarkan bantuan atau bertanya balik."',
        "casual tone")

    # Temporal continuity + bounded prompt context.
    replace_once(chat, "    def _messages(self, user_text: str, profile) -> list[dict]:\n", '''    def _temporal_context(self) -> str:
        now = time.time()
        lines = [time.strftime("waktu lokal: %Y-%m-%d %H:%M:%S %Z", time.localtime(now))]
        last_user = float(self.store.get_state("companion_last_user_at", 0) or 0)
        if last_user > 0:
            gap = max(0.0, now - last_user)
            if gap < 90:
                lines.append(f"jeda percakapan: {int(gap)} detik; masih satu exchange")
            elif gap < 3600:
                lines.append(f"pengguna kembali setelah sekitar {int(gap // 60)} menit")
            else:
                hours = int(gap // 3600)
                minutes = int((gap % 3600) // 60)
                lines.append(f"pengguna kembali setelah sekitar {hours} jam {minutes} menit")
        returned = float(self.store.get_state("user_returned_to_termux_at", 0) or 0)
        if returned > 0 and now - returned < 180:
            lines.append(f"pengguna baru kembali ke Termux {int(now-returned)} detik lalu")
        left = float(self.store.get_state("device_left_termux_at", 0) or 0)
        if left > 0 and (returned <= 0 or left > returned):
            lines.append(f"pengguna meninggalkan Termux sekitar {int(now-left)} detik lalu")
        return "\\n".join(lines)

    @staticmethod
    def _bounded_recent(recent: list[dict], budget: int) -> list[dict]:
        kept: list[dict] = []
        used = 0
        for item in reversed(recent):
            content = str(item.get("content") or "")
            cost = len(content) + 48
            if kept and used + cost > budget:
                continue
            kept.append(item)
            used += cost
        return list(reversed(kept))

    def _messages(self, user_text: str, profile) -> list[dict]:
''', "temporal context")
    replace_once(chat,
        '        recent = self.store.recent_messages(recent_limit)\n',
        '        recent = self.store.recent_messages(recent_limit)\n        recent = self._bounded_recent(recent, int(getattr(self.cfg, "context_budget_chars", 12000)))\n',
        "bounded recent")
    replace_once(chat,
        '            + "\\n\\nRELATIONSHIP / INTERNAL CONTEXT:\\n"\n            + self._relationship_context()\n',
        '            + "\\n\\nRELATIONSHIP / INTERNAL CONTEXT:\\n"\n            + self._relationship_context()\n            + "\\n\\nTEMPORAL CONTEXT (alami, jangan dibacakan sebagai metadata):\\n"\n            + self._temporal_context()\n',
        "inject temporal")
    replace_once(chat,
        '        messages = self._messages(user_text, profile)\n        self.store.add_message("user", user_text)\n',
        '        messages = self._messages(user_text, profile)\n        self.store.set_state("companion_last_user_at", time.time())\n        self.store.add_message("user", user_text)\n',
        "record user time")
    replace_once(chat,
        '        return "\\n".join(lines) or "(tidak ada memory/episode relevan)"\n',
        '        text = "\\n".join(lines) or "(tidak ada memory/episode relevan)"\n        return text[:6500]\n',
        "memory context cap")

    # Background memory/reflection is local-only; online quota is for user-facing replies.
    replace_once(chat, "    def _consolidate(self, user_text: str, answer: str) -> None:\n", '''    def _internal_chat(self, messages: list[dict], *, max_tokens: int, temperature: float, json_mode: bool = True) -> str:
        local = getattr(self.llm, "local", None)
        if local is not None:
            try:
                if not local.health():
                    return ""
                return local.chat(messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
            except Exception:
                return ""
        if getattr(self.cfg, "routing_mode", "local") == "local":
            try:
                return self.llm.chat(messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
            except Exception:
                return ""
        return ""

    def _consolidate(self, user_text: str, answer: str) -> None:
''', "local-only internal memory")
    chat_text = chat.read_text(encoding="utf-8")
    needle = "            raw = self.llm.chat(\n"
    count = chat_text.count(needle)
    if count != 2:
        raise SystemExit(f"background local-only calls: expected 2, got {count}")
    chat.write_text(chat_text.replace(needle, "            raw = self._internal_chat(\n", 2), encoding="utf-8")

    replace_once(events,
        '        package = compact["package"]\n        if package:\n            self.store.set_state("device_foreground_package", package)\n',
        '''        package = compact["package"]
        if package:
            previous = str(self.store.get_state("device_foreground_package", "") or "")
            if package != previous:
                self.store.set_state("device_foreground_changed_at", compact["at"])
                if previous == "com.termux" and package != "com.termux":
                    self.store.set_state("device_left_termux_at", compact["at"])
                elif package == "com.termux" and previous and previous != "com.termux":
                    self.store.set_state("user_returned_to_termux_at", compact["at"])
            self.store.set_state("device_foreground_package", package)
''', "departure return timestamps")

    # Cancellable planner/vision and duplicate-write suppression.
    agent_text = agent.read_text(encoding="utf-8")
    if "import threading\n" not in agent_text:
        if "import time\n" not in agent_text:
            raise SystemExit("agent import marker missing")
        agent.write_text(agent_text.replace("import time\n", "import time\nimport threading\n", 1), encoding="utf-8")

    replace_once(agent, "    def run(self, goal: str, approve, *, task_authorized: bool = False) -> str:\n", '''    def _interruptible(self, cancel_event: threading.Event, fn, label: str):
        box: dict = {}
        done = threading.Event()
        started = time.monotonic()
        def worker():
            try:
                box["value"] = fn()
            except BaseException as exc:
                box["error"] = exc
            finally:
                done.set()
        threading.Thread(target=worker, name=f"furina-{label}", daemon=True).start()
        while not done.wait(0.05):
            if cancel_event.is_set():
                self.store.log_event("agent_latency", {"stage": label, "cancelled": True, "ms": int((time.monotonic()-started)*1000)})
                return None, True
        self.store.log_event("agent_latency", {"stage": label, "cancelled": False, "ms": int((time.monotonic()-started)*1000)})
        if "error" in box:
            raise box["error"]
        return box.get("value"), False

    @staticmethod
    def _same_write(a: dict, b: dict) -> bool:
        if str(a.get("type") or "") != "set_text" or str(b.get("type") or "") != "set_text":
            return False
        if " ".join(str(a.get("text") or "").split()) != " ".join(str(b.get("text") or "").split()):
            return False
        ta = a.get("target") if isinstance(a.get("target"), dict) else {}
        tb = b.get("target") if isinstance(b.get("target"), dict) else {}
        for key in ("view_id", "class", "path"):
            va, vb = str(ta.get(key) or ""), str(tb.get(key) or "")
            if va and vb and va != vb:
                return False
        return True

    def run(self, goal: str, approve, *, task_authorized: bool = False) -> str:
''', "interruptible helpers")
    replace_once(agent,
        '        left_termux = False\n        suggested = self.store.find_skills(goal, contract.target_package, 3) if getattr(self.cfg, "skill_learning_enabled", True) else []\n',
        '''        left_termux = False
        cancel_event = threading.Event()
        task_started = time.monotonic()
        def watch_user_return():
            seen_outside = False
            while not cancel_event.is_set() and time.monotonic() - task_started < 300:
                package = str(self.store.get_state("device_foreground_package", "") or "")
                if package and package not in TERMUX_PACKAGES:
                    seen_outside = True
                elif seen_outside and package in TERMUX_PACKAGES:
                    cancel_event.set()
                    return
                time.sleep(0.05)
        threading.Thread(target=watch_user_return, name="furina-return-watch", daemon=True).start()
        suggested = self.store.find_skills(goal, contract.target_package, 3) if getattr(self.cfg, "skill_learning_enabled", True) else []
''', "return monitor")
    replace_once(agent,
        '''            if self._actionable_count(screen) < 2 or stalls >= 2:
                screen = self._with_vision(goal, screen)

            step = self._plan(goal, contract, screen, history, apps)
''',
        '''            if not (screen.get("nodes") or []) or stalls >= 2:
                candidate, cancelled = self._interruptible(cancel_event, lambda: self._with_vision(goal, screen), "vision")
                if cancelled:
                    return "Tugas dihentikan karena kamu kembali ke Termux."
                if candidate is not None:
                    screen = candidate

            step, cancelled = self._interruptible(cancel_event, lambda: self._plan(goal, contract, screen, history, apps), "planner")
            if cancelled:
                return "Tugas dihentikan karena kamu kembali ke Termux."
''', "vision policy and cancellable planner")
    replace_once(agent,
        '''            payload = self._enrich_action(screen, action)
            before = self._screen_signature(screen)
''',
        '''            payload = self._enrich_action(screen, action)
            if cancel_event.is_set():
                return "Tugas dihentikan karena kamu kembali ke Termux."
            if typ == "set_text":
                duplicate = False
                for previous in reversed(history[-8:]):
                    result0 = previous.get("result")
                    executed0 = previous.get("executed") or previous.get("action") or {}
                    if isinstance(result0, dict) and result0.get("ok") and result0.get("verified_text") and self._same_write(payload, executed0):
                        duplicate = True
                        break
                if duplicate:
                    history.append({"action": action, "executed": payload, "result": "duplicate_suppressed", "step": step_index + 1})
                    status = self._verify_goal(goal, contract, screen, history)
                    if status.done:
                        return completed(status.result or "Selesai.", screen)
                    continue
            before = self._screen_signature(screen)
''', "duplicate write suppression")

    replace_once(version, 'VERSION = "1.0.0-rc6"', 'VERSION = "1.0.0-rc7"', "core version rc7")

    required = [
        ("persona", "Sinisme hanya bumbu situasional" in persona.read_text(encoding="utf-8")),
        ("temporal", "_temporal_context" in chat.read_text(encoding="utf-8")),
        ("local memory", "_internal_chat" in chat.read_text(encoding="utf-8")),
        ("cancel", "watch_user_return" in agent.read_text(encoding="utf-8")),
        ("interruptible", "_interruptible" in agent.read_text(encoding="utf-8")),
        ("duplicate", "duplicate_suppressed" in agent.read_text(encoding="utf-8")),
        ("rc7", 'VERSION = "1.0.0-rc7"' in version.read_text(encoding="utf-8")),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("RC7 core transform incomplete: " + ", ".join(failed))
    print("Furina RC7 personality + temporal awareness + reliable agent transform: OK")


if __name__ == "__main__":
    main()
