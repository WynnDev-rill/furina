package com.wynndev.furina;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {
    private static final String HOME_URL = "https://furina-pi.vercel.app/";
    private static final String UPDATE_URL = HOME_URL + "update.json";
    private static final int BG_COLOR = Color.rgb(8, 17, 31);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private SwipeRefreshLayout refresh;
    private OfflineAiBridge offlineAiBridge;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermissionRequest;
    private boolean updateRequired;
    private String pendingApkUrl;
    private long downloadId = -1L;
    private boolean receiverRegistered;

    private final ActivityResultLauncher<Intent> filePicker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            if (fileCallback == null) return;
            Uri[] uris = null;
            if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
                Uri data = result.getData().getData();
                if (data != null) uris = new Uri[]{data};
            }
            fileCallback.onReceiveValue(uris);
            fileCallback = null;
        }
    );

    private final ActivityResultLauncher<String> audioPermission = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(), granted -> {
            if (pendingPermissionRequest != null) {
                if (granted) pendingPermissionRequest.grant(pendingPermissionRequest.getResources());
                else pendingPermissionRequest.deny();
                pendingPermissionRequest = null;
            }
        }
    );

    private final ActivityResultLauncher<Intent> installPermissionLauncher = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || getPackageManager().canRequestPackageInstalls()) {
                startApkDownload();
            } else {
                finishAndRemoveTask();
            }
        }
    );

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            long completedId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
            if (completedId != downloadId) return;
            DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            try (Cursor cursor = manager.query(new DownloadManager.Query().setFilterById(downloadId))) {
                if (cursor != null && cursor.moveToFirst()) {
                    int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                    if (status == DownloadManager.STATUS_SUCCESSFUL) openInstaller(manager.getUriForDownloadedFile(downloadId));
                    else showDownloadFailedDialog();
                }
            }
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG_COLOR);
        getWindow().setNavigationBarColor(BG_COLOR);
        showNativeLoadingScreen();
        registerDownloadReceiver();
        configureBackHandling();
        checkNativeUpdate();
    }

    private void showNativeLoadingScreen() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);
        ProgressBar progress = new ProgressBar(this);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.gravity = Gravity.CENTER;
        root.addView(progress, params);
        setContentView(root);
    }

    private void checkNativeUpdate() {
        executor.execute(() -> {
            try {
                HttpURLConnection connection = (HttpURLConnection) new URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                connection.setConnectTimeout(7000);
                connection.setReadTimeout(7000);
                connection.setUseCaches(false);
                connection.setRequestProperty("Cache-Control", "no-cache");
                int responseCode = connection.getResponseCode();
                if (responseCode < 200 || responseCode >= 300) throw new IllegalStateException("HTTP " + responseCode);
                JSONObject json = new JSONObject(readAll(connection.getInputStream()));
                int minimumVersion = json.optInt("minimumSupportedVersionCode", 0);
                int latestVersion = json.optInt("latestVersionCode", minimumVersion);
                String apkUrl = json.optString("apkUrl", HOME_URL + "Furina.apk");
                String versionName = json.optString("versionName", String.valueOf(latestVersion));
                String notes = json.optString("notes", "Pembaruan native Android diperlukan.");
                int currentVersion = getCurrentVersionCode();
                runOnUiThread(() -> {
                    if (currentVersion < minimumVersion || currentVersion < latestVersion) {
                        updateRequired = true;
                        pendingApkUrl = apkUrl;
                        showRequiredUpdateDialog(versionName, notes);
                    } else initializeWebApp();
                });
            } catch (Exception ignored) {
                runOnUiThread(this::initializeWebApp);
            }
        });
    }

    private int getCurrentVersionCode() throws PackageManager.NameNotFoundException {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) return (int) getPackageManager().getPackageInfo(getPackageName(), 0).getLongVersionCode();
        return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
    }

    private String readAll(InputStream inputStream) throws Exception {
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) builder.append(line);
        }
        return builder.toString();
    }

    private void showRequiredUpdateDialog(String versionName, String notes) {
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("Pembaruan Furina diperlukan")
            .setMessage("Versi " + versionName + " harus dipasang sebelum aplikasi dapat digunakan.\n\n" + notes)
            .setPositiveButton("Perbarui sekarang", (d, which) -> beginForcedUpdate())
            .setNegativeButton("Keluar", (d, which) -> finishAndRemoveTask())
            .setOnCancelListener(d -> finishAndRemoveTask())
            .create();
        dialog.setCancelable(false);
        dialog.setCanceledOnTouchOutside(false);
        dialog.show();
    }

    private void beginForcedUpdate() {
        if (pendingApkUrl == null || pendingApkUrl.isEmpty()) {
            finishAndRemoveTask();
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()) {
            installPermissionLauncher.launch(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName())));
            return;
        }
        startApkDownload();
    }

    private void startApkDownload() {
        try {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(pendingApkUrl));
            request.setTitle("Memperbarui Furina");
            request.setDescription("Mengunduh pembaruan wajib");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setAllowedOverMetered(true);
            request.setAllowedOverRoaming(false);
            request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, "Furina-update.apk");
            downloadId = ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
            Toast.makeText(this, "Pembaruan sedang diunduh", Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            showDownloadFailedDialog();
        }
    }

    private void openInstaller(Uri apkUri) {
        if (apkUri == null) {
            showDownloadFailedDialog();
            return;
        }
        try {
            Intent installIntent = new Intent(Intent.ACTION_VIEW);
            installIntent.setDataAndType(apkUri, "application/vnd.android.package-archive");
            installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(installIntent);
        } catch (Exception e) {
            showDownloadFailedDialog();
        }
    }

    private void showDownloadFailedDialog() {
        new AlertDialog.Builder(this)
            .setTitle("Pembaruan gagal diunduh")
            .setMessage("Coba unduh kembali. Aplikasi tidak dapat digunakan sebelum pembaruan selesai.")
            .setPositiveButton("Coba lagi", (d, which) -> beginForcedUpdate())
            .setNegativeButton("Keluar", (d, which) -> finishAndRemoveTask())
            .setCancelable(false)
            .show();
    }

    private void initializeWebApp() {
        updateRequired = false;
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);

        refresh = new SwipeRefreshLayout(this);
        refresh.setBackgroundColor(BG_COLOR);
        webView = new WebView(this);
        webView.setBackgroundColor(BG_COLOR);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        refresh.addView(webView, new SwipeRefreshLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        root.addView(refresh, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        TextView modelButton = new TextView(this);
        modelButton.setText("Model AI");
        modelButton.setTextColor(Color.rgb(238, 248, 255));
        modelButton.setTextSize(13);
        modelButton.setGravity(Gravity.CENTER);
        modelButton.setPadding(dp(15), dp(10), dp(15), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(12, 30, 50));
        background.setCornerRadius(dp(16));
        background.setStroke(dp(1), Color.argb(80, 160, 220, 255));
        modelButton.setBackground(background);
        modelButton.setElevation(dp(8));
        modelButton.setContentDescription("Buka pengelola model AI offline");
        modelButton.setOnClickListener(v -> startActivity(new Intent(this, ModelManagerActivity.class)));
        FrameLayout.LayoutParams buttonParams = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        buttonParams.gravity = Gravity.END | Gravity.BOTTOM;
        buttonParams.setMargins(dp(16), dp(16), dp(16), dp(82));
        root.addView(modelButton, buttonParams);

        setContentView(root);
        refresh.setOnRefreshListener(() -> webView.reload());
        configureWebView();
        webView.loadUrl(HOME_URL);
    }

    private void configureWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setUserAgentString(s.getUserAgentString() + " FurinaAndroid/3.1");

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);
        WebView.setWebContentsDebuggingEnabled(false);

        offlineAiBridge = new OfflineAiBridge(this, webView);
        webView.addJavascriptInterface(offlineAiBridge, "FurinaNative");

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String scheme = uri.getScheme();
                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) {}
                return true;
            }

            @Override public void onPageFinished(WebView view, String url) {
                refresh.setRefreshing(false);
                CookieManager.getInstance().flush();
                injectSettingsEntry(view);
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    refresh.setRefreshing(false);
                    showLoadError(error != null ? String.valueOf(error.getDescription()) : "Tidak dapat memuat aplikasi");
                }
            }

            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                showLoadError("Koneksi aman ke server gagal");
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { filePicker.launch(params.createIntent()); }
                catch (Exception e) {
                    fileCallback.onReceiveValue(null);
                    fileCallback = null;
                }
                return true;
            }

            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    pendingPermissionRequest = request;
                    if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(request.getResources());
                        pendingPermissionRequest = null;
                    } else audioPermission.launch(Manifest.permission.RECORD_AUDIO);
                });
            }
        });
    }

    private void injectSettingsEntry(WebView view) {
        String script = "(function(){if(window.__furinaModelHook)return;window.__furinaModelHook=true;" +
            "function mount(){if(!window.FurinaNative||!document.body)return;var id='furina-native-model-settings';if(document.getElementById(id))return;" +
            "var text=(document.body.innerText||'').toLowerCase();var route=(location.pathname+location.hash).toLowerCase();" +
            "var settings=text.indexOf('pengaturan')>=0||text.indexOf('settings')>=0||route.indexOf('setting')>=0||route.indexOf('pengaturan')>=0;if(!settings)return;" +
            "var b=document.createElement('button');b.id=id;b.type='button';b.textContent='Model AI Offline';" +
            "b.style.cssText='width:calc(100% - 32px);margin:12px 16px;padding:14px;border:1px solid rgba(138,216,255,.35);border-radius:16px;background:rgba(12,30,50,.96);color:#eef8ff;font:600 14px sans-serif';" +
            "b.onclick=function(){window.FurinaNative.openModelManager()};document.body.appendChild(b)}" +
            "mount();setInterval(mount,1000);new MutationObserver(mount).observe(document.documentElement,{subtree:true,childList:true,characterData:true});})();";
        view.evaluateJavascript(script, null);
    }

    private void configureBackHandling() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (updateRequired) finishAndRemoveTask();
                else if (webView != null && webView.canGoBack()) webView.goBack();
                else finish();
            }
        });
    }

    private void showLoadError(String reason) {
        String safeReason = reason.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
        String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>" +
            "<style>body{margin:0;background:#08111f;color:#eef6ff;font-family:sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center}.box{padding:28px;max-width:420px}h2{margin:0 0 12px}p{opacity:.78;line-height:1.5}button{margin-top:14px;padding:12px 22px;border:0;border-radius:12px;background:#8ad8ff;color:#07111e;font-weight:700}</style></head>" +
            "<body><div class='box'><h2>Furina tidak dapat dimuat</h2><p>" + safeReason + "</p><button onclick=\"location.href='" + HOME_URL + "'\">Coba lagi</button></div></body></html>";
        webView.loadDataWithBaseURL(HOME_URL, html, "text/html", "UTF-8", null);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void registerDownloadReceiver() {
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) registerReceiver(downloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(downloadReceiver, filter);
        receiverRegistered = true;
    }

    @Override protected void onDestroy() {
        if (receiverRegistered) {
            try { unregisterReceiver(downloadReceiver); } catch (Exception ignored) {}
            receiverRegistered = false;
        }
        executor.shutdownNow();
        if (offlineAiBridge != null) {
            offlineAiBridge.destroy();
            offlineAiBridge = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("FurinaNative");
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
        }
        super.onDestroy();
    }
}
