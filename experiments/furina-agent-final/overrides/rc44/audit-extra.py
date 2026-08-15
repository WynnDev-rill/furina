#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC44 audit marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: audit-extra.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    version = (core / "version.py").read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc44"' not in version:
        raise SystemExit("RC44 audit extra memerlukan Core RC44")

    hub_path = core / "hub.py"
    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(
        hub,
        '''                    "goal": intent.goal,
                    "original": text,
                    "status": "task_approval_required",
''',
        '''                    "goal": intent.goal,
                    "original": text,
                    "steps": list(intent.steps or [])[:18],
                    "status": "task_approval_required",
''',
        "preserve semantic steps",
    )
    hub = replace_once(
        hub,
        '''                goal = str(job["goal"])
                job["status"] = "running"
''',
        '''                goal = str(job["goal"])
                semantic_steps = list(job.get("steps") or [])[:18]
                job["status"] = "running"
''',
        "load semantic steps",
    )
    hub = replace_once(
        hub,
        '''                self._approval_callback(job_id),
                task_authorized=True,
            )
            answer = str(result or "")
''',
        '''                self._approval_callback(job_id),
                task_authorized=True,
                semantic_steps=semantic_steps,
            )
            answer = str(result or "")
''',
        "pass semantic steps",
    )
    hub = replace_once(
        hub,
        '''    @staticmethod
    def _json_object(raw: str) -> dict:
        text = str(raw or "").strip()
        match = re.search(r"\\{.*\\}", text, re.S)
        if not match:
            raise ValueError("model tidak menghasilkan rencana plugin yang valid")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("rencana plugin tidak valid")
        return value
''',
        '''    @staticmethod
    def _json_object(raw: str) -> dict:
        text = str(raw or "")
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise ValueError("model tidak menghasilkan rencana plugin yang valid")
''',
        "plugin JSON parser",
    )
    hub_path.write_text(hub, encoding="utf-8")

    routing_path = core / "routing.py"
    routing = routing_path.read_text(encoding="utf-8")
    routing = replace_once(routing, "import re\nimport subprocess\n", "import re\nimport shutil\nimport subprocess\n", "routing shutil import")
    routing = replace_once(
        routing,
        '''        launcher = HOME / "bin" / "furina"
        if not launcher.exists():
            return False
        try:
            subprocess.run(
                [str(launcher), "start"],
''',
        '''        launcher = shutil.which("furina")
        if not launcher:
            bundled = HOME / "bin" / "furina"
            launcher = str(bundled) if bundled.exists() else ""
        if not launcher:
            return False
        try:
            subprocess.run(
                [launcher, "start"],
''',
        "local launcher discovery",
    )
    routing = replace_once(
        routing,
        '''        if self.cfg.routing_mode == "local":
            answer = self.local.chat(
''',
        '''        if self.cfg.routing_mode == "local":
            if not self._ensure_local():
                raise LLMError("Model lokal belum aktif atau tidak dapat dimulai.")
            answer = self.local.chat(
''',
        "local mode autostart",
    )
    routing_path.write_text(routing, encoding="utf-8")

    direct_path = core / "direct_control.py"
    direct = direct_path.read_text(encoding="utf-8")
    direct = replace_once(
        direct,
        '_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout)\\b", re.I)',
        '_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout|call|dial|telepon|install|pasang|izinkan|allow|permission|grant|revoke|confirm|konfirmasi|accept|setujui|aktifkan|nonaktifkan|enable|disable|record|rekam)\\b", re.I)',
        "direct sensitive actions",
    )
    direct_path.write_text(direct, encoding="utf-8")

    memory_path = core / "memory.py"
    memory = memory_path.read_text(encoding="utf-8")
    memory = replace_once(
        memory,
        '''    def delete_conversation(self, conversation_id: int) -> int:
        value = int(conversation_id)
        rows = int(self._conn().execute("SELECT count(*) FROM conversations").fetchone()[0])
        if rows <= 1:
            self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
            self._conn().execute("UPDATE conversations SET title='Percakapan baru',updated_at=? WHERE id=?", (time.time(), value))
            self._conn().commit()
            return value
        self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
        self._conn().execute("DELETE FROM conversations WHERE id=?", (value,))
        latest = self._conn().execute("SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1").fetchone()
        self._conn().commit()
        return self.switch_conversation(int(latest[0]))
''',
        '''    def delete_conversation(self, conversation_id: int) -> int:
        value = int(conversation_id)
        active = self.active_conversation_id()
        if not self._conn().execute("SELECT 1 FROM conversations WHERE id=?", (value,)).fetchone():
            raise ValueError("percakapan tidak ditemukan")
        rows = int(self._conn().execute("SELECT count(*) FROM conversations").fetchone()[0])
        if rows <= 1:
            self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
            self._conn().execute("UPDATE conversations SET title='Percakapan baru',updated_at=? WHERE id=?", (time.time(), value))
            self._conn().commit()
            return value
        self._conn().execute("DELETE FROM messages WHERE conversation_id=?", (value,))
        self._conn().execute("DELETE FROM conversations WHERE id=?", (value,))
        self._conn().commit()
        if value != active:
            return active
        latest = self._conn().execute("SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1").fetchone()
        return self.switch_conversation(int(latest[0]))
''',
        "delete inactive conversation",
    )
    memory_path.write_text(memory, encoding="utf-8")

    for path in (hub_path, routing_path, direct_path, memory_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in (hub_path, routing_path, direct_path, memory_path))
    for marker in (
        "semantic_steps=semantic_steps",
        "decoder.raw_decode",
        'shutil.which("furina")',
        "call|dial|telepon",
        "if value != active:",
    ):
        if marker not in combined:
            raise SystemExit(f"RC44 audit marker hilang: {marker}")
    print("FURINAHUB_CORE_RC44_AUDIT_EXTRA_OK")


if __name__ == "__main__":
    main()
