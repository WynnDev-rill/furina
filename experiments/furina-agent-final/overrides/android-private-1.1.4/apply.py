#!/usr/bin/env python3
"""Repair false APK-missing state and make Termux confirmation non-blocking."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
APP=ROOT/'bridge/app'; BUILD=APP/'build.gradle'; MAIN=APP/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'

text=BUILD.read_text(encoding='utf-8')
if 'versionCode 10080' not in text or "versionName '1.1.12'" not in text: raise SystemExit('expected Android 1.1.12')
BUILD.write_text(text.replace('versionCode 10080','versionCode 10081',1).replace("versionName '1.1.12'","versionName '1.1.13'",1),encoding='utf-8')

text=MAIN.read_text(encoding='utf-8')
for old,new,label in (
 ('private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.12";', 'private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.13";', 'bundle'),
 ('private static final String EXPECTED_CORE_VERSION = "1.1.12";', 'private static final String EXPECTED_CORE_VERSION = "1.1.13";', 'core'),
 ('private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r62";', 'private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r63";', 'revision'),
 ('new String[]{"furina-2026.08.25-private-1.1.12"}', 'new String[]{"furina-2026.08.25-private-1.1.13"}', 'confirm'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)

old='''        runFixedTermux("/data/data/com.termux/files/usr/bin/furina-apk-confirm", new String[]{"furina-2026.08.25-private-1.1.13"});
        BridgePrefs.openBootstrapWindow(this, 120_000L);'''
new='''        BridgePrefs.openBootstrapWindow(this, 120_000L);
        confirmInstalledApkIfAllowed();'''
if old not in text: raise SystemExit('resume confirmation marker missing')
text=text.replace(old,new,1)

marker='''    private void probeSavedCore() {'''
insert='''    private void confirmInstalledApkIfAllowed() {
        if (!isTermuxInstalled()) return;
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_COMMAND) != PackageManager.PERMISSION_GRANTED) return;
        try {
            runFixedTermux("/data/data/com.termux/files/usr/bin/furina-apk-confirm", new String[]{EXPECTED_BUNDLE_ID});
        } catch (Throwable ignored) {
            // Confirmation only avoids a future APK re-download; it must never mark Core offline.
        }
    }

'''
if marker not in text: raise SystemExit('probe marker missing')
text=text.replace(marker,insert+marker,1)

old='''                if (!EXPECTED_CORE_VERSION.equals(core) || !EXPECTED_DEPENDENCY_REVISION.equals(revision)
                        || !EXPECTED_BUNDLE_ID.equals(bundle)) {
                    bundleSyncChecked = false;
                    coreUpdateState = "Core baru menunggu FurinaHub dipasang dari dialog Android.";
                    handler.post(() -> setConnection("mismatch", "APK FurinaHub belum dipasang. Jalankan `furina update`, lalu tekan Perbarui di dialog Android.", false));
                }'''
new='''                boolean synced = state.optBoolean("bundle_synced", false);
                if (!synced || !EXPECTED_CORE_VERSION.equals(core) || !EXPECTED_DEPENDENCY_REVISION.equals(revision)
                        || !EXPECTED_BUNDLE_ID.equals(bundle)) {
                    bundleSyncChecked = false;
                    String detail = "Core " + (core.isEmpty() ? "tidak diketahui" : core)
                            + " · runtime " + (revision.isEmpty() ? "tidak diketahui" : revision);
                    coreUpdateState = "Core belum selaras: " + detail + ".";
                    handler.post(() -> setConnection("mismatch", detail + ". Jalankan `furina update` di Termux.", false));
                }'''
if old not in text: raise SystemExit('false APK mismatch marker missing')
text=text.replace(old,new,1)

old='''            if (granted && update) startCoreRecoveryUpdate();
            else if (granted) startCoreConnection();
            else setConnection("permission_required", "Izin Termux diperlukan agar FurinaHub dapat menyalakan Core.", false);'''
new='''            if (granted) confirmInstalledApkIfAllowed();
            if (granted && update) startCoreRecoveryUpdate();
            else if (granted) startCoreConnection();
            else setConnection("permission_required", "Izin Termux diperlukan agar FurinaHub dapat menyalakan Core.", false);'''
if old not in text: raise SystemExit('permission confirmation marker missing')
text=text.replace(old,new,1)
MAIN.write_text(text,encoding='utf-8')
print('FURINA_FINAL_114_ANDROID_OK')
