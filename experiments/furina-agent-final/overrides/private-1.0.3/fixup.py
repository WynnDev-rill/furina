#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/companion.py"


def replace_method(text: str, class_name: str, name: str, replacement: str) -> str:
    tree=ast.parse(text)
    cls=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name),None)
    if cls is None: raise SystemExit(f"missing class {class_name}")
    nodes=[n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    if len(nodes)!=1: raise SystemExit(f"{class_name}.{name}: expected one method, got {len(nodes)}")
    node=nodes[0]; start_line=min([node.lineno]+[d.lineno for d in node.decorator_list]); lines=text.splitlines(keepends=True)
    start=sum(len(x) for x in lines[:start_line-1]); end=sum(len(x) for x in lines[:node.end_lineno])
    return text[:start]+replacement.rstrip()+"\n"+text[end:]

text=PATH.read_text(encoding="utf-8")
if "import re" not in text:
    text=text.replace("import json\n", "import json\nimport re\n", 1)
text=replace_method(text,"CompanionSession","classify",r'''    def classify(self, text: str) -> Intent:
        clean = " ".join(str(text or "").strip().split())
        if not clean:
            return Intent("chat", clean, 0.99)

        verbs = re.compile(r"\b(buka|open|jalankan|launch|cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|putar|play|pause|tutup|close|panggil|call|pilih|select|aktifkan|matikan)\b", re.I)
        secondary = re.compile(r"\b(cari|search|kirim|send|balas|reply|ketik|tulis|tekan|tap|klik|click|scroll|geser|swipe|putar|play|pause|pilih|select|panggil|call)\b", re.I)
        targets = re.compile(r"\b(youtube|whatsapp|wa|telegram|instagram|tiktok|chrome|browser|gmail|maps|spotify|kamera|camera|galeri|gallery|notes?|catatan|kontak|contact|pesan|message|aplikasi|app|hp|ponsel|phone|layar|screen|settings?|pengaturan)\b", re.I)
        explanation = re.compile(r"^\s*(cara|bagaimana|gimana|kenapa|mengapa|jelaskan|apa itu)\b", re.I)
        open_prefix = re.compile(r"^\s*(buka|open|jalankan|launch)\b", re.I)

        # Deterministic device fast path; no model round-trip needed.
        if not explanation.search(clean):
            if verbs.search(clean) and targets.search(clean):
                return Intent("device", clean, 0.99)
            if open_prefix.search(clean) and len(clean) <= 240:
                return Intent("device", clean, 0.99)
            if len(secondary.findall(clean)) >= 2:
                return Intent("device", clean, 0.96)
        else:
            return Intent("chat", clean, 0.99)

        # LOCAL_FAST_CHAT_ROUTER: ordinary prose/greetings/questions never call
        # the local LLM merely to decide that they are chat.
        device_hint = bool(
            verbs.search(clean)
            or targets.search(clean)
            or re.search(r"\b(tolong|coba|cek|lihat|baca|akses|gunakan|pakai)\b", clean, re.I)
        )
        if not device_hint:
            return Intent("chat", clean, 0.98)

        prompt = f"Tentukan apakah pesan ini meminta tindakan nyata pada HP/aplikasi atau hanya percakapan.\nPesan: {clean[:500]}\nOutput JSON saja: {{\"mode\":\"chat|device\",\"goal\":\"tujuan singkat\",\"confidence\":0.0}}"
        try:
            raw = self.llm.chat(
                [
                    {"role":"system","content":"Router intent internal. device hanya jika perlu menyentuh UI Android. Output JSON valid saja."},
                    {"role":"user","content":prompt},
                ],
                max_tokens=80,
                temperature=0.0,
                json_mode=True,
            )
            obj = _first_json_object(raw)
            if not obj:
                return Intent("chat", clean, 0.0)
            mode = str(obj.get("mode", "chat")).lower()
            if mode not in {"chat", "device"}: mode = "chat"
            goal = str(obj.get("goal") or clean).strip() or clean
            try: confidence = float(obj.get("confidence", 0.5))
            except Exception: confidence = 0.5
            return Intent(mode, goal, max(0.0, min(1.0, confidence)))
        except Exception:
            return Intent("chat", clean, 0.0)''')
PATH.write_text(text,encoding="utf-8")
compile(text,str(PATH),"exec")
print("FURINA_PRIVATE_1_0_3_INTENT_FIXUP_OK")
