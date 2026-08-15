#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC46 marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    hub_path = core / "hub.py"
    version_path = core / "version.py"
    if not hub_path.is_file() or not version_path.is_file():
        raise SystemExit("RC46 source Core tidak lengkap")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc46"' in version:
        print("FurinaHub Core RC46 already applied")
        return
    if 'VERSION = "1.0.0-rc45"' not in version:
        raise SystemExit("RC46 hanya dapat diterapkan dari Core RC45")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(
        hub,
        '''            elif waking or time.monotonic() - self._connector_wake_at < 8:
                out.update(state="starting", message="Menyalakan layanan Plugin…")
            else:
                detail = self._connector_runtime_error()
                fallback = str(exc).strip()[:220]
                out.update(
                    state="error",
                    message=(detail or fallback or "Layanan Plugin gagal dimulai. Tekan Perbaiki / update Core & dependency."),
                )
''',
        '''            elif waking or time.monotonic() - self._connector_wake_at < 12:
                out.update(state="starting", message="Menyalakan layanan Plugin…", repairable=False)
            else:
                detail = self._connector_runtime_error()
                fallback = str(exc).strip()[:220]
                out.update(
                    state="error",
                    repairable=True,
                    message=(detail or fallback or "Layanan Plugin gagal dimulai. Gunakan Perbaiki Plugin."),
                )
''',
        "connector terminal state",
    )
    hub = replace_once(
        hub,
        '''                "state": status.get("state", "offline"),
                "message": status.get("message", "Layanan Plugin belum siap."),
            }
''',
        '''                "state": status.get("state", "offline"),
                "message": status.get("message", "Layanan Plugin belum siap."),
                "repairable": bool(status.get("repairable") or status.get("state") in {"missing", "error"}),
            }
''',
        "plugin repair hint",
    )
    if hub.count('"bridge_target": "1.0.0-rc28"') != 2:
        raise SystemExit("RC46 bridge target marker berubah")
    hub = hub.replace('"bridge_target": "1.0.0-rc28"', '"bridge_target": "1.0.0-rc29"')

    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(
        version.replace('VERSION = "1.0.0-rc45"', 'VERSION = "1.0.0-rc46"', 1),
        encoding="utf-8",
    )
    for path in (hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    joined = hub_path.read_text(encoding="utf-8") + "\n" + version_path.read_text(encoding="utf-8")
    required = (
        'VERSION = "1.0.0-rc46"',
        'time.monotonic() - self._connector_wake_at < 12',
        'repairable=True',
        '"repairable": bool(status.get("repairable")',
        '"bridge_target": "1.0.0-rc29"',
    )
    missing = [x for x in required if x not in joined]
    if missing:
        raise SystemExit(f"RC46 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC46_OK")


if __name__ == "__main__":
    main()
