package com.wynndev.furinaagentbridge;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.ColorSpace;
import android.graphics.Path;
import android.graphics.Rect;
import android.hardware.HardwareBuffer;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.Display;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.util.ArrayDeque;
import java.util.Queue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

public class FurinaAccessibilityService extends AccessibilityService {

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        BridgeRuntime.setAccessibility(this);
        BridgeForegroundService.start(this);
        BridgeForegroundService.refreshNotification();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        BridgeRuntime.markAccessibilityEvent();
    }

    @Override
    public void onInterrupt() {
        BridgeForegroundService.refreshNotification();
    }

    @Override
    public boolean onUnbind(Intent intent) {
        BridgeRuntime.clearAccessibility(this);
        BridgeForegroundService.refreshNotification();
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        BridgeRuntime.clearAccessibility(this);
        BridgeForegroundService.refreshNotification();
        super.onDestroy();
    }

    public JSONObject screenSnapshot() throws JSONException {
        JSONObject out = new JSONObject();
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return out.put("ok", false).put("error", "no_active_window");

        CharSequence pkg = root.getPackageName();
        out.put("ok", true);
        out.put("package", pkg == null ? "" : pkg.toString());
        JSONArray nodes = new JSONArray();
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        int index = 0;
        while (!q.isEmpty() && index < 350) {
            AccessibilityNodeInfo node = q.remove();
            JSONObject j = nodeToJson(node, index++);
            if (j.length() > 1) nodes.put(j);
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        out.put("nodes", nodes);
        return out;
    }

    private JSONObject nodeToJson(AccessibilityNodeInfo n, int id) throws JSONException {
        JSONObject j = new JSONObject().put("id", id);
        putText(j, "text", n.getText());
        putText(j, "desc", n.getContentDescription());
        putText(j, "view_id", n.getViewIdResourceName());
        CharSequence cls = n.getClassName();
        if (cls != null) j.put("class", shortClass(cls.toString()));
        if (n.isClickable()) j.put("clickable", true);
        if (n.isEditable()) j.put("editable", true);
        if (n.isScrollable()) j.put("scrollable", true);
        if (n.isCheckable()) j.put("checkable", true).put("checked", n.isChecked());
        Rect r = new Rect();
        n.getBoundsInScreen(r);
        if (!r.isEmpty()) j.put("bounds", new JSONArray().put(r.left).put(r.top).put(r.right).put(r.bottom));
        return j;
    }

    private void putText(JSONObject j, String key, CharSequence text) throws JSONException {
        if (text == null) return;
        String s = text.toString().trim();
        if (!s.isEmpty()) j.put(key, s.length() > 300 ? s.substring(0, 300) : s);
    }

    private String shortClass(String c) {
        int i = c.lastIndexOf('.');
        return i >= 0 ? c.substring(i + 1) : c;
    }

    public JSONObject performAction(JSONObject a) throws JSONException {
        String type = a.optString("type", "");
        boolean ok;
        switch (type) {
            case "tap_node":
                ok = tapNode(a.optInt("node", -1));
                break;
            case "tap":
                ok = tap(a.optInt("x"), a.optInt("y"));
                break;
            case "swipe":
                ok = swipe(a.optInt("x1"), a.optInt("y1"), a.optInt("x2"), a.optInt("y2"), a.optInt("duration_ms", 350));
                break;
            case "set_text":
                ok = setText(a.optInt("node", -1), a.optString("text", ""));
                break;
            case "back":
                ok = performGlobalAction(GLOBAL_ACTION_BACK);
                break;
            case "home":
                ok = performGlobalAction(GLOBAL_ACTION_HOME);
                break;
            case "recents":
                ok = performGlobalAction(GLOBAL_ACTION_RECENTS);
                break;
            case "open_app":
                ok = openApp(a.optString("package", ""));
                break;
            default:
                return new JSONObject().put("ok", false).put("error", "unsupported_action");
        }
        return new JSONObject().put("ok", ok).put("type", type);
    }

    private AccessibilityNodeInfo nodeByIndex(int target) {
        if (target < 0) return null;
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return null;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        int i = 0;
        while (!q.isEmpty() && i <= 350) {
            AccessibilityNodeInfo n = q.remove();
            if (i++ == target) return n;
            for (int c = 0; c < n.getChildCount(); c++) {
                AccessibilityNodeInfo child = n.getChild(c);
                if (child != null) q.add(child);
            }
        }
        return null;
    }

    private boolean tapNode(int id) {
        AccessibilityNodeInfo n = nodeByIndex(id);
        if (n == null) return false;
        AccessibilityNodeInfo cur = n;
        for (int i = 0; i < 5 && cur != null; i++) {
            if (cur.isClickable() && cur.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
            cur = cur.getParent();
        }
        Rect r = new Rect();
        n.getBoundsInScreen(r);
        return !r.isEmpty() && tap(r.centerX(), r.centerY());
    }

    private boolean setText(int id, String text) {
        AccessibilityNodeInfo n = nodeByIndex(id);
        if (n == null || !n.isEditable()) return false;
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        return n.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
    }

    private boolean tap(int x, int y) {
        Path p = new Path();
        p.moveTo(x, y);
        GestureDescription gd = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(p, 0, 70))
                .build();
        return dispatchGesture(gd, null, null);
    }

    private boolean swipe(int x1, int y1, int x2, int y2, int duration) {
        Path p = new Path();
        p.moveTo(x1, y1);
        p.lineTo(x2, y2);
        GestureDescription gd = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(p, 0, Math.max(100, Math.min(duration, 2000))))
                .build();
        return dispatchGesture(gd, null, null);
    }

    private boolean openApp(String pkg) {
        if (pkg == null || pkg.isEmpty()) return false;
        Intent launch = getPackageManager().getLaunchIntentForPackage(pkg);
        if (launch == null) return false;
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(launch);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public JSONObject screenshot() throws JSONException {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            return new JSONObject().put("ok", false).put("error", "android_11_required");
        }
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<String> data = new AtomicReference<>();
        AtomicReference<String> error = new AtomicReference<>();
        takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
            @Override
            public void onSuccess(ScreenshotResult result) {
                HardwareBuffer hb = result.getHardwareBuffer();
                try {
                    ColorSpace cs = result.getColorSpace();
                    Bitmap wrapped = Bitmap.wrapHardwareBuffer(hb, cs);
                    if (wrapped == null) {
                        error.set("bitmap_wrap_failed");
                        return;
                    }
                    Bitmap copy = wrapped.copy(Bitmap.Config.ARGB_8888, false);
                    ByteArrayOutputStream bos = new ByteArrayOutputStream();
                    copy.compress(Bitmap.CompressFormat.PNG, 100, bos);
                    data.set(Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP));
                    copy.recycle();
                } catch (Throwable t) {
                    error.set(t.toString());
                } finally {
                    hb.close();
                    latch.countDown();
                }
            }

            @Override
            public void onFailure(int errorCode) {
                error.set("screenshot_error_" + errorCode);
                latch.countDown();
            }
        });
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) return new JSONObject().put("ok", false).put("error", "timeout");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new JSONObject().put("ok", false).put("error", "interrupted");
        }
        if (data.get() == null) return new JSONObject().put("ok", false).put("error", error.get() == null ? "unknown" : error.get());
        return new JSONObject().put("ok", true).put("png_base64", data.get());
    }
}
