#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc60"
TARGET_REVISION = "2026.08.18-r30"
SUPPORTED = {"1.0.0-rc59", TARGET_VERSION}


def read_version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)', text)
    return m.group(1) if m else ""


def atomic(path: Path, content: str) -> None:
    temp = path.with_name(path.name + ".rc60.new")
    temp.write_text(content, encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def replace_method(text: str, start: str, end: str, replacement: str) -> str:
    a = text.find(start)
    b = text.find(end, max(0, a) + len(start))
    if a < 0 or b < 0 or b <= a:
        raise SystemExit(f"RC60 hub boundary mismatch: {start.strip()} -> {end.strip()}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    hub_path = core / "hub.py"
    version_path = core / "version.py"
    for path in (hub_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC60 required source missing: {path}")

    current = read_version(version_path)
    if current not in SUPPORTED:
        raise SystemExit(f"RC60 requires RC59 foundation, found {current or 'unknown'}")

    hub = hub_path.read_text(encoding="utf-8")
    if "EXPECTED_DEPENDENCY_REVISION =" not in hub:
        marker = 'UPDATE_STATUS_PATH = HOME / "run" / "furinahub-update.json"\n'
        if marker not in hub:
            raise SystemExit("RC60 update-status constant boundary missing")
        hub = hub.replace(
            marker,
            marker
            + f'EXPECTED_DEPENDENCY_REVISION = "{TARGET_REVISION}"\n'
            + 'UPDATE_STATUS_SCHEMA = 2\n',
            1,
        )
    else:
        hub = re.sub(
            r'EXPECTED_DEPENDENCY_REVISION\s*=\s*["\'][^"\']+["\']',
            f'EXPECTED_DEPENDENCY_REVISION = "{TARGET_REVISION}"',
            hub,
            count=1,
        )

    status_methods = r'''    def _disk_update_versions(self) -> tuple[str, str]:
        version_path = HOME / "core" / "furina_agent" / "version.py"
        revision_path = HOME / "data" / "dependency_revision"
        disk_version = ""
        try:
            raw = version_path.read_text(encoding="utf-8")
            match = re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)', raw)
            disk_version = match.group(1) if match else ""
        except Exception:
            pass
        try:
            revision = revision_path.read_text(encoding="utf-8").strip()
        except Exception:
            revision = ""
        return disk_version, revision

    def get_update_status(self) -> dict:
        with self.update_lock:
            memory_status = dict(self.update_status)
        file_status = {}
        try:
            loaded = json.loads(UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                file_status = loaded
        except Exception:
            pass
        status = file_status or memory_status
        disk_version, revision = self._disk_update_versions()
        status["schema"] = int(status.get("schema") or UPDATE_STATUS_SCHEMA)
        status["installed_core_version"] = disk_version or VERSION
        status["running_core_version"] = VERSION
        status["dependency_revision"] = revision
        target_version = str(status.get("target_version") or VERSION)
        target_revision = str(status.get("target_revision") or EXPECTED_DEPENDENCY_REVISION)
        status["target_version"] = target_version
        status["target_revision"] = target_revision
        status["restart_required"] = bool(disk_version and disk_version != VERSION)

        # Disk state is authoritative. A stale native/UI error must never survive
        # a successful update performed from the other entry point.
        installed_matches_target = bool(
            disk_version
            and disk_version == target_version
            and revision
            and revision == target_revision
        )
        if installed_matches_target and status.get("state") not in {"running", "starting"}:
            result = str(status.get("result") or "")
            if result not in {"updated", "no_update"}:
                result = "no_update" if target_version == VERSION else "updated"
            status["state"] = "done"
            status["result"] = result
            status["percent"] = 100
            if result == "updated":
                status["message"] = str(status.get("message") or f"Pembaruan berhasil. Core {target_version} · runtime {target_revision.rsplit('-', 1)[-1]} aktif.")
            else:
                status["message"] = f"Tidak ada pembaruan terbaru. Core {target_version} · runtime {target_revision.rsplit('-', 1)[-1]} sudah aktif."

        with self.update_lock:
            self.update_status = dict(status)
        return dict(status)
'''
    hub = replace_method(
        hub,
        "    def get_update_status(self) -> dict:\n",
        "    def get_model_status(self) -> dict:\n",
        status_methods + "\n    def get_model_status(self) -> dict:\n",
    )

    set_status = r'''    def _set_update_status(self, **values) -> None:
        with self.update_lock:
            self.update_status.update(values)
            self.update_status["schema"] = UPDATE_STATUS_SCHEMA
            self.update_status["updated_at"] = time.time()
            snapshot = dict(self.update_status)
        try:
            UPDATE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp = UPDATE_STATUS_PATH.with_name(UPDATE_STATUS_PATH.name + ".new")
            temp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            os.chmod(temp, 0o600)
            os.replace(temp, UPDATE_STATUS_PATH)
        except Exception:
            pass

    @staticmethod
'''
    hub = replace_method(
        hub,
        "    def _set_update_status(self, **values) -> None:\n",
        "    @staticmethod\n",
        set_status,
    )

    run_update = r'''    def _run_core_update(self) -> None:
        log_path = HOME / "logs" / "furinahub-inapp-update.log"
        try:
            command = shutil.which("furina")
            if not command:
                raise RuntimeError("launcher furina tidak ditemukan")
            self._set_update_status(
                state="running",
                result="",
                stage="checking",
                message="Memeriksa pembaruan Core & dependency…",
                percent=1,
                source="furinahub",
                target_version=VERSION,
                target_revision=EXPECTED_DEPENDENCY_REVISION,
                restart_required=False,
            )
            with log_path.open("w", encoding="utf-8") as log:
                update_env = dict(os.environ)
                update_env["FURINAHUB_MACHINE_PROGRESS"] = "1"
                update_env["FURINA_UPDATE_SOURCE"] = "furinahub"
                proc = subprocess.Popen(
                    [command, "update"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=update_env,
                )
                started = time.time()
                assert proc.stdout is not None
                for line in proc.stdout:
                    log.write(line)
                    log.flush()
                    # The shell updater owns the shared status file. Keep only a
                    # transient in-memory mirror for sub-second UI responsiveness.
                    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()
                    match = re.match(r"PROGRESS\s+(\d{1,3})\s+(.+)", clean)
                    if match:
                        with self.update_lock:
                            self.update_status.update(
                                state="running",
                                percent=max(1, min(99, int(match.group(1)))),
                                message=match.group(2)[:180],
                                elapsed_seconds=int(time.time() - started),
                            )
                proc.wait(timeout=1500)
            if proc.returncode != 0:
                current = self.get_update_status()
                if current.get("state") != "error":
                    detail = self._update_failure_detail(log_path)
                    self._set_update_status(
                        state="error",
                        result="error",
                        stage=str(current.get("stage") or "updater"),
                        message=f"Pembaruan gagal: {detail or f'updater berhenti (kode {proc.returncode})'}"[:320],
                        percent=int(current.get("percent") or 0),
                        source="furinahub",
                        restart_required=False,
                    )
                return
            current = self.get_update_status()
            if current.get("state") != "done":
                disk_version, revision = self._disk_update_versions()
                self._set_update_status(
                    state="done",
                    result="updated" if disk_version != VERSION else "no_update",
                    stage="done",
                    message=f"Pemeriksaan selesai. Core {disk_version or VERSION} · runtime {revision.rsplit('-', 1)[-1] if revision else '?'} aktif.",
                    percent=100,
                    source="furinahub",
                    target_version=disk_version or VERSION,
                    target_revision=revision or EXPECTED_DEPENDENCY_REVISION,
                    restart_required=bool(disk_version and disk_version != VERSION),
                )
        except Exception as exc:
            current = self.get_update_status()
            self._set_update_status(
                state="error",
                result="error",
                stage=str(current.get("stage") or "updater"),
                message=f"Pembaruan gagal pada tahap {current.get('stage') or 'updater'}: {str(exc)[:260]}",
                percent=int(current.get("percent") or 0),
                source="furinahub",
                restart_required=False,
            )

    def start_core_update(self) -> dict:
        current = self.get_update_status()
        if current.get("state") in {"running", "starting"}:
            return current
        self._set_update_status(
            state="starting",
            result="",
            stage="checking",
            message="Memeriksa pembaruan Core & dependency…",
            percent=0,
            source="furinahub",
            target_version=VERSION,
            target_revision=EXPECTED_DEPENDENCY_REVISION,
            restart_required=False,
        )
        threading.Thread(target=self._run_core_update, name="furinahub-core-update", daemon=True).start()
        return self.get_update_status()
'''
    hub = replace_method(
        hub,
        "    def _run_core_update(self) -> None:\n",
        "    def chat(self, text: str, image: dict | None = None, plugins: list | None = None) -> dict:\n",
        run_update + "\n    def chat(self, text: str, image: dict | None = None, plugins: list | None = None) -> dict:\n",
    )

    # The Android bridge target changes in RC45; accept either state so Core RC60
    # can be installed before or after the APK source patch is applied.
    version = version_path.read_text(encoding="utf-8")
    version = re.sub(
        r'VERSION\s*=\s*(["\'])([^"\']+)\1',
        f'VERSION = "{TARGET_VERSION}"',
        version,
        count=1,
    )

    compile(hub, str(hub_path), "exec")
    compile(version, str(version_path), "exec")
    required = (
        "EXPECTED_DEPENDENCY_REVISION",
        "def _disk_update_versions",
        "Disk state is authoritative",
        'update_env["FURINA_UPDATE_SOURCE"] = "furinahub"',
        'result="no_update"',
        'stage="checking"',
    )
    missing = [item for item in required if item not in hub]
    if missing:
        raise SystemExit("RC60 unified update integration incomplete: " + ", ".join(missing))

    atomic(hub_path, hub)
    atomic(version_path, version)
    if read_version(version_path) != TARGET_VERSION:
        raise SystemExit("RC60 version commit failed")
    print("FURINA_RC60_UNIFIED_UPDATE_STATE_OK")


if __name__ == "__main__":
    main()
