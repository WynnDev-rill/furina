#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC44 marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    hub_path = core / "hub.py"
    routing_path = core / "routing.py"
    direct_path = core / "direct_control.py"
    memory_path = core / "memory.py"
    version_path = core / "version.py"
    for path in (hub_path, routing_path, direct_path, memory_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC44 source Core tidak lengkap: {path.name}")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc44"' in version:
        print("FurinaHub Core RC44 already applied")
        return
    if 'VERSION = "1.0.0-rc43"' not in version:
        raise SystemExit("RC44 hanya dapat diterapkan dari Core RC43")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(
        hub,
        '''    @staticmethod
    def _connector_is_read_action(action_id: str) -> bool:
        verb = str(action_id).rsplit(".", 1)[-1].lower()
        return verb.startswith(("get", "list", "search", "read", "find", "query", "download", "fetch", "lookup"))
''',
        '''    @staticmethod
    def _connector_is_read_action(action_id: str) -> bool:
        raw = str(action_id).rsplit(".", 1)[-1]
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\\1_\\2", raw).lower()
        tokens = {item for item in re.split(r"[^a-z0-9]+", normalized) if item}
        mutating = {
            "add", "approve", "archive", "assign", "cancel", "commit", "create",
            "delete", "edit", "execute", "forward", "invite", "label", "merge",
            "modify", "move", "patch", "post", "publish", "push", "put", "reject",
            "remove", "rename", "reply", "revoke", "run", "send", "set", "share",
            "trash", "update", "upload", "write",
        }
        if tokens & mutating:
            return False
        return normalized.startswith(("get", "list", "search", "read", "find", "query", "download", "fetch", "lookup"))
''',
        "connector read/write classifier",
    )
    hub = replace_once(
        hub,
        '''        actions = [
            item for item in self.connector_actions().get("actions", [])
            if str(item.get("service") or item.get("provider") or item.get("id") or item.get("actionId") or "").split(".", 1)[0].lower() in allowed
        ][:40]
''',
        '''        all_actions = self._connector_action_items(self._connector_request("GET", "/v1/actions"))
        actions = [
            item for item in all_actions
            if isinstance(item, dict)
            and str(item.get("service") or item.get("provider") or item.get("id") or item.get("actionId") or "").split(".", 1)[0].lower() in allowed
        ][:40]
''',
        "plugin action filtering",
    )
    hub = replace_once(
        hub,
        '''            if received < 1024:
                raise RuntimeError("file unduhan kosong atau tidak valid")
            os.replace(part, target)
''',
        '''            if received < 1024:
                raise RuntimeError("file unduhan kosong atau tidak valid")
            with part.open("rb") as check:
                if check.read(4) != b"GGUF":
                    raise RuntimeError("file unduhan bukan GGUF yang valid")
            os.replace(part, target)
''',
        "GGUF validation",
    )
    hub = replace_once(
        hub,
        '''            job_id = secrets.token_hex(8)
            with self.job_lock:
''',
        '''            self.store.add_message("user", text)
            job_id = secrets.token_hex(8)
            with self.job_lock:
''',
        "persist device request",
    )
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
        "preserve semantic device steps",
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
        "load semantic device steps",
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
        "pass semantic device steps",
    )
    hub = replace_once(
        hub,
        '''            result = self.session.agent.run(
                goal,
                self._approval_callback(job_id),
                task_authorized=True,
                semantic_steps=semantic_steps,
            )
            answer = str(result or "")
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = str(result or "")
''',
        '''            result = self.session.agent.run(
                goal,
                self._approval_callback(job_id),
                task_authorized=True,
                semantic_steps=semantic_steps,
            )
            answer = str(result or "")
            self.store.add_message("assistant", answer or "Selesai.")
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = answer
''',
        "persist device result",
    ) if 'job["answer"] = str(result or "")' in hub else hub
    if 'self.store.add_message("assistant", answer or "Selesai.")' not in hub:
        hub = replace_once(
            hub,
            '''            answer = str(result or "")
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = answer
''',
            '''            answer = str(result or "")
            self.store.add_message("assistant", answer or "Selesai.")
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = answer
''',
            "persist device result",
        )
    hub = replace_once(
        hub,
        '''            history.append(item)
        return {
''',
        '''            history.append(item)
        with self.job_lock:
            active_jobs = [
                {k: v for k, v in job.items() if not k.startswith("_")}
                for job in sorted(self.jobs.values(), key=lambda item: float(item.get("updated_at") or 0))
                if job.get("status") not in {"done", "error", "cancelled"}
            ][-8:]
        return {
''',
        "bootstrap active jobs",
    )
    hub = replace_once(
        hub,
        '''            "conversations": self.store.list_conversations(),
            "settings": load_hub_settings(),
''',
        '''            "conversations": self.store.list_conversations(),
            "jobs": active_jobs,
            "settings": load_hub_settings(),
''',
        "bootstrap jobs field",
    )
    if hub.count('"bridge_target": "1.0.0-rc27"') != 2:
        raise SystemExit("RC44 bridge target marker berubah")
    hub = hub.replace('"bridge_target": "1.0.0-rc27"', '"bridge_target": "1.0.0-rc28"')
    hub_path.write_text(hub, encoding="utf-8")

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

    direct = direct_path.read_text(encoding="utf-8")
    direct = replace_once(
        direct,
        '_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout)\\b", re.I)',
        '_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout|call|dial|telepon|install|pasang|izinkan|allow|permission|grant|revoke|confirm|konfirmasi|accept|setujui|aktifkan|nonaktifkan|enable|disable|record|rekam)\\b", re.I)',
        "direct-control sensitive actions",
    )
    direct_path.write_text(direct, encoding="utf-8")

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

    version_path.write_text(version.replace('VERSION = "1.0.0-rc43"', 'VERSION = "1.0.0-rc44"', 1), encoding="utf-8")

    for path in (hub_path, routing_path, direct_path, memory_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    joined = "\n".join(path.read_text(encoding="utf-8") for path in (version_path, hub_path, routing_path, direct_path, memory_path))
    required = (
        'VERSION = "1.0.0-rc44"',
        '"bridge_target": "1.0.0-rc28"',
        'file unduhan bukan GGUF yang valid',
        'all_actions = self._connector_action_items',
        'active_jobs = [',
        'semantic_steps=semantic_steps',
        'shutil.which("furina")',
        'Model lokal belum aktif atau tidak dapat dimulai.',
        'call|dial|telepon',
        'if value != active:',
    )
    missing = [marker for marker in required if marker not in joined]
    if missing:
        raise SystemExit(f"RC44 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC44_OK")


if __name__ == "__main__":
    main()
