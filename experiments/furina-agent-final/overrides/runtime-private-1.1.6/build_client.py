#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent; BASE=HERE.parent/'runtime-private-1.1.5'/'build_client.py'
spec=importlib.util.spec_from_file_location('furina_115_builder',BASE)
if spec is None or spec.loader is None: raise SystemExit('base builder unavailable')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
def main() -> int:
    if len(sys.argv) not in {2,3}: print(f'usage: {sys.argv[0]} [base-update-client.py] OUTPUT',file=sys.stderr); return 2
    base,output=(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve()) if len(sys.argv)==3 else (module.module.module.module.DEFAULT_BASE,Path(sys.argv[1]).resolve())
    module.build(base,output); print('FURINA_FINAL_116_UPDATER_BUILD_OK'); return 0
if __name__=='__main__': raise SystemExit(main())
