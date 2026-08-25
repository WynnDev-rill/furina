#!/usr/bin/env python3
"""Advance the APK contract and make pending APK installation unambiguous."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
APP=ROOT/'bridge/app'; BUILD=APP/'build.gradle'; MAIN=APP/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'

text=BUILD.read_text(encoding='utf-8')
if 'versionCode 10079' not in text or "versionName '1.1.11'" not in text: raise SystemExit('expected Android 1.1.11')
BUILD.write_text(text.replace('versionCode 10079','versionCode 10080',1).replace("versionName '1.1.11'","versionName '1.1.12'",1),encoding='utf-8')

text=MAIN.read_text(encoding='utf-8')
for old,new,label in (
 ('private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.11";', 'private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.12";', 'bundle'),
 ('private static final String EXPECTED_CORE_VERSION = "1.1.11";', 'private static final String EXPECTED_CORE_VERSION = "1.1.12";', 'core'),
 ('private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r61";', 'private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r62";', 'revision'),
 ('new String[]{"furina-2026.08.25-private-1.1.11"}', 'new String[]{"furina-2026.08.25-private-1.1.12"}', 'confirm'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)
# An APK cannot silently install itself. Make the actual state/action explicit
# rather than presenting an opaque Core mismatch as a connection failure.
old='coreUpdateState = "Versi Core berbeda. Jalankan `furina update` di Termux.";\n                    handler.post(() -> setConnection("mismatch", "Versi Core berbeda. Update melalui Termux.", false));'
new='coreUpdateState = "Core baru menunggu FurinaHub dipasang dari dialog Android.";\n                    handler.post(() -> setConnection("mismatch", "APK FurinaHub belum dipasang. Jalankan `furina update`, lalu tekan Perbarui di dialog Android.", false));'
if old not in text: raise SystemExit('mismatch copy marker missing')
text=text.replace(old,new,1)
MAIN.write_text(text,encoding='utf-8')
print('FURINA_FINAL_113_ANDROID_OK')
