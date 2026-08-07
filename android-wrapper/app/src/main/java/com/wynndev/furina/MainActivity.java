package com.wynndev.furina;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.browser.customtabs.CustomTabsIntent;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;

import org.json.JSONObject;

import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;

/** Hardware-accelerated native shell for the Mirei virtual companion. */
public class MainActivity extends AppCompatActivity {
    /**
     * The old team-scoped hostname is protected by Vercel Authentication and
     * redirects fresh installs to vercel.com/sso-api. This public alias serves
     * the same production deployment without turning app startup into Chrome.
     */
    private static final String APP_URL = "https://furina-pi.vercel.app/";
    private static final String APP_HOST = "furina-pi.vercel.app";
    private static final String LEGACY_PROTECTED_HOST =
        "furina-indonesiafilmku-2721s-projects.vercel.app";
    private static final int BG_COLOR = Color.rgb(11, 9, 17);
    private static final int ACCENT_COLOR = Color.rgb(239, 143, 175);

    private final AtomicInteger utteranceCounter = new AtomicInteger();
    private WebView webView;
    private ProgressBar pageProgress;
    private PermissionRequest pendingMicrophoneRequest;
    private TextToSpeech textToSpeech;
    private volatile boolean textToSpeechReady;

    private final ActivityResultLauncher<String> microphonePermissionLauncher =
        registerForActivityResult(new ActivityResultContracts.RequestPermission(), granted -> {
            PermissionRequest request = pendingMicrophoneRequest;
            pendingMicrophoneRequest = null;
            if (request == null) return;
            if (granted) request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else request.deny();
        });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG_COLOR);
        getWindow().setNavigationBarColor(BG_COLOR);
        initializeJapaneseVoice();
        initializeWebApp();
        configureBackHandling();

        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(APP_URL);
        }
        handleDeepLink(getIntent());
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void initializeJapaneseVoice() {
        textToSpeech = new TextToSpeech(getApplicationContext(), status -> {
            if (status != TextToSpeech.SUCCESS || textToSpeech == null) {
                textToSpeechReady = false;
                dispatchVoiceEvent("mirei-tts-error");
                return;
            }

            int languageResult = textToSpeech.setLanguage(Locale.JAPAN);
            textToSpeechReady = languageResult != TextToSpeech.LANG_MISSING_DATA
                && languageResult != TextToSpeech.LANG_NOT_SUPPORTED;
            textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override
                public void onStart(String utteranceId) {
                    dispatchVoiceEvent("mirei-tts-start");
                }

                @Override
                public void onDone(String utteranceId) {
                    dispatchVoiceEvent("mirei-tts-done");
                }

                @Override
                public void onError(String utteranceId) {
                    dispatchVoiceEvent("mirei-tts-error");
                }

                @Override
                public void onError(String utteranceId, int errorCode) {
                    dispatchVoiceEvent("mirei-tts-error");
                }
            });
        });
    }

    private void dispatchVoiceEvent(String eventName) {
        runOnUiThread(() -> {
            if (webView == null) return;
            String script = "window.dispatchEvent(new CustomEvent(" + JSONObject.quote(eventName) + "));";
            webView.evaluateJavascript(script, null);
        });
    }

    private final class MireiVoiceBridge {
        @JavascriptInterface
        public boolean isAvailable() {
            return textToSpeechReady;
        }

        @JavascriptInterface
        public void speak(String text, float rate, float pitch) {
            if (text == null || text.trim().isEmpty()) return;
            runOnUiThread(() -> {
                if (!textToSpeechReady || textToSpeech == null) {
                    dispatchVoiceEvent("mirei-tts-error");
                    return;
                }
                textToSpeech.setSpeechRate(Math.max(0.72f, Math.min(1.3f, rate)));
                textToSpeech.setPitch(Math.max(0.82f, Math.min(1.35f, pitch)));
                String utteranceId = "mirei-" + utteranceCounter.incrementAndGet();
                int result = textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId);
                if (result == TextToSpeech.ERROR) dispatchVoiceEvent("mirei-tts-error");
            });
        }

        @JavascriptInterface
        public void stop() {
            runOnUiThread(() -> {
                if (textToSpeech != null) textToSpeech.stop();
                dispatchVoiceEvent("mirei-tts-done");
            });
        }
    }

    private void initializeWebApp() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);

        webView = new WebView(this);
        webView.setBackgroundColor(BG_COLOR);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        webView.setVerticalScrollBarEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setHapticFeedbackEnabled(true);
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, true);
        }

        root.addView(webView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        pageProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        pageProgress.setMax(100);
        pageProgress.setProgress(6);
        pageProgress.setProgressTintList(ColorStateList.valueOf(ACCENT_COLOR));
        pageProgress.setBackgroundTintList(ColorStateList.valueOf(Color.TRANSPARENT));
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(2)
        );
        progressParams.gravity = Gravity.TOP;
        root.addView(pageProgress, progressParams);

        setContentView(root);
        configureWebView();
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setLoadsImagesAutomatically(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);
        settings.setDefaultTextEncodingName("utf-8");
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBlockNetworkLoads(false);
        settings.setUserAgentString(settings.getUserAgentString() + " MireiCompanion/2.0");

        webView.addJavascriptInterface(new MireiVoiceBridge(), "MireiNative");
        WebView.setWebContentsDebuggingEnabled(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (uri == null) return true;

                String scheme = uri.getScheme() == null
                    ? ""
                    : uri.getScheme().toLowerCase(Locale.ROOT);
                String host = uri.getHost() == null
                    ? ""
                    : uri.getHost().toLowerCase(Locale.ROOT);

                if ("mirei".equals(scheme)) {
                    loadDeepLink(uri);
                    return true;
                }

                // Recover stale/protected Vercel URLs inside the app instead of Chrome.
                if (LEGACY_PROTECTED_HOST.equals(host)
                    || "vercel.com".equals(host)
                    || host.endsWith(".vercel.com")) {
                    view.loadUrl(APP_URL);
                    return true;
                }

                boolean trustedAppHost = APP_HOST.equals(host)
                    || host.endsWith(".lovable.app")
                    || host.endsWith(".supabase.co");
                if (trustedAppHost) return false;

                if ("http".equals(scheme) || "https".equals(scheme)) {
                    openInsideApp(uri);
                    return true;
                }

                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) {
                    Toast.makeText(
                        MainActivity.this,
                        "Tautan tidak dapat dibuka.",
                        Toast.LENGTH_SHORT
                    ).show();
                }
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (pageProgress != null) pageProgress.setVisibility(View.GONE);
                view.evaluateJavascript(
                    "document.documentElement.classList.add('mirei-native');",
                    null
                );
            }

            @Override
            public void onReceivedError(
                WebView view,
                WebResourceRequest request,
                WebResourceError error
            ) {
                if (!request.isForMainFrame()) return;
                if (pageProgress != null) pageProgress.setVisibility(View.GONE);
                Toast.makeText(
                    MainActivity.this,
                    "Mirei tidak dapat terhubung. Periksa jaringan lalu coba lagi.",
                    Toast.LENGTH_LONG
                ).show();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (pageProgress == null) return;
                pageProgress.setProgress(newProgress);
                pageProgress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> handleWebPermissionRequest(request));
            }
        });
    }

    /** User-initiated external links open in an in-app Custom Tab. */
    private void openInsideApp(Uri uri) {
        try {
            CustomTabsIntent tab = new CustomTabsIntent.Builder()
                .setShowTitle(true)
                .setUrlBarHidingEnabled(true)
                .build();
            tab.intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            tab.launchUrl(this, uri);
        } catch (Exception first) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
            } catch (Exception ignored) {
                Toast.makeText(MainActivity.this, "Tautan tidak dapat dibuka.", Toast.LENGTH_SHORT).show();
            }
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleDeepLink(intent);
    }

    private void loadDeepLink(Uri data) {
        if (data == null || webView == null) return;
        String fragment = data.getEncodedFragment();
        String query = data.getEncodedQuery();
        StringBuilder target = new StringBuilder(APP_URL);
        if (query != null && !query.isEmpty()) target.append('?').append(query);
        if (fragment != null && !fragment.isEmpty()) target.append('#').append(fragment);
        webView.loadUrl(target.toString());
    }

    /** mirei://auth#access_token=... hands a finished sign-in back to the WebView. */
    private void handleDeepLink(Intent intent) {
        if (intent == null || webView == null) return;
        Uri data = intent.getData();
        if (data == null || !"mirei".equalsIgnoreCase(data.getScheme())) return;
        loadDeepLink(data);
    }

    private void handleWebPermissionRequest(PermissionRequest request) {
        boolean asksForMicrophone = false;
        for (String resource : request.getResources()) {
            if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                asksForMicrophone = true;
                break;
            }
        }
        if (!asksForMicrophone) {
            request.deny();
            return;
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            return;
        }

        if (pendingMicrophoneRequest != null) pendingMicrophoneRequest.deny();
        pendingMicrophoneRequest = request;
        microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO);
    }

    private void configureBackHandling() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView != null && webView.canGoBack()) webView.goBack();
                else finish();
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
            webView.resumeTimers();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
            webView.pauseTimers();
        }
        super.onPause();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onDestroy() {
        if (pendingMicrophoneRequest != null) {
            pendingMicrophoneRequest.deny();
            pendingMicrophoneRequest = null;
        }
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
            textToSpeech = null;
            textToSpeechReady = false;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("MireiNative");
            webView.stopLoading();
            webView.loadUrl("about:blank");
            webView.clearHistory();
            webView.removeAllViews();
            webView.destroy();
            webView = null;
        }
        pageProgress = null;
        super.onDestroy();
    }
}
