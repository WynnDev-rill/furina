#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
hub=root/'core/furina_agent/hub.py'
text=hub.read_text(encoding='utf-8')
old='''        target = (MODELS_DIR / item["file"]).resolve()\n        if not target.is_file(): raise ValueError("model lokal belum diunduh")'''
new='''        from .local_models import path_for, installed\n        target = path_for(item).resolve()\n        if not installed(item) or not target.is_file(): raise ValueError("model lokal belum diunduh atau belum lolos verifikasi")'''
if old not in text: raise SystemExit('1.1.0 model path marker missing')
hub.write_text(text.replace(old,new,1),encoding='utf-8')
compile(hub.read_text(encoding='utf-8'),str(hub),'exec')
print('FURINA_PRIVATE_1_1_0_FIXUP_OK')
