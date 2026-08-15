#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC45 marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    hub_path = core / "hub.py"
    version_path = core / "version.py"
    if not hub_path.is_file() or not version_path.is_file():
        raise SystemExit("RC45 source Core tidak lengkap")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc45"' in version:
        print("FurinaHub Core RC45 already applied")
        return
    if 'VERSION = "1.0.0-rc44"' not in version:
        raise SystemExit("RC45 hanya dapat diterapkan dari Core RC44")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(
        hub,
        '''    def _wake_connector_runtime(self) -> bool:
        """Ask the managed Termux launcher to start without blocking the UI."""
        now = time.monotonic()
        if now - self._connector_wake_at < 8:
            return False
        self._connector_wake_at = now
        launcher = shutil.which("furina-openconnector")
        if not launcher:
            return False
        try:
            subprocess.Popen(
                [launcher, "start"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            return False
''',
        '''    def _wake_connector_runtime(self) -> bool:
        """Ask the managed Termux launcher to start without blocking the UI."""
        now = time.monotonic()
        if now - self._connector_wake_at < 8:
            return False
        self._connector_wake_at = now
        launcher = shutil.which("furina-openconnector")
        if not launcher:
            return False
        try:
            subprocess.Popen(
                [launcher, "start"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _connector_runtime_error() -> str:
        log_path = HOME / "logs" / "openconnector.log"
        try:
            raw = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
        except Exception:
            return ""
        raw = re.sub(r"\\x1b\\[[0-?]*[ -/]*[@-~]", "", raw).replace("\\r", "\\n")
        lines = []
        for item in raw.splitlines():
            line = " ".join(item.strip().split())
            if not line or line in lines:
                continue
            lines.append(line)
        return " · ".join(lines[-2:])[:360]
''',
        "connector runtime diagnostics",
    )

    hub = replace_once(
        hub,
        '''        except Exception:
            waking = self._wake_connector_runtime()
            installed = bool(shutil.which("furina-openconnector"))
            out.update(
                state="starting" if waking or installed else "missing",
                message=(
                    "Menyalakan layanan Plugin…"
                    if waking or installed
                    else "Komponen Plugin belum terpasang. Jalankan update Core & dependency."
                ),
            )
''',
        '''        except Exception as exc:
            launcher = shutil.which("furina-openconnector")
            waking = self._wake_connector_runtime() if launcher else False
            if not launcher:
                out.update(
                    state="missing",
                    message="Komponen Plugin belum terpasang. Jalankan update Core & dependency.",
                )
            elif waking or time.monotonic() - self._connector_wake_at < 8:
                out.update(state="starting", message="Menyalakan layanan Plugin…")
            else:
                detail = self._connector_runtime_error()
                fallback = str(exc).strip()[:220]
                out.update(
                    state="error",
                    message=(detail or fallback or "Layanan Plugin gagal dimulai. Tekan Perbaiki / update Core & dependency."),
                )
''',
        "connector status terminal error",
    )

    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(
        version.replace('VERSION = "1.0.0-rc44"', 'VERSION = "1.0.0-rc45"', 1),
        encoding="utf-8",
    )

    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    joined = hub_path.read_text(encoding="utf-8") + "\n" + version_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc45"',
        "_connector_runtime_error",
        'state="error"',
        "time.monotonic() - self._connector_wake_at < 8",
        '"bridge_target": "1.0.0-rc28"',
    )
    missing = [item for item in required if item not in joined]
    if missing:
        raise SystemExit(f"RC45 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC45_OK")


if __name__ == "__main__":
    main()
