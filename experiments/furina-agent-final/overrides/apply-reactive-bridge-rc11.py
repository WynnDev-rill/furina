#!/usr/bin/env python3
from __future__ import annotations
import pathlib, sys

def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text: return text
    if text.count(old) != 1: raise SystemExit(f"Bridge RC11 marker mismatch {label}: {text.count(old)}")
    return text.replace(old, new, 1)

def main() -> None:
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    s = service.read_text(encoding="utf-8")
    old_ready = '''    private boolean nextFastReady(JSONObject step) {
        String type = step.optString("type", "");
        if ("tap_text".equals(type) || "wait_text".equals(type)) return fastFind(step) != null;
        if ("set_text_best".equals(type) || "ime_best".equals(type)) return fastEditable() != null;
        if ("wait_package".equals(type)) return step.optString("package", "").equals(activeRootPackage());
        return false;
    }

    private void awaitFastNext(JSONArray steps, int nextIndex, long afterSequence, long timeoutMs) {
        if (nextIndex >= steps.length()) return;
        JSONObject next = steps.optJSONObject(nextIndex);
        if (next == null || nextFastReady(next)) return;
        long deadline = System.currentTimeMillis() + Math.max(40L, timeoutMs);
        long sequence = afterSequence;
        while (System.currentTimeMillis() < deadline) {
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
            if (nextFastReady(next)) return;
        }
    }
'''
    new_ready = '''    private boolean nextNeedsReadyWait(JSONObject step) {
        if (step == null) return false;
        String type = step.optString("type", "");
        return "tap_text".equals(type) || "wait_text".equals(type) || "set_text_best".equals(type) || "ime_best".equals(type) || "wait_package".equals(type);
    }

    private boolean nextFastReady(JSONObject step) {
        if (step == null) return true;
        String type = step.optString("type", "");
        if ("tap_text".equals(type) || "wait_text".equals(type)) return fastFind(step) != null;
        if ("set_text_best".equals(type) || "ime_best".equals(type)) return fastEditable() != null;
        if ("wait_package".equals(type)) return step.optString("package", "").equals(activeRootPackage());
        return true;
    }

    private void awaitFastNext(JSONArray steps, int nextIndex, long afterSequence, long timeoutMs) {
        if (nextIndex >= steps.length()) return;
        JSONObject next = steps.optJSONObject(nextIndex);
        if (next == null || !nextNeedsReadyWait(next) || nextFastReady(next)) return;
        long deadline = System.currentTimeMillis() + Math.max(40L, timeoutMs);
        long sequence = afterSequence;
        while (System.currentTimeMillis() < deadline) {
            waitFastEvent(sequence, Math.min(120L, Math.max(1L, deadline - System.currentTimeMillis())));
            sequence = currentEventSeq();
            if (nextFastReady(next)) return;
        }
    }
'''
    s = rep(s, old_ready, new_ready, "readiness")
    s = rep(s, '''            if ("open_app".equals(type)) {
                ok = openApp(step.optString("package", "")) && waitFastPackage(step.optString("package", ""), step.optLong("timeout_ms", 1300L));
''', '''            if ("open_app".equals(type)) {
                ok = openApp(step.optString("package", ""));
''', "open continuation")
    s = rep(s, '''            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
                awaitFastNext(steps, i + 1, sequence, "open_app".equals(type) ? 900L : 420L);
            }
''', '''            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
                long nextTimeout;
                if ("open_app".equals(type) || "ime_best".equals(type)) nextTimeout = 3200L;
                else if ("tap_text".equals(type) || "set_text_best".equals(type)) nextTimeout = 1800L;
                else nextTimeout = 0L;
                if (nextTimeout > 0L) awaitFastNext(steps, i + 1, sequence, nextTimeout);
            }
''', "adaptive wait")
    service.write_text(s, encoding="utf-8")
    g = gradle.read_text(encoding="utf-8")
    g = rep(g, "        versionCode 10010", "        versionCode 10011", "versionCode")
    g = rep(g, "        versionName '1.0.0-rc10'", "        versionName '1.0.0-rc11'", "versionName")
    gradle.write_text(g, encoding="utf-8")
    print("Furina Bridge RC11: OK")

if __name__ == "__main__": main()
