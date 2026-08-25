#!/usr/bin/env python3
"""Keep a successful Core pairing connected even if update metadata is stale."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
APP=ROOT/'bridge/app'; BUILD=APP/'build.gradle'; MAIN=APP/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'
text=BUILD.read_text(encoding='utf-8')
if 'versionCode 10081' not in text or "versionName '1.1.13'" not in text: raise SystemExit('expected Android 1.1.13')
BUILD.write_text(text.replace('versionCode 10081','versionCode 10082',1).replace("versionName '1.1.13'","versionName '1.1.14'",1),encoding='utf-8')
text=MAIN.read_text(encoding='utf-8')
for old,new,label in (
 ('private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.13";', 'private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.14";', 'bundle'),
 ('private static final String EXPECTED_CORE_VERSION = "1.1.13";', 'private static final String EXPECTED_CORE_VERSION = "1.1.14";', 'core'),
 ('private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r63";', 'private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r64";', 'revision'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)
old='''                    coreUpdateState = "Core belum selaras: " + detail + ".";
                    handler.post(() -> setConnection("mismatch", detail + ". Jalankan `furina update` di Termux.", false));'''
new='''                    coreUpdateState = "Status paket perlu diselaraskan: " + detail + ". Jalankan `furina update` di Termux.";
                    // /api/system already proved the paired Core is reachable. Metadata must
                    // never overwrite that healthy connection with a false Offline state.
                    handler.post(this::notifyShellConnection);'''
if old not in text: raise SystemExit('metadata-to-offline marker missing')
text=text.replace(old,new,1)
MAIN.write_text(text,encoding='utf-8')
print('FURINA_FINAL_115_ANDROID_OK')
