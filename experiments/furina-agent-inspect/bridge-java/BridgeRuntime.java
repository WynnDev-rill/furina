package com.wynndev.furinaagentbridge;

import android.content.Context;

import org.json.JSONException;
import org.json.JSONObject;

public final class BridgeRuntime {
    private static final long PROCESS_STARTED_AT = System.currentTimeMillis();
    private static volatile FurinaAccessibilityService accessibility;
    private static volatile boolean foregroundAlive;
    private static volatile long accessibilityConnectedAt;
    private static volatile long accessibilityDisconnectedAt;
    private static volatile long lastAccessibilityEventAt;
    private static volatile long lastAuthorizedClientAt;
    private static volatile String lastServerError = "";

    private BridgeRuntime() {}

    public static void setAccessibility(FurinaAccessibilityService service) {
        accessibility = service;
        accessibilityConnectedAt = System.currentTimeMillis();
        lastServerError = "";
    }

    public static void clearAccessibility(FurinaAccessibilityService service) {
        if (accessibility == service) accessibility = null;
        accessibilityDisconnectedAt = System.currentTimeMillis();
    }

    public static FurinaAccessibilityService accessibility() { return accessibility; }
    public static boolean accessibilityBound() { return accessibility != null; }

    public static void markAccessibilityEvent() { lastAccessibilityEventAt = System.currentTimeMillis(); }
    public static void markAuthorizedClient() { lastAuthorizedClientAt = System.currentTimeMillis(); }
    public static long lastAuthorizedClientAt() { return lastAuthorizedClientAt; }

    public static void setForegroundAlive(boolean value) { foregroundAlive = value; }
    public static boolean foregroundAlive() { return foregroundAlive; }

    public static void setLastServerError(Throwable error) {
        lastServerError = error == null ? "" : error.toString();
    }

    public static JSONObject health(Context context) throws JSONException {
        JSONObject out = new JSONObject();
        out.put("ok", foregroundAlive);
        out.put("service", "furina-bridge");
        out.put("version", "1.0.0-rc1");
        out.put("port", 8765);
        out.put("foreground", foregroundAlive);
        out.put("accessibility", accessibilityBound());
        out.put("bootstrap_open", BridgePrefs.bootstrapOpen(context));
        out.put("last_authorized_client_at", lastAuthorizedClientAt);
        out.put("process_uptime_ms", Math.max(0, System.currentTimeMillis() - PROCESS_STARTED_AT));
        out.put("accessibility_connected_at", accessibilityConnectedAt);
        out.put("accessibility_disconnected_at", accessibilityDisconnectedAt);
        out.put("last_accessibility_event_at", lastAccessibilityEventAt);
        out.put("last_server_error", lastServerError);
        out.put("persistent_enabled", BridgePrefs.isPersistentEnabled(context));
        return out;
    }
}
