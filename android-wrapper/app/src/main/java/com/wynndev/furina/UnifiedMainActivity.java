package com.wynndev.furina;

import android.annotation.SuppressLint;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import androidx.activity.OnBackPressedCallback;

import java.util.Locale;

/**
 * Launcher activity that keeps the hosted Smart Dashboard as the single Furina UI.
 * The existing FurinaNative bridge remains available inside that page, so changing
 * between Lovable AI and the local model only changes the response provider.
 */
public final class UnifiedMainActivity extends MainActivity {
    private static final String HOME_URL = "https://furina-pi.vercel.app/";
    private static final String LOCAL_PREFIX = "file:///android_asset/offline/";

    private WebView unifiedWebView;
    private TextToSpeech japaneseVoice;
    private volatile boolean japaneseVoiceReady;

    @SuppressLint("SetJavaScriptEnabled")
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        unifiedWebView = findWebView(getWindow().getDecorView());
        if (unifiedWebView == null) return;

        initializeJapaneseVoice();
        unifiedWebView.addJavascriptInterface(new JapaneseVoiceBridge(), "FurinaVoice");
        unifiedWebView.getSettings().setCacheMode(
            hasUsableNetwork() ? WebSettings.LOAD_DEFAULT : WebSettings.LOAD_CACHE_ELSE_NETWORK
        );

        // MainActivity creates the secure native bridge first. We then load the
        // unified hosted shell, which can call both the online and offline engines.
        unifiedWebView.post(() -> unifiedWebView.loadUrl(HOME_URL));
        unifiedWebView.postDelayed(() -> {
            String current = unifiedWebView.getUrl();
            if (current != null && current.startsWith(HOME_URL)) unifiedWebView.clearHistory();
        }, 3_500L);

        // Prevent Android Back from exposing the old local shell that was loaded
        // briefly while MainActivity initialized its secure bridge.
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

    private void initializeJapaneseVoice() {
        japaneseVoice = new TextToSpeech(this, status -> {
            if (status != TextToSpeech.SUCCESS || japaneseVoice == null) {
                japaneseVoiceReady = false;
                return;
            }
            int result = japaneseVoice.setLanguage(Locale.JAPAN);
            japaneseVoice.setSpeechRate(1.0f);
            japaneseVoice.setPitch(1.08f);
            japaneseVoiceReady = result != TextToSpeech.LANG_MISSING_DATA &&
                result != TextToSpeech.LANG_NOT_SUPPORTED;
        });
    }

    private final class JapaneseVoiceBridge {
        @JavascriptInterface public boolean speak(String text) {
            if (!japaneseVoiceReady || japaneseVoice == null || text == null) return false;
            String safe = text.trim();
            if (safe.isEmpty()) return false;
            if (safe.length() > 4_000) safe = safe.substring(0, 4_000);
            final String utterance = safe;
            runOnUiThread(() -> japaneseVoice.speak(
                utterance,
                TextToSpeech.QUEUE_FLUSH,
                null,
                "furina-japanese-" + System.currentTimeMillis()
            ));
            return true;
        }

        @JavascriptInterface public void stop() {
            runOnUiThread(() -> {
                if (japaneseVoice != null) japaneseVoice.stop();
            });
        }

        @JavascriptInterface public boolean isReady() {
            return japaneseVoiceReady;
        }
    }

    @Override protected void onDestroy() {
        if (unifiedWebView != null) unifiedWebView.removeJavascriptInterface("FurinaVoice");
        if (japaneseVoice != null) {
            japaneseVoice.stop();
            japaneseVoice.shutdown();
            japaneseVoice = null;
        }
        super.onDestroy();
    }
}
