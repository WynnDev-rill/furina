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
    version_path = core / "version.py"
    if not hub_path.is_file() or not version_path.is_file():
        raise SystemExit("RC44 source Core tidak lengkap")

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
        '''            result = self.session.agent.run(
                goal,
                self._approval_callback(job_id),
                task_authorized=True,
            )
            with self.job_lock:
                job = self.jobs[job_id]
                job["answer"] = str(result or "")
''',
        '''            result = self.session.agent.run(
                goal,
                self._approval_callback(job_id),
                task_authorized=True,
            )
            answer = str(result or "")
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
    version_path.write_text(
        version.replace('VERSION = "1.0.0-rc43"', 'VERSION = "1.0.0-rc44"', 1),
        encoding="utf-8",
    )

    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    joined = version_path.read_text(encoding="utf-8") + "\n" + hub_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc44"',
        '"bridge_target": "1.0.0-rc28"',
        'file unduhan bukan GGUF yang valid',
        'all_actions = self._connector_action_items',
        'active_jobs = [',
        'self.store.add_message("user", text)',
    )
    missing = [marker for marker in required if marker not in joined]
    if missing:
        raise SystemExit(f"RC44 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC44_OK")


if __name__ == "__main__":
    main()
