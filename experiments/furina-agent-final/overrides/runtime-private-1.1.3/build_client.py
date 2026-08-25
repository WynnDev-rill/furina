#!/usr/bin/env python3
"""Build the updater used by the chat-only private final channel."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_BUILDER = HERE.parent / "runtime-private-1.0.1" / "build_client.py"

spec = importlib.util.spec_from_file_location("furina_base_updater_builder", BASE_BUILDER)
if spec is None or spec.loader is None:
    raise SystemExit("base updater builder unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def build(base: Path, output: Path) -> None:
    module.build(base, output)
    text = output.read_text(encoding="utf-8")
    marker = "# FURINA_AUTO_APK_SYNC_113"
    start = text.find(marker)
    end = text.find('\nif __name__ == "__main__":', start)
    if start < 0 or end < 0:
        raise SystemExit("previous updater wrapper marker missing")
    replacement = r'''# FURINA_FINAL_113_APK_INSTALL_GATE
def _furina_113_sync_apk(root, channel, work, state):
    """Download exactly one matching APK and prove that Android installer opened."""
    confirmed = root / "data" / "furinahub_apk_bundle"
    if confirmed.exists() and confirmed.read_text(encoding="utf-8").strip() == channel["bundle_id"]:
        return False
    apk = channel["apk"]
    target = Path.home() / f"FurinaHub-v{apk['version']}.apk"
    state.progress(86, "bridge", f"Mengunduh FurinaHub {apk['version']}", channel)
    fetch(apk["url"], target, expected_sha256=apk["sha256"], expected_size=apk["size"], limit=MAX_APK_BYTES)
    atomic_text(root / "data" / "pending_apk_bundle", channel["bundle_id"] + "\n")
    if test_mode():
        return True
    opener = shutil.which("termux-open")
    if not opener:
        raise RuntimeError("APK sudah diunduh, tetapi termux-open tidak tersedia. Pasang APK ini secara manual: " + str(target))
    launched = subprocess.run(
        [opener, "--content-type", "application/vnd.android.package-archive", str(target)],
        check=False,
    )
    if launched.returncode != 0:
        raise RuntimeError("gagal membuka pemasang Android untuk: " + str(target))
    print("Dialog pemasangan Android dibuka. Tekan Perbarui/Instal, lalu buka FurinaHub.")
    return True

sync_apk = _furina_113_sync_apk

_furina_113_base_update = update
def update(args):
    # Base updater already syncs Core and downloads/opens the matching APK once.
    # Do not call apk-only again: that duplicate call hides the real Android
    # install gate and can make an old APK look like it was updated.
    result = _furina_113_base_update(args)
    if result != 0:
        return result
    root = root_dir()
    pending = root / "data" / "pending_apk_bundle"
    if pending.exists():
        bundle = pending.read_text(encoding="utf-8").strip()
        print("APK FurinaHub menunggu konfirmasi pemasangan Android.")
        print("Tekan Perbarui/Instal di dialog itu, lalu buka FurinaHub. Bundle menunggu: " + bundle)
    return result
'''
    text = text[:start] + replacement + text[end:]
    compile(text, str(output), "exec")
    output.write_text(text, encoding="utf-8")
    output.chmod(0o755)

def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(f"usage: {sys.argv[0]} [base-update-client.py] OUTPUT", file=sys.stderr)
        return 2
    base, output = (Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()) if len(sys.argv) == 3 else (module.DEFAULT_BASE, Path(sys.argv[1]).resolve())
    build(base, output)
    print("FURINA_FINAL_113_UPDATER_BUILD_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
