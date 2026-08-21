#!/usr/bin/env python3
from pathlib import Path
import shutil,sys

BUNDLE_OLD="furina-2026.08.21-rc62-rc50"
BUNDLE_NEW="furina-2026.08.21-rc63-rc51"

def once(text,old,new,label):
    if old not in text:
        if new in text: return text
        raise SystemExit(f"RC51 marker missing: {label}")
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit("usage: apply.py <furina-root>")
    root=Path(sys.argv[1]).resolve(); here=Path(__file__).resolve().parent
    app=root/'bridge/app'; java=app/'src/main/java/com/wynndev/furinaagentbridge'
    gradle=app/'build.gradle'; main_path=java/'MainActivity.java'; runtime_path=java/'BridgeRuntime.java'
    for p in (gradle,main_path,runtime_path):
        if not p.is_file(): raise SystemExit(f"RC51 source missing: {p}")
    shutil.copyfile(here/'NativeImageEditorActivity.java',java/'NativeImageEditorActivity.java')
    g=gradle.read_text(); g=once(g,'versionCode 10050','versionCode 10051','version code'); g=once(g,"versionName '1.0.0-rc50'","versionName '1.0.0-rc51'",'version name')
    main=main_path.read_text().replace(BUNDLE_OLD,BUNDLE_NEW)
    main=once(main,'EXPECTED_CORE_VERSION = "1.0.0-rc62"','EXPECTED_CORE_VERSION = "1.0.0-rc63"','Core target')
    main=once(main,'EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r32"','EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r33"','runtime target')
    runtime=runtime_path.read_text().replace(BUNDLE_OLD,BUNDLE_NEW)
    combined='\n'.join((g,main,runtime,(here/'NativeImageEditorActivity.java').read_text()))
    for marker in ('versionCode 10051',"versionName '1.0.0-rc51'",BUNDLE_NEW,'EXPECTED_CORE_VERSION = "1.0.0-rc63"','roundBackground','editor.setPadding(dp(16)'):
        if marker not in combined: raise SystemExit(f"RC51 integration incomplete: {marker}")
    gradle.write_text(g); main_path.write_text(main); runtime_path.write_text(runtime)
    print('FURINAHUB_ANDROID_RC51_POLISHED_NATIVE_EDITOR_OK')

if __name__=='__main__': main()
