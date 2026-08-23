#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
HTML = APP / "src/main/assets/furinahub/index.html"


def one(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected one match, got {text.count(old)}")
    return text.replace(old, new, 1)

build = BUILD.read_text(encoding="utf-8")
build = one(build, "versionCode 10059", "versionCode 10060", "version code")
build = one(build, "versionName '1.0.1'", "versionName '1.0.2'", "version name")
BUILD.write_text(build, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
main = one(main, 'EXPECTED_CORE_VERSION = "1.0.1"', 'EXPECTED_CORE_VERSION = "1.0.2"', "expected core")
main = one(main, 'furina-2026.08.23-private-1.0.1', 'furina-2026.08.24-private-1.0.2', "bundle id")
MAIN.write_text(main, encoding="utf-8")

page = HTML.read_text(encoding="utf-8")
old = '''async function selectLocalModel(path){await saveCore({routing_mode:'local',model_path:path,auto_start:false})}'''
new = '''async function selectLocalModel(path){await saveCore({routing_mode:'local',model_path:path,auto_start:false});try{const r=await core('POST','/api/models',{action:'prewarm'});paintModelProgress({state:r.state||'starting',message:r.message||'Menyiapkan model lokal…',percent:0})}catch(e){toast('Model akan disiapkan saat chat dibuka.')}}'''
page = one(page, old, new, "local prewarm action")
# Product copy makes cold-start work visible without presenting technical knobs.
page = page.replace("Hanya satu model lokal aktif pada satu waktu. Setelah unduhan selesai, tekan Pilih.", "Hanya satu model lokal aktif pada satu waktu. Setelah dipilih, Furina menyiapkannya di background agar chat pertama lebih cepat.")
HTML.write_text(page, encoding="utf-8")

print("FURINAHUB_PRIVATE_1_0_2_PERFORMANCE_UI_OK")
