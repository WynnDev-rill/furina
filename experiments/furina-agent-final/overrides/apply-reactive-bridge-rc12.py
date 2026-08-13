#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    if text.count(old)!=1: raise SystemExit(f"Bridge RC12 marker mismatch {label}: {text.count(old)}")
    return text.replace(old,new,1)

def before(text,marker,block,label):
    if block.strip() in text: return text
    if text.count(marker)!=1: raise SystemExit(f"Bridge RC12 insertion mismatch {label}: {text.count(marker)}")
    return text.replace(marker,block.rstrip()+"\n\n"+marker,1)

def main():
    root=pathlib.Path(sys.argv[1]).resolve()
    service=root/"bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle=root/"bridge/app/build.gradle"
    s=service.read_text(encoding="utf-8")
    runtime=r'''    private void configureAgentAccessibility() {
        try {
            android.accessibilityservice.AccessibilityServiceInfo info = getServiceInfo();
            if (info == null) return;
            info.eventTypes |= AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                    | AccessibilityEvent.TYPE_WINDOWS_CHANGED
                    | AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
                    | AccessibilityEvent.TYPE_VIEW_CLICKED
                    | AccessibilityEvent.TYPE_VIEW_SCROLLED
                    | AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED
                    | AccessibilityEvent.TYPE_VIEW_FOCUSED;
            info.packageNames = null;
            info.notificationTimeout = 15L;
            info.flags |= android.accessibilityservice.AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;
            info.flags |= android.accessibilityservice.AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                info.flags |= android.accessibilityservice.AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;
            }
            setServiceInfo(info);
        } catch (Throwable ignored) {}
    }

    private String[] fastRoleAliases(String role) {
        String r = fastNorm(role);
        if ("search".equals(r)) return new String[]{"search", "cari", "pencarian", "telusuri", "find"};
        if ("settings".equals(r)) return new String[]{"settings", "setelan", "pengaturan"};
        if ("battery".equals(r)) return new String[]{"battery", "baterai"};
        if ("battery_usage".equals(r)) return new String[]{"battery usage", "penggunaan baterai", "penggunaan baterai aplikasi", "app battery usage"};
        if ("details".equals(r)) return new String[]{"details", "detail", "selengkapnya", "more details", "deskripsi", "description"};
        if ("latest".equals(r)) return new String[]{"latest", "terbaru", "recent", "paling baru"};
        if ("menu".equals(r)) return new String[]{"menu", "more options", "opsi lainnya", "lainnya"};
        if ("notes".equals(r)) return new String[]{"notes", "catatan"};
        return new String[0];
    }
'''
    s=before(s,"    private static String fastNorm(String value) {\n",runtime,"runtime")
    old='''    private AccessibilityNodeInfo fastFind(JSONObject action) {
        JSONArray targets = action.optJSONArray("targets");
        if (targets != null) {
            AccessibilityNodeInfo best = null;
            int bestScore = -1;
            for (int i = 0; i < targets.length(); i++) {
                String wanted = targets.optString(i, "");
                AccessibilityNodeInfo node = fastFind(wanted);
                int score = fastScore(node, wanted);
                if (score > bestScore) {
                    best = node;
                    bestScore = score;
                }
            }
            if (best != null) return best;
        }
        return fastFind(action.optString("target", ""));
    }
'''
    new='''    private AccessibilityNodeInfo fastFind(JSONObject action) {
        AccessibilityNodeInfo best = null;
        int bestScore = -1;
        java.util.ArrayList<String> wantedValues = new java.util.ArrayList<>();
        JSONArray targets = action.optJSONArray("targets");
        if (targets != null) for (int i = 0; i < targets.length(); i++) {
            String value = targets.optString(i, "").trim();
            if (!value.isEmpty()) wantedValues.add(value);
        }
        String target = action.optString("target", "").trim();
        if (!target.isEmpty()) wantedValues.add(target);
        for (String alias : fastRoleAliases(action.optString("role", ""))) wantedValues.add(alias);
        for (String wanted : wantedValues) {
            AccessibilityNodeInfo node = fastFind(wanted);
            int score = fastScore(node, wanted);
            if (score > bestScore) { best = node; bestScore = score; }
        }
        return best;
    }
'''
    s=rep(s,old,new,"role find")
    old='''    private boolean tapTextFast(JSONObject action) {
        AccessibilityNodeInfo node = fastFind(action);
        if (node == null) return false;
        AccessibilityNodeInfo current = node;
        for (int i = 0; i < 6 && current != null; i++) {
            if (current.isEnabled() && current.isClickable()
                    && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
            current = current.getParent();
        }
        Rect rect = new Rect();
        node.getBoundsInScreen(rect);
        return !rect.isEmpty() && tap(rect.centerX(), rect.centerY());
    }
'''
    new='''    private boolean tapTextFast(JSONObject action) {
        configureAgentAccessibility();
        int maxScrolls = Math.max(0, Math.min(action.optInt("max_scrolls", 0), 6));
        for (int attempt = 0; attempt <= maxScrolls; attempt++) {
            AccessibilityNodeInfo node = fastFind(action);
            if (node != null) {
                AccessibilityNodeInfo current = node;
                for (int i = 0; i < 6 && current != null; i++) {
                    if (current.isEnabled() && current.isClickable() && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
                    current = current.getParent();
                }
                Rect rect = new Rect(); node.getBoundsInScreen(rect);
                if (!rect.isEmpty() && tap(rect.centerX(), rect.centerY())) return true;
            }
            if (attempt >= maxScrolls) break;
            long sequence = currentEventSeq();
            try {
                JSONObject scroll = new JSONObject().put("direction", "forward");
                if (!scrollBestFast(scroll)) break;
            } catch (Throwable ignored) { break; }
            waitFastEvent(sequence, 650L);
        }
        return false;
    }
'''
    s=rep(s,old,new,"scroll tap")
    old='''    private boolean imeFast() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false;
        AccessibilityNodeInfo node = fastEditable();
        if (node == null) return false;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        return node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());
    }
'''
    new='''    private boolean imeFast() {
        configureAgentAccessibility();
        AccessibilityNodeInfo node = fastEditable();
        if (node != null) {
            if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId())) return true;
        }
        try { return tapTextFast(new JSONObject().put("role", "search").put("max_scrolls", 0)); }
        catch (Throwable ignored) { return false; }
    }
'''
    s=rep(s,old,new,"ime fallback")
    s=rep(s,'        if ("tap_text".equals(type) || "wait_text".equals(type)) return fastFind(step) != null;\n','        if ("tap_text".equals(type)) return step.optInt("max_scrolls", 0) > 0 || fastFind(step) != null;\n        if ("wait_text".equals(type)) return fastFind(step) != null;\n',"tap readiness")
    s=rep(s,'    private JSONObject runUiSequence(JSONObject action) throws JSONException {\n        JSONArray steps = action.optJSONArray("steps");\n','    private JSONObject runUiSequence(JSONObject action) throws JSONException {\n        configureAgentAccessibility();\n        JSONArray steps = action.optJSONArray("steps");\n',"configure sequence")
    s=rep(s,'            if (!ok) return out.put("failed_step", i).put("error", "step_failed").put("elapsed_ms", System.currentTimeMillis() - started);\n','            if (!ok) return out.put("failed_step", i).put("failed_type", type).put("error", "step_failed").put("package", activeRootPackage()).put("event_seq", currentEventSeq()).put("elapsed_ms", System.currentTimeMillis() - started);\n',"diagnostics")
    service.write_text(s,encoding="utf-8")
    g=gradle.read_text(encoding="utf-8")
    g=rep(g,"        versionCode 10011","        versionCode 10012","versionCode")
    g=rep(g,"        versionName '1.0.0-rc11'","        versionName '1.0.0-rc12'","versionName")
    gradle.write_text(g,encoding="utf-8")
    checks=[(service,"info.notificationTimeout = 15L"),(service,"fastRoleAliases"),(service,'action.optInt("max_scrolls", 0)'),(gradle,"versionCode 10012"),(gradle,"versionName '1.0.0-rc12'")]
    missing=[n for p,n in checks if n not in p.read_text(encoding="utf-8")]
    if missing: raise SystemExit("Bridge RC12 incomplete: "+", ".join(missing))
    print("Furina Bridge RC12 persistent reactive runtime: OK")

if __name__=="__main__": main()
