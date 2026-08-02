package com.wynndev.furina;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

/** Offline-only host. The UI is loaded exclusively from APK assets. */
public class MainActivity extends AppCompatActivity {
    private static final String LOCAL_URL = "file:///android_asset/offline/index.html";
    private static final String LOCAL_PREFIX = "file:///android_asset/offline/";
    private static final int BG_COLOR = Color.rgb(8, 17, 31);

    private WebView webView;
    private OfflineAiBridge offlineAiBridge;
    private ValueCallback<Uri[]> fileCallback;

    private final ActivityResultLauncher<Intent> filePicker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(),
        result -> {
            if (fileCallback == null) return;
            Uri[] uris = null;
            Intent data = result.getData();
            if (result.getResultCode() == Activity.RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    uris = new Uri[count];
                    for (int index = 0; index < count; index++) {
                        uris[index] = data.getClipData().getItemAt(index).getUri();
                    }
                } else if (data.getData() != null) {
                    uris = new Uri[]{data.getData()};
                }
            }
            fileCallback.onReceiveValue(uris);
            fileCallback = null;
        }
    );

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG_COLOR);
        getWindow().setNavigationBarColor(BG_COLOR);
        initializeWebApp();
        configureBackHandling();
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(LOCAL_URL);
        }
    }

    private void initializeWebApp() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);
        webView = new WebView(this);
        webView.setBackgroundColor(BG_COLOR);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        root.addView(webView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
        setContentView(root);
        configureWebView();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBlockNetworkLoads(true);
        settings.setUserAgentString(settings.getUserAgentString() + " FurinaOffline/1.0");

        WebView.setWebContentsDebuggingEnabled(false);
        offlineAiBridge = new OfflineAiBridge(this, webView);
        webView.addJavascriptInterface(offlineAiBridge, "FurinaNative");

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String url = uri == null ? "" : uri.toString();
                return !url.startsWith(LOCAL_PREFIX);
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) return;
                Toast.makeText(MainActivity.this, "Antarmuka lokal Furina tidak dapat dimuat.", Toast.LENGTH_LONG).show();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(
                WebView view,
                ValueCallback<Uri[]> callback,
                FileChooserParams params
            ) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    filePicker.launch(params.createIntent());
                } catch (Exception error) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                }
                return true;
            }
        });
    }

    private void configureBackHandling() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (webView != null && webView.canGoBack()) webView.goBack();
                else finish();
            }
        });
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override protected void onDestroy() {
        if (fileCallback != null) {
            fileCallback.onReceiveValue(null);
            fileCallback = null;
        }
        if (offlineAiBridge != null) {
            offlineAiBridge.destroy();
            offlineAiBridge = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("FurinaNative");
            webView.stopLoading();
            webView.loadUrl("about:blank");
            webView.clearHistory();
            webView.removeAllViews();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
