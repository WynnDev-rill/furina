#!/usr/bin/env python3
"""Build a repair updater with one authoritative bundle state."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE_BUILDER=HERE.parent/'runtime-private-1.1.3'/'build_client.py'
spec=importlib.util.spec_from_file_location('furina_113_updater_builder',BASE_BUILDER)
if spec is None or spec.loader is None: raise SystemExit('base updater builder unavailable')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

def build(base: Path, output: Path) -> None:
    module.build(base,output)
    text=output.read_text(encoding='utf-8')
    marker='# FURINA_FINAL_113_APK_INSTALL_GATE'
    start=text.find(marker); end=text.find('\nif __name__ == "__main__":',start)
    if start<0 or end<0: raise SystemExit('previous updater repair marker missing')
    repair=r'''# FURINA_FINAL_114_AUTHORITATIVE_BUNDLE_STATE
_furina_114_install_core = install_core
def install_core(root, channel, work, state, *, force):
    changed = _furina_114_install_core(root, channel, work, state, force=force)
    # Hub used to read these legacy files while the updater wrote only JSON.
    # Keep them synchronized for migration, but JSON remains authoritative.
    atomic_text(root / "data" / "dependency_revision", str(channel["core"]["revision"]) + "\n")
    atomic_text(root / "data" / "bundle_id", str(channel["bundle_id"]) + "\n")
    return changed

'''+text[start:end]+r'''
'''
    text=text[:start]+repair+text[end:]
    compile(text,str(output),'exec')
    output.write_text(text,encoding='utf-8'); output.chmod(0o755)

def main() -> int:
    if len(sys.argv) not in {2,3}:
        print(f'usage: {sys.argv[0]} [base-update-client.py] OUTPUT',file=sys.stderr); return 2
    base,output=(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve()) if len(sys.argv)==3 else (module.module.DEFAULT_BASE,Path(sys.argv[1]).resolve())
    build(base,output); print('FURINA_FINAL_114_UPDATER_BUILD_OK'); return 0

if __name__=='__main__': raise SystemExit(main())
