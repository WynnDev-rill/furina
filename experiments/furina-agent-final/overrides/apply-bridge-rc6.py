#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_block(path: pathlib.Path, start: str, end: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return
        raise SystemExit(f"{label}: block markers not found")
    path.write_text(text[:a] + new.rstrip() + "\n\n" + text[b:], encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-bridge-rc6.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    service = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
    gradle = root / "bridge/app/build.gradle"
    if not service.is_file() or not gradle.is_file():
        raise SystemExit("missing RC6 Bridge source")

    replace_once(
        service,
        "import java.io.ByteArrayOutputStream;\n",
        "import java.io.ByteArrayOutputStream;\nimport java.net.DatagramPacket;\nimport java.net.DatagramSocket;\nimport java.net.InetAddress;\nimport java.nio.charset.StandardCharsets;\n",
        "event network imports",
    )
    replace_once(
        service,
        "import java.util.concurrent.CountDownLatch;\n",
        "import java.util.concurrent.CountDownLatch;\nimport java.util.concurrent.ExecutorService;\nimport java.util.concurrent.Executors;\n",
        "event executor imports",
    )
    replace_once(
        service,
        "public class FurinaAccessibilityService extends AccessibilityService {\n",
        '''public class FurinaAccessibilityService extends AccessibilityService {
    private static final Object EVENT_LOCK = new Object();
    private static final ArrayDeque<JSONObject> RECENT_EVENTS = new ArrayDeque<>();
    private static long EVENT_SEQ = 0L;
    private final ExecutorService eventExecutor = Executors.newSingleThreadExecutor();
''',
        "event fields",
    )
    replace_once(
        service,
        '''    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        BridgeRuntime.markAccessibilityEvent();
    }
''',
        '''    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        BridgeRuntime.markAccessibilityEvent();
        recordEvent(event);
    }
''',
        "event capture hook",
    )
    replace_once(
        service,
        '''    @Override
    public void onDestroy() {
        BridgeRuntime.clearAccessibility(this);
        BridgeForegroundService.refreshNotification();
        super.onDestroy();
    }
''',
        '''    @Override
    public void onDestroy() {
        BridgeRuntime.clearAccessibility(this);
        BridgeForegroundService.refreshNotification();
        try { eventExecutor.shutdownNow(); } catch (Throwable ignored) {}
        super.onDestroy();
    }
''',
        "event executor cleanup",
    )
    replace_once(
        service,
        '        out.put("nodes", nodes);\n        return out;\n',
        '        out.put("nodes", nodes);\n        out.put("event_seq", currentEventSeq());\n        out.put("recent_events", recentEventsJson());\n        return out;\n',
        "screen recent events",
    )

    # Add a model-independent vertical gesture for apps that expose no scrollable node.
    replace_once(
        service,
        '''            case "scroll_node":
                ok = scrollNode(a);
                break;
            case "set_text":''',
        '''            case "scroll_node":
                ok = scrollNode(a);
                break;
            case "scroll_global":
                ok = scrollGlobal(a);
                break;
            case "set_text":''',
        "global scroll switch",
    )
    replace_once(
        service,
        '        return new JSONObject().put("ok", ok).put("type", type);\n',
        '''        JSONObject result = new JSONObject().put("ok", ok).put("type", type);
        if ("set_text".equals(type)) result.put("verified_text", ok);
        if ("swipe".equals(type) || "scroll_node".equals(type) || "scroll_global".equals(type) || "tap".equals(type)) {
            result.put("gesture_completed", ok);
        }
        return result;
''',
        "action evidence response",
    )

    replace_block(
        service,
        "    private AccessibilityNodeInfo editableNode(AccessibilityNodeInfo start) {\n",
        "    private boolean longPress(JSONObject action) {\n",
        '''    private AccessibilityNodeInfo editableNode(AccessibilityNodeInfo start) {
        AccessibilityNodeInfo cur = start;
        for (int i = 0; i < 6 && cur != null; i++) {
            if (cur.isEditable()) return cur;
            cur = cur.getParent();
        }
        if (start != null) {
            Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
            q.add(start);
            int seen = 0;
            while (!q.isEmpty() && seen++ < 90) {
                AccessibilityNodeInfo n = q.remove();
                if (n.isEditable()) return n;
                for (int i = 0; i < n.getChildCount(); i++) {
                    AccessibilityNodeInfo child = n.getChild(i);
                    if (child != null) q.add(child);
                }
            }
        }
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo only = null;
        int editableCount = 0;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 350) {
            AccessibilityNodeInfo n = q.remove();
            if (n.isEditable()) {
                if (n.isFocused()) return n;
                if (only == null) only = n;
                editableCount++;
            }
            for (int i = 0; i < n.getChildCount(); i++) {
                AccessibilityNodeInfo child = n.getChild(i);
                if (child != null) q.add(child);
            }
        }
        return editableCount == 1 ? only : null;
    }

    private boolean textMatches(AccessibilityNodeInfo n, String text) {
        if (n == null) return false;
        CharSequence cs = n.getText();
        String actual = cs == null ? "" : cs.toString();
        String expected = text == null ? "" : text;
        return actual.equals(expected) || (!expected.isEmpty() && actual.contains(expected));
    }

    private boolean setText(JSONObject action, String text) {
        AccessibilityNodeInfo n = editableNode(resolveNode(action));
        if (n == null) return false;
        if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        boolean accepted = n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
        if (accepted) {
            try { Thread.sleep(70); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            AccessibilityNodeInfo refreshed = editableNode(resolveNode(action));
            if (textMatches(refreshed != null ? refreshed : n, text)) return true;
        }
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard == null) return false;
            clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
            if (!n.isFocused()) n.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            boolean pasted = n.performAction(AccessibilityNodeInfo.ACTION_PASTE);
            if (!pasted) return false;
            try { Thread.sleep(80); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            AccessibilityNodeInfo refreshed = editableNode(resolveNode(action));
            return textMatches(refreshed != null ? refreshed : n, text);
        } catch (Throwable ignored) {
            return false;
        }
    }''',
        "verified text input",
    )

    # Insert global scroll before tap implementation, then make raw gestures await completion.
    replace_once(
        service,
        "    private boolean tap(int x, int y) {\n",
        '''    private boolean scrollGlobal(JSONObject action) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        Rect r = new Rect();
        root.getBoundsInScreen(r);
        if (r.isEmpty()) return false;
        double distance = Math.max(0.35, Math.min(action.optDouble("distance", 0.62), 0.82));
        int x = r.centerX();
        int center = r.centerY();
        int delta = Math.max(120, (int) (r.height() * distance * 0.5));
        int top = Math.max(r.top + 40, center - delta);
        int bottom = Math.min(r.bottom - 40, center + delta);
        boolean backward = "backward".equalsIgnoreCase(action.optString("direction", "forward"));
        return backward ? swipe(x, top, x, bottom, 420) : swipe(x, bottom, x, top, 420);
    }

    private boolean dispatchGestureAwait(GestureDescription gd, long timeoutMs) {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<Boolean> completed = new AtomicReference<>(false);
        boolean accepted = dispatchGesture(gd, new GestureResultCallback() {
            @Override public void onCompleted(GestureDescription gestureDescription) {
                completed.set(true); latch.countDown();
            }
            @Override public void onCancelled(GestureDescription gestureDescription) {
                completed.set(false); latch.countDown();
            }
        }, null);
        if (!accepted) return false;
        try {
            if (!latch.await(Math.max(250L, timeoutMs), TimeUnit.MILLISECONDS)) return false;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
        return Boolean.TRUE.equals(completed.get());
    }

    private boolean tap(int x, int y) {
''',
        "global scroll and gesture waiter",
    )
    replace_once(service, "        return dispatchGesture(gd, null, null);\n    }\n\n    private boolean swipe", "        return dispatchGestureAwait(gd, 1200L);\n    }\n\n    private boolean swipe", "tap completion")
    replace_once(service, "        return dispatchGesture(gd, null, null);\n    }\n\n    private boolean openApp", "        return dispatchGestureAwait(gd, 3200L);\n    }\n\n    private boolean openApp", "swipe completion")

    # Event buffer + UDP push: no polling and no model call on every event.
    replace_once(
        service,
        "    private void putText(JSONObject j, String key, CharSequence text) throws JSONException {\n",
        '''    private long currentEventSeq() {
        synchronized (EVENT_LOCK) { return EVENT_SEQ; }
    }

    private JSONArray recentEventsJson() {
        JSONArray out = new JSONArray();
        synchronized (EVENT_LOCK) {
            for (JSONObject event : RECENT_EVENTS) out.put(event);
        }
        return out;
    }

    private String eventTypeName(int type) {
        if (type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return "window";
        if (type == AccessibilityEvent.TYPE_VIEW_SCROLLED) return "scroll";
        if (type == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED) return "text";
        if (type == AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED) return "notification";
        if (type == AccessibilityEvent.TYPE_VIEW_CLICKED) return "click";
        if (type == AccessibilityEvent.TYPE_WINDOWS_CHANGED) return "windows";
        return "other";
    }

    private void recordEvent(AccessibilityEvent event) {
        if (event == null) return;
        int type = event.getEventType();
        boolean useful = type == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                || type == AccessibilityEvent.TYPE_VIEW_SCROLLED
                || type == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED
                || type == AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED
                || type == AccessibilityEvent.TYPE_VIEW_CLICKED
                || type == AccessibilityEvent.TYPE_WINDOWS_CHANGED;
        if (!useful) return;
        try {
            JSONObject j = new JSONObject();
            synchronized (EVENT_LOCK) { j.put("seq", ++EVENT_SEQ); }
            j.put("type", eventTypeName(type));
            j.put("at", System.currentTimeMillis() / 1000.0);
            if (event.getPackageName() != null) j.put("package", event.getPackageName().toString());
            if (event.getClassName() != null) j.put("class", event.getClassName().toString());
            StringBuilder text = new StringBuilder();
            for (CharSequence cs : event.getText()) {
                if (cs == null) continue;
                String s = cs.toString().trim();
                if (s.isEmpty()) continue;
                if (text.length() > 0) text.append(" | ");
                text.append(s);
                if (text.length() >= 260) break;
            }
            if (text.length() == 0 && event.getContentDescription() != null) text.append(event.getContentDescription().toString());
            if (text.length() > 0) j.put("text", text.substring(0, Math.min(260, text.length())));
            synchronized (EVENT_LOCK) {
                RECENT_EVENTS.addLast(j);
                while (RECENT_EVENTS.size() > 32) RECENT_EVENTS.removeFirst();
            }
            eventExecutor.execute(() -> sendEventUdp(j));
        } catch (Throwable ignored) {}
    }

    private void sendEventUdp(JSONObject event) {
        try (DatagramSocket socket = new DatagramSocket()) {
            byte[] data = event.toString().getBytes(StandardCharsets.UTF_8);
            DatagramPacket packet = new DatagramPacket(data, data.length, InetAddress.getByName("127.0.0.1"), 8767);
            socket.send(packet);
        } catch (Throwable ignored) {}
    }

    private void putText(JSONObject j, String key, CharSequence text) throws JSONException {
''',
        "event buffer implementation",
    )

    replace_once(gradle, "        versionCode 10005", "        versionCode 10006", "Bridge RC6 versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc5'", "        versionName '1.0.0-rc6'", "Bridge RC6 versionName")

    service_text = service.read_text(encoding="utf-8")
    gradle_text = gradle.read_text(encoding="utf-8")
    required = [
        ("verified text", 'result.put("verified_text", ok)' in service_text and "textMatches" in service_text),
        ("global scroll", 'case "scroll_global"' in service_text and "scrollGlobal(JSONObject action)" in service_text),
        ("gesture callback", "dispatchGestureAwait" in service_text and "onCompleted" in service_text),
        ("event buffer", 'out.put("recent_events"' in service_text and "recordEvent(event)" in service_text),
        ("udp event push", "DatagramSocket" in service_text and "127.0.0.1" in service_text),
        ("rc6 code", "versionCode 10006" in gradle_text),
        ("rc6 name", "versionName '1.0.0-rc6'" in gradle_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("Bridge RC6 transform incomplete: " + ", ".join(failed))
    print("Furina Bridge RC6 reliable control + event stream transform: OK")


if __name__ == "__main__":
    main()
