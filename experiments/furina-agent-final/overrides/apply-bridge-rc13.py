#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    n=text.count(old)
    if n!=1: raise SystemExit(f'Bridge RC13 marker mismatch {label}: {n}')
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-bridge-rc13.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); j=root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge'
    runtime=j/'BridgeRuntime.java'; service=j/'FurinaAccessibilityService.java'; updater=j/'BridgeUpdater.java'; gradle=root/'bridge/app/build.gradle'
    for p in (runtime,service,updater,gradle):
        if not p.is_file(): raise SystemExit(f'missing Bridge RC13 source: {p}')

    r=runtime.read_text()
    r=rep(r,'        out.put("version", "1.0.0-rc8");\n','''        try {
            android.content.pm.PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
            out.put("version", info.versionName == null ? String.valueOf(info.getLongVersionCode()) : info.versionName);
            out.put("version_code", info.getLongVersionCode());
        } catch (Throwable ignored) {
            out.put("version", "unknown");
            out.put("version_code", 0L);
        }
''','dynamic health version')
    runtime.write_text(r)

    s=service.read_text()
    s=rep(s,'        if (steps == null || steps.length() == 0 || steps.length() > 10) return out.put("error", "invalid_sequence");\n','        if (steps == null || steps.length() == 0 || steps.length() > 18) return out.put("error", "invalid_sequence");\n','sequence length')
    s=rep(s,'        if ("tap_text".equals(type)) return step.optInt("max_scrolls", 0) > 0 || fastFind(step) != null;\n','        if ("tap_text".equals(type)) return fastFind(step) != null;\n','tap readiness')
    s=rep(s,'''            if ("open_app".equals(type)) {
                ok = openApp(step.optString("package", ""));
''','''            if ("open_app".equals(type)) {
                String packageName = step.optString("package", "");
                ok = openApp(packageName) && waitFastPackage(packageName, step.optLong("timeout_ms", 5000L));
''','open wait package')
    service.write_text(s)

    u=updater.read_text()
    u=rep(u,'        activity.grantUriPermission("com.google.android.packageinstaller", uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);\n','''        try {
            for (android.content.pm.ResolveInfo handler : activity.getPackageManager().queryIntentActivities(intentForApk(uri), PackageManager.MATCH_DEFAULT_ONLY)) {
                if (handler.activityInfo != null) activity.grantUriPermission(handler.activityInfo.packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            }
        } catch (Throwable ignored) {}
''','installer package grant')
    u=rep(u,'''        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        activity.startActivity(intent);
    }
''','''        Intent intent = intentForApk(uri);
        activity.startActivity(intent);
    }

    private Intent intentForApk(Uri uri) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        return intent;
    }
''','installer intent helper')
    updater.write_text(u)

    g=gradle.read_text(); g=rep(g,'        versionCode 10012','        versionCode 10013','version code'); g=rep(g,"        versionName '1.0.0-rc12'","        versionName '1.0.0-rc13'",'version name'); gradle.write_text(g)
    checks=[(runtime,'version_code'),(service,'steps.length() > 18'),(service,'waitFastPackage(packageName'),(updater,'intentForApk'),(gradle,'versionCode 10013')]
    missing=[n for p,n in checks if n not in p.read_text()]
    if missing: raise SystemExit('Bridge RC13 incomplete: '+', '.join(missing))
    print('Furina Bridge RC13 health + executor fixes: OK')

if __name__=='__main__': main()
