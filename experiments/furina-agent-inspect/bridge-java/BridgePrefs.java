package com.wynndev.furinaagentbridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import java.security.SecureRandom;

public final class BridgePrefs {
    private static final String PREFS = "furina_bridge";
    private static final String KEY_TOKEN = "token";
    private static final String KEY_PERSISTENT = "persistent";
    private static final String KEY_BOOTSTRAP_UNTIL = "bootstrap_until";

    private BridgePrefs() {}

    public static String getToken(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String token = prefs.getString(KEY_TOKEN, null);
        if (token != null && !token.isEmpty()) return token;
        token = newToken();
        prefs.edit().putString(KEY_TOKEN, token).apply();
        return token;
    }

    public static String rotateToken(Context context) {
        String token = newToken();
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_TOKEN, token).apply();
        return token;
    }

    public static void openBootstrapWindow(Context context, long durationMs) {
        long until = System.currentTimeMillis() + Math.max(15_000L, Math.min(durationMs, 5 * 60_000L));
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putLong(KEY_BOOTSTRAP_UNTIL, until).apply();
    }

    public static boolean consumeBootstrapWindow(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long until = prefs.getLong(KEY_BOOTSTRAP_UNTIL, 0L);
        if (until <= System.currentTimeMillis()) return false;
        prefs.edit().putLong(KEY_BOOTSTRAP_UNTIL, 0L).apply();
        return true;
    }

    public static boolean bootstrapOpen(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getLong(KEY_BOOTSTRAP_UNTIL, 0L) > System.currentTimeMillis();
    }

    public static boolean isPersistentEnabled(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_PERSISTENT, true);
    }

    public static void setPersistentEnabled(Context context, boolean enabled) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_PERSISTENT, enabled).apply();
    }

    private static String newToken() {
        byte[] raw = new byte[32];
        new SecureRandom().nextBytes(raw);
        return Base64.encodeToString(raw, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    }
}
