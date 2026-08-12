from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .agent import AndroidAgent
from .bridge import AndroidBridge
from .chat import FurinaChat
from .config import Config
from .memory import MemoryStore


_DEVICE_VERBS = re.compile(
    r"\b(buka|open|jalankan|launch|cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|putar|play|pause|tutup|close|panggil|call|pilih|select|aktifkan|matikan)\b",
    re.I,
)
_SECONDARY_DEVICE_VERBS = re.compile(
    r"\b(cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|putar|play|pause|pilih|select|panggil|call)\b",
    re.I,
)
_DEVICE_TARGETS = re.compile(
    r"\b(youtube|whatsapp|wa|telegram|instagram|tiktok|chrome|browser|gmail|maps|spotify|kamera|camera|galeri|gallery|notes?|catatan|kontak|contact|pesan|message|aplikasi|app|hp|ponsel|phone|layar|screen|settings?|pengaturan)\b",
    re.I,
)
_EXPLANATION_PREFIX = re.compile(r"^\s*(cara|bagaimana|gimana|kenapa|mengapa|jelaskan|apa itu)\b", re.I)
_OPEN_PREFIX = re.compile(r"^\s*(buka|open|jalankan|launch)\b", re.I)


@dataclass
class Intent:
    mode: str
    goal: str
    confidence: float = 0.0


def _obvious_device_intent(text: str) -> bool:
    """Fast path for explicit device commands, including arbitrary app names."""
    clean = " ".join(text.strip().split())
    if not clean or _EXPLANATION_PREFIX.search(clean):
        return False
    if _DEVICE_VERBS.search(clean) and _DEVICE_TARGETS.search(clean):
        return True
    # Any imperative that begins by opening an app/device target is treated as
    # an execution request even if the app name is unknown to our vocabulary.
    # This is what lets "buka Tokopedia lalu cari ..." route correctly.
    if _OPEN_PREFIX.search(clean) and len(clean) <= 240:
        return True
    # Commands such as "di Discord cari Wynn lalu kirim ..." may omit "buka".
    # Two independent interaction verbs are strong enough evidence of device intent.
    if len(_SECONDARY_DEVICE_VERBS.findall(clean)) >= 2:
        return True
    return False


def _first_json_object(raw: str) -> dict | None:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(str(raw or "")):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(str(raw)[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


class CompanionSession:
    """One natural-language entry point for conversation and Android actions."""

    def __init__(self, cfg: Config, store: MemoryStore, llm):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.chat = FurinaChat(cfg, store, llm)
        self.bridge = AndroidBridge(cfg)
        self.agent = AndroidAgent(cfg, store, llm, self.bridge)

    def classify(self, text: str) -> Intent:
        text = text.strip()
        if _obvious_device_intent(text):
            return Intent("device", text, 0.99)

        prompt = f"""
Klasifikasikan maksud pesan pengguna ke salah satu mode:
- chat: percakapan, pertanyaan, ide, penjelasan, menulis, atau permintaan yang tidak perlu menyentuh UI Android.
- device: pengguna ingin Furina benar-benar melakukan sesuatu pada HP/aplikasi apa pun: membuka app, mencari di app, membaca isi app, navigasi, mengetik, memilih kontrol, memutar media, atau mengirim pesan.

Pahami typo, singkatan, bahasa campuran, nama aplikasi yang belum pernah disebut, dan kalimat sangat pendek.
Jika pengguna hanya bertanya CARA melakukan sesuatu, pilih chat.
Jika pengguna memerintahkan tindakan nyata di suatu aplikasi, pilih device walaupun nama aplikasinya tidak ada di contoh mana pun.
Jika pengguna meminta tindakan Android sekaligus percakapan, pilih device dan pertahankan tujuan lengkap.

Pesan pengguna:
{text}

Output JSON tunggal:
{{"mode":"chat|device","goal":"tujuan pengguna tanpa menambah maksud baru","confidence":0.0}}
""".strip()
        try:
            raw = self.llm.chat(
                [
                    {
                        "role": "system",
                        "content": "Kamu router intent internal. Jangan roleplay, jangan menampilkan reasoning, dan keluarkan hanya JSON valid.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=160,
                temperature=0.0,
                json_mode=True,
            )
            obj = _first_json_object(raw)
            if not obj:
                return Intent("chat", text, 0.0)
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
            return Intent("chat", text, 0.0)

    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:
        intent = self.classify(text)
        if intent.mode == "device":
            result = self.agent.run(intent.goal, approve, task_authorized=task_authorized)
            return result, "device"
        return self.chat.respond(text), "chat"
