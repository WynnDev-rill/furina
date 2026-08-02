package com.wynndev.furina;

import android.annotation.SuppressLint;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import androidx.activity.OnBackPressedCallback;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Launcher activity that keeps the hosted Smart Dashboard as the single Furina UI.
 * The FurinaNative bridge remains available inside that page, so switching between
 * Lovable AI and the local model changes only the response provider.
 */
public final class UnifiedMainActivity extends MainActivity {
    private static final String HOME_URL = "https://furina-pi.vercel.app/";
    private static final String LOCAL_URL = "file:///android_asset/offline/index.html";
    private static final String LOCAL_PREFIX = "file:///android_asset/offline/";
    private static final String LEGACY_FILE = "furina-legacy-conversations.json";
    private static final int MAX_LEGACY_BYTES = 24 * 1024 * 1024;

    private final Object migrationLock = new Object();
    private WebView unifiedWebView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        unifiedWebView = findWebView(getWindow().getDecorView());
        if (unifiedWebView == null) return;

        unifiedWebView.addJavascriptInterface(new LegacyMigrationBridge(), "FurinaMigration");
        unifiedWebView.addJavascriptInterface(new NetworkBridge(), "FurinaNetwork");
        unifiedWebView.getSettings().setCacheMode(
            hasUsableNetwork() ? WebSettings.LOAD_DEFAULT : WebSettings.LOAD_CACHE_ELSE_NETWORK
        );

        // Stage data from the old file origin before opening the hosted interface.
        unifiedWebView.setAlpha(0f);
        unifiedWebView.loadUrl(LOCAL_URL);
        unifiedWebView.postDelayed(() -> waitForLegacyStage(0), 120L);

        // Prevent Back from exposing the staging shell.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (unifiedWebView == null) {
                    finish();
                    return;
                }
                String current = unifiedWebView.getUrl();
                if (current != null && current.startsWith(LOCAL_PREFIX)) {
                    finish();
                    return;
                }
                if (unifiedWebView.canGoBack()) unifiedWebView.goBack();
                else finish();
            }
        });
    }

    private void waitForLegacyStage(int attempt) {
        if (unifiedWebView == null || isFinishing() || isDestroyed()) return;
        unifiedWebView.evaluateJavascript(
            "Boolean(window.FurinaLegacyStageReady===true)",
            result -> {
                boolean ready = "true".equalsIgnoreCase(String.valueOf(result));
                if (ready || attempt >= 30) {
                    openUnifiedInterface();
                } else {
                    unifiedWebView.postDelayed(() -> waitForLegacyStage(attempt + 1), 80L);
                }
            }
        );
    }

    private void openUnifiedInterface() {
        if (unifiedWebView == null || isFinishing() || isDestroyed()) return;
        unifiedWebView.loadUrl(HOME_URL);
        unifiedWebView.postDelayed(() -> {
            if (unifiedWebView != null) unifiedWebView.animate().alpha(1f).setDuration(220L).start();
        }, 620L);
        unifiedWebView.postDelayed(() -> {
            if (unifiedWebView == null) return;
            String current = unifiedWebView.getUrl();
            if (current != null && current.startsWith(HOME_URL)) unifiedWebView.clearHistory();
        }, 3_500L);
    }

    private WebView findWebView(View view) {
        if (view instanceof WebView) return (WebView) view;
        if (!(view instanceof ViewGroup)) return null;
        ViewGroup group = (ViewGroup) view;
        for (int index = 0; index < group.getChildCount(); index++) {
            WebView found = findWebView(group.getChildAt(index));
            if (found != null) return found;
        }
        return null;
    }

    private boolean hasUsableNetwork() {
        try {
            ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            if (manager == null) return false;
            Network network = manager.getActiveNetwork();
            if (network == null) return false;
            NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
            return capabilities != null &&
                capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } catch (Exception ignored) {
            return false;
        }
    }

    private File legacyFile() {
        return new File(getFilesDir(), LEGACY_FILE);
    }

    private final class NetworkBridge {
        @JavascriptInterface public boolean isOnline() {
            return hasUsableNetwork();
        }
    }

    private final class LegacyMigrationBridge {
        @JavascriptInterface public boolean stageLegacyConversations(String payload) {
            if (payload == null) return false;
            byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
            if (bytes.length > MAX_LEGACY_BYTES) return false;
            try {
                JSONObject root = new JSONObject(payload);
                JSONArray conversations = root.optJSONArray("conversations");
                if (conversations == null || conversations.length() > 120) return false;
                String activeId = root.optString("activeId", "");
                if (activeId.length() > 120) return false;

                synchronized (migrationLock) {
                    File target = legacyFile();
                    File temporary = new File(getFilesDir(), LEGACY_FILE + ".tmp");
                    try (FileOutputStream output = new FileOutputStream(temporary, false)) {
                        output.write(bytes);
                        output.flush();
                    }
                    if (target.exists() && !target.delete()) return false;
                    if (!temporary.renameTo(target)) {
                        try (FileOutputStream output = new FileOutputStream(target, false)) {
                            output.write(bytes);
                        }
                        temporary.delete();
                    }
                }
                return true;
            } catch (Exception ignored) {
                return false;
            }
        }

        @JavascriptInterface public String getLegacyConversations() {
            synchronized (migrationLock) {
                File source = legacyFile();
                if (!source.isFile() || source.length() <= 0 || source.length() > MAX_LEGACY_BYTES) return "";
                try (FileInputStream input = new FileInputStream(source);
                     ByteArrayOutputStream output = new ByteArrayOutputStream((int) source.length())) {
                    byte[] buffer = new byte[16 * 1024];
                    int read;
                    int total = 0;
                    while ((read = input.read(buffer)) >= 0) {
                        total += read;
                        if (total > MAX_LEGACY_BYTES) return "";
                        output.write(buffer, 0, read);
                    }
                    return output.toString(StandardCharsets.UTF_8.name());
                } catch (Exception ignored) {
                    return "";
                }
            }
        }

        @JavascriptInterface public boolean consumeLegacyConversations() {
            synchronized (migrationLock) {
                File source = legacyFile();
                return !source.exists() || source.delete();
            }
        }
    }

    @Override protected void onDestroy() {
        if (unifiedWebView != null) {
            unifiedWebView.removeJavascriptInterface("FurinaMigration");
            unifiedWebView.removeJavascriptInterface("FurinaNetwork");
        }
        super.onDestroy();
    }
}
