package com.wynndev.furina;

import android.Manifest;
import android.annotation.SuppressLint;
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
import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {
    private static final String HOME_URL = "https://furina-pi.vercel.app/";
    private static final String LOCAL_URL = "file:///android_asset/offline/index.html";
    private static final String UPDATE_URL = HOME_URL + "update.json";
    private static final int BG_COLOR = Color.rgb(8, 17, 31);
    private static final String UPDATE_FILE = "Furina-update.apk";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private SwipeRefreshLayout refresh;
    private OfflineAiBridge offlineAiBridge;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermissionRequest;
    private boolean updateRequired;
    private String pendingApkUrl = "";
    private String expectedApkSha256 = "";
    private long downloadId = -1L;
    private boolean receiverRegistered;

    private final ActivityResultLauncher<Intent> filePicker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(),
        result -> {
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
        new ActivityResultContracts.RequestPermission(),
        granted -> {
            if (pendingPermissionRequest == null) return;
            if (granted) pendingPermissionRequest.grant(pendingPermissionRequest.getResources());
            else pendingPermissionRequest.deny();
            pendingPermissionRequest = null;
        }
    );

    private final ActivityResultLauncher<Intent> installPermissionLauncher = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(),
        result -> {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || getPackageManager().canRequestPackageInstalls()) {
                startApkDownload();
            } else {
                showDownloadFailedDialog("Izin instalasi belum diberikan.");
            }
        }
    );

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            long completedId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
            if (completedId != downloadId) return;

            DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            try (Cursor cursor = manager.query(new DownloadManager.Query().setFilterById(downloadId))) {
                if (cursor == null || !cursor.moveToFirst()) {
                    showDownloadFailedDialog("Hasil unduhan tidak ditemukan.");
                    return;
                }
                int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                if (status != DownloadManager.STATUS_SUCCESSFUL) {
                    showDownloadFailedDialog("Android tidak dapat menyelesaikan unduhan.");
                    return;
                }
                Uri apkUri = manager.getUriForDownloadedFile(downloadId);
                verifyAndInstall(apkUri);
            } catch (Exception error) {
                showDownloadFailedDialog(error.getMessage());
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
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.gravity = Gravity.CENTER;
        root.addView(progress, params);
        setContentView(root);
    }

    private void checkNativeUpdate() {
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                connection.setConnectTimeout(7_000);
                connection.setReadTimeout(7_000);
                connection.setUseCaches(false);
                connection.setRequestProperty("Cache-Control", "no-cache");
                connection.setRequestProperty("User-Agent", "Furina-Android/4.0");
                int responseCode = connection.getResponseCode();
                if (responseCode < 200 || responseCode >= 300) {
                    throw new IllegalStateException("HTTP " + responseCode);
                }

                JSONObject json = new JSONObject(readAll(connection.getInputStream()));
                int minimumVersion = json.optInt("minimumSupportedVersionCode", 1);
                int latestVersion = json.optInt("latestVersionCode", minimumVersion);
                String apkUrl = json.optString("apkUrl", HOME_URL + "Furina.apk");
                String versionName = json.optString("versionName", String.valueOf(latestVersion));
                String notes = json.optString("notes", "Pembaruan Furina tersedia.");
                String sha256 = json.optString("sha256", "").trim().toLowerCase(Locale.US);
                int currentVersion = getCurrentVersionCode();

                runOnUiThread(() -> {
                    pendingApkUrl = apkUrl;
                    expectedApkSha256 = sha256;
                    if (currentVersion < minimumVersion) {
                        updateRequired = true;
                        showRequiredUpdateDialog(versionName, notes);
                    } else if (currentVersion < latestVersion) {
                        updateRequired = false;
                        showOptionalUpdateDialog(versionName, notes);
                    } else {
                        initializeLocalApp();
                    }
                });
            } catch (Exception ignored) {
                runOnUiThread(this::initializeLocalApp);
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private int getCurrentVersionCode() throws PackageManager.NameNotFoundException {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            return (int) getPackageManager().getPackageInfo(getPackageName(), 0).getLongVersionCode();
        }
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
            .setMessage("Versi " + versionName + " harus dipasang agar aplikasi tetap kompatibel.\n\n" + notes)
            .setPositiveButton("Perbarui sekarang", (d, which) -> beginUpdate())
            .setNeutralButton("Unduh lewat browser", (d, which) -> openBrowserDownload())
            .setNegativeButton("Keluar", (d, which) -> finishAndRemoveTask())
            .setOnCancelListener(d -> finishAndRemoveTask())
            .create();
        dialog.setCancelable(false);
        dialog.setCanceledOnTouchOutside(false);
        dialog.show();
    }

    private void showOptionalUpdateDialog(String versionName, String notes) {
        new AlertDialog.Builder(this)
            .setTitle("Pembaruan Furina tersedia")
            .setMessage("Versi " + versionName + " tersedia. Model dan riwayat tidak dihapus saat APK diperbarui.\n\n" + notes)
            .setPositiveButton("Perbarui", (d, which) -> beginUpdate())
            .setNegativeButton("Nanti", (d, which) -> initializeLocalApp())
            .setOnCancelListener(d -> initializeLocalApp())
            .show();
    }

    private void beginUpdate() {
        if (pendingApkUrl.isEmpty()) {
            showDownloadFailedDialog("Alamat APK tidak tersedia.");
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()) {
            installPermissionLauncher.launch(
                new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))
            );
            return;
        }
        startApkDownload();
    }

    private void startApkDownload() {
        try {
            File stale = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), UPDATE_FILE);
            if (stale.exists()) stale.delete();

            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(pendingApkUrl));
            request.setTitle("Memperbarui Furina");
            request.setDescription("Mengunduh APK resmi Furina");
            request.setMimeType("application/vnd.android.package-archive");
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setAllowedOverMetered(true);
            request.setAllowedOverRoaming(false);
            request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, UPDATE_FILE);
            downloadId = ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
            Toast.makeText(this, "Pembaruan sedang diunduh", Toast.LENGTH_LONG).show();
        } catch (Exception error) {
            showDownloadFailedDialog(error.getMessage());
        }
    }

    private void verifyAndInstall(Uri apkUri) {
        if (apkUri == null) {
            showDownloadFailedDialog("File APK tidak ditemukan.");
            return;
        }
        executor.execute(() -> {
            try {
                if (!expectedApkSha256.isEmpty()) {
                    String actual;
                    try (InputStream input = getContentResolver().openInputStream(apkUri)) {
                        if (input == null) throw new IllegalStateException("APK tidak dapat dibaca.");
                        actual = sha256(input);
                    }
                    if (!expectedApkSha256.equalsIgnoreCase(actual)) {
                        throw new IllegalStateException("Verifikasi APK gagal. File tidak akan dipasang.");
                    }
                }
                runOnUiThread(() -> openInstaller(apkUri));
            } catch (Exception error) {
                runOnUiThread(() -> showDownloadFailedDialog(error.getMessage()));
            }
        });
    }

    private String sha256(InputStream input) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[1024 * 1024];
        int read;
        while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
        StringBuilder out = new StringBuilder(64);
        for (byte value : digest.digest()) out.append(String.format(Locale.US, "%02x", value & 0xff));
        return out.toString();
    }

    private void openInstaller(Uri apkUri) {
        try {
            Intent installIntent = new Intent(Intent.ACTION_VIEW);
            installIntent.setDataAndType(apkUri, "application/vnd.android.package-archive");
            installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(installIntent);
        } catch (Exception error) {
            showDownloadFailedDialog(error.getMessage());
        }
    }

    private void openBrowserDownload() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(pendingApkUrl)));
        } catch (Exception error) {
            showDownloadFailedDialog(error.getMessage());
        }
    }

    private void showDownloadFailedDialog(String reason) {
        String details = reason == null || reason.trim().isEmpty() ? "Unduhan tidak dapat diselesaikan." : reason;
        AlertDialog.Builder builder = new AlertDialog.Builder(this)
            .setTitle("Pembaruan gagal")
            .setMessage(details + "\n\nModel offline dan riwayat tetap tersimpan di perangkat.")
            .setPositiveButton("Coba lagi", (d, which) -> beginUpdate())
            .setNeutralButton("Unduh lewat browser", (d, which) -> openBrowserDownload());
        if (updateRequired) {
            builder.setNegativeButton("Keluar", (d, which) -> finishAndRemoveTask()).setCancelable(false);
        } else {
            builder.setNegativeButton("Gunakan aplikasi", (d, which) -> initializeLocalApp());
        }
        builder.show();
    }

    private void initializeLocalApp() {
        initializeWebApp(LOCAL_URL);
    }

    private void initializeWebApp(String initialUrl) {
        updateRequired = false;
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);

        refresh = new SwipeRefreshLayout(this);
        refresh.setBackgroundColor(BG_COLOR);
        webView = new WebView(this);
        webView.setBackgroundColor(BG_COLOR);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        refresh.addView(
            webView,
            new SwipeRefreshLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        );
        root.addView(
            refresh,
            new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        );

        setContentView(root);
        refresh.setOnRefreshListener(() -> webView.reload());
        configureWebView();
        webView.loadUrl(initialUrl);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " FurinaAndroid/4.0");

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
                if ("file".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) {}
                return true;
            }

            @Override public void onPageFinished(WebView view, String url) {
                refresh.setRefreshing(false);
                CookieManager.getInstance().flush();
                refresh.setEnabled(url != null && url.startsWith(HOME_URL));
                if (url != null && url.startsWith(HOME_URL)) injectSettingsEntry(view);
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) return;
                refresh.setRefreshing(false);
                String failedUrl = request.getUrl() == null ? "" : request.getUrl().toString();
                if (failedUrl.startsWith("http")) {
                    Toast.makeText(MainActivity.this, "Mode online tidak tersedia. Kembali ke Furina lokal.", Toast.LENGTH_LONG).show();
                    view.loadUrl(LOCAL_URL);
                } else {
                    showLoadError(error == null ? "Antarmuka lokal tidak dapat dimuat." : String.valueOf(error.getDescription()));
                }
            }

            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                if (view.getUrl() != null && view.getUrl().startsWith("http")) {
                    Toast.makeText(MainActivity.this, "Koneksi online tidak aman. Kembali ke mode lokal.", Toast.LENGTH_LONG).show();
                    view.loadUrl(LOCAL_URL);
                }
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

            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    pendingPermissionRequest = request;
                    if (
                        ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) ==
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        request.grant(request.getResources());
                        pendingPermissionRequest = null;
                    } else {
                        audioPermission.launch(Manifest.permission.RECORD_AUDIO);
                    }
                });
            }
        });
    }

    private void injectSettingsEntry(WebView view) {
        String script = "(function(){" +
            "if(!window.FurinaNative||document.getElementById('furina-native-model-settings'))return;" +
            "var nodes=[].slice.call(document.querySelectorAll('section,div,main'));" +
            "var host=nodes.find(function(el){var t=(el.innerText||'').toLowerCase();return t.indexOf('pengaturan')>=0&&t.indexOf('persona')>=0&&t.indexOf('akun')>=0;});" +
            "if(!host)return;" +
            "var b=document.createElement('button');b.id='furina-native-model-settings';b.type='button';" +
            "b.textContent='Kelola Model AI Offline';" +
            "b.style.cssText='width:calc(100% - 32px);margin:16px;padding:15px 17px;border:1px solid rgba(138,216,255,.28);border-radius:16px;background:#10243b;color:#eef8ff;font:600 14px sans-serif;text-align:left';" +
            "b.onclick=function(){window.FurinaNative.openModelManager();};host.appendChild(b);" +
        "})();";
        view.evaluateJavascript(script, null);
    }

    private void showLoadError(String message) {
        new AlertDialog.Builder(this)
            .setTitle("Furina tidak dapat dibuka")
            .setMessage(message)
            .setPositiveButton("Muat ulang", (d, which) -> webView.loadUrl(LOCAL_URL))
            .setNeutralButton("Buka versi online", (d, which) -> webView.loadUrl(HOME_URL))
            .setNegativeButton("Keluar", (d, which) -> finish())
            .show();
    }

    private void configureBackHandling() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (updateRequired) {
                    finishAndRemoveTask();
                    return;
                }
                if (webView != null) {
                    String current = webView.getUrl() == null ? "" : webView.getUrl();
                    if (webView.canGoBack()) {
                        webView.goBack();
                        return;
                    }
                    if (current.startsWith("http")) {
                        webView.loadUrl(LOCAL_URL);
                        return;
                    }
                }
                finish();
            }
        });
    }

    private void registerDownloadReceiver() {
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(downloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, filter);
        }
        receiverRegistered = true;
    }

    @Override protected void onDestroy() {
        if (receiverRegistered) {
            try {
                unregisterReceiver(downloadReceiver);
            } catch (Exception ignored) {}
            receiverRegistered = false;
        }
        if (offlineAiBridge != null) offlineAiBridge.destroy();
        if (webView != null) {
            webView.removeJavascriptInterface("FurinaNative");
            webView.stopLoading();
            webView.destroy();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
