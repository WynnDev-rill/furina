#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    n=text.count(old)
    if n!=1: raise SystemExit(f'Bridge RC14 marker mismatch {label}: {n}')
    return text.replace(old,new,1)

def before(text,marker,block,label):
    if block.strip() in text: return text
    n=text.count(marker)
    if n!=1: raise SystemExit(f'Bridge RC14 insertion mismatch {label}: {n}')
    return text.replace(marker,block.rstrip()+"\n\n"+marker,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-bridge-rc14.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); service=root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java'; gradle=root/'bridge/app/build.gradle'
    if not service.is_file() or not gradle.is_file(): raise SystemExit('missing Bridge RC14 source')
    s=service.read_text(encoding='utf-8')

    helper='''    private boolean isTermuxPackageFast(String packageName) {
        if (packageName == null) return false;
        String value = packageName.trim().toLowerCase(java.util.Locale.ROOT);
        return value.equals("com.termux") || value.startsWith("com.termux.");
    }
'''
    s=before(s,'    private static String fastNorm(String value) {\n',helper,'Termux package helper')

    s=rep(s,
'''        for (int attempt = 0; attempt <= maxScrolls; attempt++) {
            AccessibilityNodeInfo node = fastFind(action);
''',
'''        for (int attempt = 0; attempt <= maxScrolls; attempt++) {
            if (isTermuxPackageFast(activeRootPackage())) return false;
            AccessibilityNodeInfo node = fastFind(action);
''','tap return guard')
    s=rep(s,
'''    private boolean setTextFast(JSONObject action) {
        String text = action.optString("text", "");
''',
'''    private boolean setTextFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        String text = action.optString("text", "");
''','text return guard')
    s=rep(s,
'''    private boolean imeFast() {
        configureAgentAccessibility();
''',
'''    private boolean imeFast() {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        configureAgentAccessibility();
''','ime return guard')
    s=rep(s,
'''    private boolean scrollBestFast(JSONObject action) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
''',
'''    private boolean scrollBestFast(JSONObject action) {
        if (isTermuxPackageFast(activeRootPackage())) return false;
        AccessibilityNodeInfo root = getRootInActiveWindow();
''','scroll return guard')

    s=rep(s,
'''        while (System.currentTimeMillis() < deadline) {
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
            if (nextFastReady(next)) return;
        }
''',
'''        while (System.currentTimeMillis() < deadline) {
            if (isTermuxPackageFast(activeRootPackage())) return;
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
            if (isTermuxPackageFast(activeRootPackage()) || nextFastReady(next)) return;
        }
''','next wait return guard')

    s=rep(s,
'''        long started = System.currentTimeMillis();
        for (int i = 0; i < steps.length(); i++) {
            JSONObject step = steps.optJSONObject(i);
''',
'''        long started = System.currentTimeMillis();
        boolean leftTermux = false;
        for (int i = 0; i < steps.length(); i++) {
            String foregroundBefore = activeRootPackage();
            if (foregroundBefore != null && !foregroundBefore.isEmpty() && !isTermuxPackageFast(foregroundBefore)) {
                leftTermux = true;
            } else if (leftTermux && isTermuxPackageFast(foregroundBefore)) {
                return out.put("cancelled_user_return", true).put("completed_steps", i).put("elapsed_ms", System.currentTimeMillis() - started);
            }
            JSONObject step = steps.optJSONObject(i);
''','sequence pre-step breaker')

    s=rep(s,
'''            out.put("completed_steps", i + 1);
            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
''',
'''            out.put("completed_steps", i + 1);
            String foregroundAfter = activeRootPackage();
            if (foregroundAfter != null && !foregroundAfter.isEmpty() && !isTermuxPackageFast(foregroundAfter)) {
                leftTermux = true;
            } else if (leftTermux && isTermuxPackageFast(foregroundAfter)) {
                return out.put("cancelled_user_return", true).put("completed_steps", i + 1).put("elapsed_ms", System.currentTimeMillis() - started);
            }
            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
''','sequence post-step breaker')

    service.write_text(s,encoding='utf-8')
    g=gradle.read_text(encoding='utf-8'); g=rep(g,'        versionCode 10013','        versionCode 10014','version code'); g=rep(g,"        versionName '1.0.0-rc13'","        versionName '1.0.0-rc14'",'version name'); gradle.write_text(g,encoding='utf-8')
    checks=[(service,'cancelled_user_return'),(service,'isTermuxPackageFast'),(service,'boolean leftTermux = false'),(gradle,'versionCode 10014'),(gradle,"versionName '1.0.0-rc14'")]
    missing=[n for p,n in checks if n not in p.read_text(encoding='utf-8')]
    if missing: raise SystemExit('Bridge RC14 incomplete: '+', '.join(missing))
    print('Furina Bridge RC14 user-return circuit breaker: OK')

if __name__=='__main__': main()
