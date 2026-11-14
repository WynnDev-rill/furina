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
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public final class MainActivity extends Activity {
    // Matches the working Lovable preview URL seen in the original Furina screenshot.
    private static final String DEFAULT_URL = "https://furina.lovable.app/";
    private static final String PREFS = "furina_webview_settings";
    private static final String PREF_URL = "url";
    private static final int FILE_PICKER_REQUEST = 73;

    private WebView webView;
    private ValueCallback<Uri[]> fileResult;
    private ProgressBar loadingBar;
    private boolean errorDialogVisible = false;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(7, 17, 36));
        getWindow().setNavigationBarColor(Color.rgb(7, 17, 36));
        getWindow().getDecorView().setSystemUiVisibility(0);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(7, 17, 36));
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true); // Needed for user-selected content:// image uploads.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setSafeBrowsingEnabled(true);
        WebView.setWebContentsDebuggingEnabled(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equalsIgnoreCase(uri.getScheme())) return false;
                if ("intent".equalsIgnoreCase(uri.getScheme())) {
                    try {
                        Intent intent = Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME);
                        if (intent.resolveActivity(getPackageManager()) != null) startActivity(intent);
                    } catch (Exception ignored) { }
                }
                return true; // Never load http:// or file:// in this WebView.
            }
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showUrlDialog("Halaman Furina tidak dapat dimuat. Periksa alamat atau koneksi internet.");
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int progress) {
                loadingBar.setProgress(progress);
                loadingBar.setVisibility(progress >= 100 ? View.GONE : View.VISIBLE);
            }
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileResult != null) fileResult.onReceiveValue(null);
                fileResult = callback;
                try {
                    startActivityForResult(params.createIntent(), FILE_PICKER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException exception) {
                    fileResult = null;
                    Toast.makeText(MainActivity.this, "Tidak ada aplikasi pemilih file.", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });
        root.addView(webView, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        loadingBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        loadingBar.setMax(100);
        FrameLayout.LayoutParams barParams = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 3);
        root.addView(loadingBar, barParams);
        setContentView(root);
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(getSavedUrl());
        }

        // Long-press the Android back button to change the hosted Furina URL.
        webView.setOnLongClickListener(view -> false);
    }

    private String getSavedUrl() {
        String stored = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_URL, DEFAULT_URL);
        return isValidUrl(stored) ? stored : DEFAULT_URL;
    }

    private boolean isValidUrl(String raw) {
        try {
            Uri uri = Uri.parse(raw);
            return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null
                && !uri.getHost().isEmpty() && uri.getUserInfo() == null;
        } catch (Exception ignored) { return false; }
    }

    private void showUrlDialog(String message) {
        if (errorDialogVisible || isFinishing()) return;
        errorDialogVisible = true;
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setText(getSavedUrl());
        field.setSelectAllOnFocus(true);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        FrameLayout container = new FrameLayout(this);
        container.setPadding(padding, 0, padding, 0);
        container.addView(field);
        new AlertDialog.Builder(this)
            .setTitle("Alamat Furina")
            .setMessage(message)
            .setView(container)
            .setPositiveButton("Buka", (dialog, which) -> {
                String url = field.getText().toString().trim();
                if (isValidUrl(url)) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PREF_URL, url).apply();
                    webView.loadUrl(url);
                } else Toast.makeText(this, "Alamat harus berupa HTTPS.", Toast.LENGTH_LONG).show();
            })
            .setNegativeButton("Tutup", (dialog, which) -> {})
            .setOnDismissListener(dialog -> errorDialogVisible = false)
            .show();
    }

    @Override
    public boolean onKeyLongPress(int keyCode, android.view.KeyEvent event) {
        if (keyCode == android.view.KeyEvent.KEYCODE_BACK) {
            showUrlDialog("Ganti URL jika Furina sudah dipublikasikan ke domain baru.");
            return true;
        }
        return super.onKeyLongPress(keyCode, event);
    }

    @Override
    public boolean onKeyDown(int keyCode, android.view.KeyEvent event) {
        if (keyCode == android.view.KeyEvent.KEYCODE_BACK) {
            event.startTracking();
            if (webView.canGoBack()) { webView.goBack(); return true; }
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onActivityResult(int code, int resultCode, Intent data) {
        super.onActivityResult(code, resultCode, data);
        if (code == FILE_PICKER_REQUEST && fileResult != null) {
            fileResult.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileResult = null;
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle bundle) {
        webView.saveState(bundle);
        super.onSaveInstanceState(bundle);
    }

    @Override
    protected void onDestroy() {
        if (fileResult != null) { fileResult.onReceiveValue(null); fileResult = null; }
        webView.destroy();
        super.onDestroy();
    }
}
