from __future__ import annotations

import json
from dataclasses import dataclass

from .agent import AndroidAgent
from .bridge import AndroidBridge
from .chat import FurinaChat
from .config import Config
from .memory import MemoryStore
from .persona import build_system_prompt


@dataclass
class Intent:
    mode: str
    goal: str
    confidence: float = 0.0


class CompanionSession:
    """Natural-language entry point for both conversation and Android tasks."""

    def __init__(self, cfg: Config, store: MemoryStore, llm):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.chat = FurinaChat(cfg, store, llm)
        self.bridge = AndroidBridge(cfg)
        self.agent = AndroidAgent(cfg, store, llm, self.bridge)

    def classify(self, text: str) -> Intent:
        prompt = f"""
Klasifikasikan maksud pesan pengguna ke salah satu mode:
- chat: percakapan, pertanyaan, ide, penjelasan, menulis, atau permintaan yang tidak perlu menyentuh UI Android.
- device: pengguna ingin Furina melakukan sesuatu pada HP/aplikasi: membuka app, mencari sesuatu di app, membaca isi app/catatan, navigasi, mengetik, memilih kontrol, atau mengirim pesan.

Pahami typo, singkatan, bahasa campuran, dan kalimat sangat pendek. Jangan bergantung pada keyword/template literal.
Jika pesan meminta tindakan Android sekaligus percakapan, pilih device dan pertahankan tujuan lengkap.

Pesan pengguna:
{text}

Output JSON tunggal tanpa markdown:
{{"mode":"chat|device","goal":"tujuan pengguna yang dipertahankan tanpa menambah maksud baru","confidence":0.0}}
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname) + "\n\nKamu sedang melakukan routing intent; output hanya JSON."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=120,
                temperature=0.05,
            )
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                return Intent("chat", text, 0.0)
            obj = json.loads(raw[start : end + 1])
            mode = str(obj.get("mode", "chat")).lower()
            if mode not in {"chat", "device"}:
                mode = "chat"
            goal = str(obj.get("goal") or text).strip() or text
            try:
                confidence = float(obj.get("confidence", 0.5))
            except Exception:
                confidence = 0.5
            return Intent(mode, goal, max(0.0, min(1.0, confidence)))
        except Exception:
            # A router failure should never destroy ordinary chat.
            return Intent("chat", text, 0.0)

    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:
        intent = self.classify(text)
        if intent.mode == "device":
            result = self.agent.run(intent.goal, approve, task_authorized=task_authorized)
            return result, "device"
        return self.chat.respond(text), "chat"
