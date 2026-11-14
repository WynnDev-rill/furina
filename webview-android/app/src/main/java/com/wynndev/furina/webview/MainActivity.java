package com.wynndev.furina.webview;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String HOST = "furina.lovable.app";
    private static final String HOME = "https://" + HOST + "/";
    private static final int FILE_PICKER = 73;
    private static final int NAV_COLOR = Color.rgb(8, 20, 33);

    private WebView webView;
    private FrameLayout root;
    private ProgressBar progress;
    private ValueCallback<Uri[]> fileResult;
    private AlertDialog errorDialog;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(NAV_COLOR);
        getWindow().setNavigationBarColor(NAV_COLOR);
        root = new FrameLayout(this);
        root.setBackgroundColor(NAV_COLOR);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        root.addView(progress, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
            Math.round(3 * getResources().getDisplayMetrics().density)));
        setContentView(root);
        createWebView();
        if (state == null || webView.restoreState(state) == null) {
            if (!consumeAuthReturn(getIntent())) webView.loadUrl(HOME);
        }
    }

    private void createWebView() {
        webView = new WebView(this);
        webView.setBackgroundColor(NAV_COLOR);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString() + " FurinaWebView/1.1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        root.addView(webView, 0, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return false;
                Uri uri = request.getUrl();
                if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getUserInfo() != null) return true;
                if (HOST.equalsIgnoreCase(uri.getHost()) && (uri.getPort() == -1 || uri.getPort() == 443)) {
                    if (uri.getQueryParameter("furina_android_callback") == null &&
                            !"/~oauth/initiate".equals(uri.getPath())) return false;
                }
                if (request.hasGesture() || HOST.equalsIgnoreCase(uri.getHost())) openBrowser(uri);
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showLoadError();
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse error) {
                if (request.isForMainFrame()) showLoadError();
            }

            @Override
            public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                if (view == webView) {
                    disposeWebView();
                    createWebView();
                    showLoadError();
                }
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int percent) {
                progress.setProgress(percent);
                progress.setVisibility(percent >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                completeFilePicker(null);
                fileResult = callback;
                try {
                    startActivityForResult(params.createIntent(), FILE_PICKER);
                } catch (ActivityNotFoundException ignored) {
                    completeFilePicker(null);
                    Toast.makeText(MainActivity.this, "Pemilih file tidak tersedia.", Toast.LENGTH_SHORT).show();
                }
                return true;
            }
        });
    }

    private void openBrowser(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE));
        } catch (ActivityNotFoundException ignored) {
            Toast.makeText(this, "Browser tidak tersedia.", Toast.LENGTH_SHORT).show();
        }
    }

    private void showLoadError() {
        if (isFinishing() || errorDialog != null) return;
        progress.setVisibility(View.GONE);
        errorDialog = new AlertDialog.Builder(this)
            .setTitle("Furina tidak dapat dimuat")
            .setMessage("Periksa sambungan internet, lalu coba lagi.")
            .setPositiveButton("Coba lagi", (dialog, which) -> webView.loadUrl(HOME))
            .setNeutralButton("Buka di browser", (dialog, which) -> openBrowser(Uri.parse(HOME)))
            .setNegativeButton("Tutup", (dialog, which) -> {})
            .setOnDismissListener(dialog -> errorDialog = null)
            .show();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        consumeAuthReturn(intent);
    }

    private boolean consumeAuthReturn(Intent intent) {
        Uri uri = intent.getData();
        if (uri == null || !"furina-webview".equals(uri.getScheme()) || !"auth-return".equals(uri.getHost())) return false;
        String payload = uri.getQueryParameter("payload");
        intent.setData(null);
        if (payload == null || payload.length() > 16384 || !payload.matches("[A-Za-z0-9_-]{16}\\.[A-Za-z0-9_-]+")) return false;
        webView.loadUrl(HOME + "#android-session=" + payload);
        return true;
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == FILE_PICKER) completeFilePicker(WebChromeClient.FileChooserParams.parseResult(result, data));
    }

    private void completeFilePicker(Uri[] result) {
        if (fileResult == null) return;
        ValueCallback<Uri[]> callback = fileResult;
        fileResult = null;
        callback.onReceiveValue(result);
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        webView.saveState(state);
        super.onSaveInstanceState(state);
    }

    private void disposeWebView() {
        completeFilePicker(null);
        root.removeView(webView);
        webView.destroy();
    }

    @Override
    protected void onDestroy() {
        if (errorDialog != null) errorDialog.dismiss();
        disposeWebView();
        super.onDestroy();
    }
}
