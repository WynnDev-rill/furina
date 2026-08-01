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
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;

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
    private static final String HOME_HOST = "furina-pi.vercel.app";
    private static final String LOCAL_URL = "file:///android_asset/offline/index.html";
    private static final String UPDATE_URL = HOME_URL + "update.json";
    private static final int BG_COLOR = Color.rgb(8, 17, 31);
    private static final String UPDATE_FILE = "Furina-update.apk";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private OfflineAiBridge offlineAiBridge;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermissionRequest;
    private boolean bridgeAttached;
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
                Intent dataIntent = result.getData();
                if (dataIntent.getClipData() != null) {
                    int count = dataIntent.getClipData().getItemCount();
                    uris = new Uri[count];
                    for (int i = 0; i < count; i++) {
                        uris[i] = dataIntent.getClipData().getItemAt(i).getUri();
                    }
                } else if (dataIntent.getData() != null) {
                    uris = new Uri[]{dataIntent.getData()};
                }
            }
            fileCallback.onReceiveValue(uris);
            fileCallback = null;
        }
    );

    private final ActivityResultLauncher<String> audioPermission = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(),
        granted -> {
            if (pendingPermissionRequest == null) return;
            if (granted) {
                pendingPermissionRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingPermissionRequest.deny();
            }
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
                verifyAndInstall(manager.getUriForDownloadedFile(downloadId));
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
        registerDownloadReceiver();
        configureBackHandling();
        initializeWebApp();
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            attachBridgeForUrl(LOCAL_URL);
            webView.loadUrl(LOCAL_URL);
        }
        checkNativeUpdate();
    }

    private void initializeWebApp() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG_COLOR);

        webView = new WebView(this);
        webView.setBackgroundColor(BG_COLOR);
        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        root.addView(
            webView,
            new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        );
        setContentView(root);
        configureWebView();
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
        settings.setUserAgentString(settings.getUserAgentString() + " FurinaAndroid/5.0");

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);
        WebView.setWebContentsDebuggingEnabled(false);

        offlineAiBridge = new OfflineAiBridge(this, webView);

        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String url = uri == null ? "" : uri.toString();
                if (isTrustedPageUrl(url)) {
                    attachBridgeForUrl(url);
                    return false;
                }
                detachBridge();
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) {}
                return true;
            }

            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                attachBridgeForUrl(url);
            }

            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                attachBridgeForUrl(url);
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) return;
                String failedUrl = request.getUrl() == null ? "" : request.getUrl().toString();
                if (failedUrl.startsWith("https://")) {
                    Toast.makeText(MainActivity.this, "Mode online tidak tersedia. Kembali ke Furina offline.", Toast.LENGTH_LONG).show();
                    attachBridgeForUrl(LOCAL_URL);
                    view.loadUrl(LOCAL_URL);
                } else {
                    showLoadError(error == null ? "Antarmuka lokal tidak dapat dimuat." : String.valueOf(error.getDescription()));
                }
            }

            @Override public void onReceivedHttpError(
                WebView view,
                WebResourceRequest request,
                WebResourceResponse response
            ) {
                if (!request.isForMainFrame()) return;
                String failedUrl = request.getUrl() == null ? "" : request.getUrl().toString();
                if (failedUrl.startsWith(HOME_URL) && response.getStatusCode() >= 500) {
                    Toast.makeText(MainActivity.this, "Server online sedang bermasalah. Mode offline tetap tersedia.", Toast.LENGTH_LONG).show();
                    attachBridgeForUrl(LOCAL_URL);
                    view.loadUrl(LOCAL_URL);
                }
            }

            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                Toast.makeText(MainActivity.this, "Koneksi online tidak aman. Kembali ke mode offline.", Toast.LENGTH_LONG).show();
                attachBridgeForUrl(LOCAL_URL);
                view.loadUrl(LOCAL_URL);
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
                runOnUiThread(() -> handleWebPermissionRequest(request));
            }
        });
    }

    private void handleWebPermissionRequest(PermissionRequest request) {
        String origin = request.getOrigin() == null ? "" : request.getOrigin().toString();
        String[] resources = request.getResources();
        boolean audioOnly = resources != null && resources.length == 1 &&
            PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resources[0]);
        if (!isTrustedPageUrl(origin) || !audioOnly) {
            request.deny();
            return;
        }

        pendingPermissionRequest = request;
        if (
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            pendingPermissionRequest = null;
        } else {
            audioPermission.launch(Manifest.permission.RECORD_AUDIO);
        }
    }

    private boolean isTrustedPageUrl(String url) {
        if (url == null) return false;
        if (url.startsWith(LOCAL_URL) || url.startsWith("file:///android_asset/offline/")) return true;
        try {
            Uri uri = Uri.parse(url);
            return "https".equalsIgnoreCase(uri.getScheme()) && HOME_HOST.equalsIgnoreCase(uri.getHost());
        } catch (Exception ignored) {
            return false;
        }
    }

    private void attachBridgeForUrl(String url) {
        if (webView == null || offlineAiBridge == null) return;
        if (!isTrustedPageUrl(url)) {
            detachBridge();
            return;
        }
        if (!bridgeAttached) {
            webView.addJavascriptInterface(offlineAiBridge, "FurinaNative");
            bridgeAttached = true;
        }
    }

    private void detachBridge() {
        if (webView != null && bridgeAttached) {
            webView.removeJavascriptInterface("FurinaNative");
            bridgeAttached = false;
        }
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
                    if (current.startsWith("https://")) {
                        attachBridgeForUrl(LOCAL_URL);
                        webView.loadUrl(LOCAL_URL);
                        return;
                    }
                }
                finish();
            }
        });
    }

    private void checkNativeUpdate() {
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(UPDATE_URL + "?t=" + System.currentTimeMillis()).openConnection();
                connection.setConnectTimeout(5_000);
                connection.setReadTimeout(5_000);
                connection.setUseCaches(false);
                connection.setRequestProperty("Cache-Control", "no-cache");
                connection.setRequestProperty("User-Agent", "Furina-Android/5.0");
                int responseCode = connection.getResponseCode();
                if (responseCode < 200 || responseCode >= 300) throw new IllegalStateException("HTTP " + responseCode);

                JSONObject json = new JSONObject(readAll(connection.getInputStream()));
                int minimumVersion = json.optInt("minimumSupportedVersionCode", 1);
                int latestVersion = json.optInt("latestVersionCode", minimumVersion);
                String apkUrl = json.optString("apkUrl", HOME_URL + "Furina.apk");
                String versionName = json.optString("versionName", String.valueOf(latestVersion));
                String notes = json.optString("notes", "Pembaruan Furina tersedia.");
                String sha256 = json.optString("sha256", "").trim().toLowerCase(Locale.US);
                int currentVersion = getCurrentVersionCode();

                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    pendingApkUrl = apkUrl;
                    expectedApkSha256 = sha256;
                    if (currentVersion < minimumVersion) {
                        updateRequired = true;
                        setRequiredUpdateGate(true);
                        showRequiredUpdateDialog(versionName, notes);
                    } else if (currentVersion < latestVersion) {
                        updateRequired = false;
                        setRequiredUpdateGate(false);
                        showOptionalUpdateDialog(versionName, notes);
                    }
                });
            } catch (Exception ignored) {
                // Offline launch must never depend on the update endpoint.
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

    private void setRequiredUpdateGate(boolean blocked) {
        if (webView != null) {
            webView.setEnabled(!blocked);
            webView.setClickable(!blocked);
            webView.setFocusable(!blocked);
        }
    }

    private void showRequiredUpdateDialog(String versionName, String notes) {
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("Pembaruan Furina diperlukan")
            .setMessage("Versi " + versionName + " harus dipasang agar aplikasi tetap kompatibel.\n\n" + notes)
            .setPositiveButton("Perbarui sekarang", (dialogInterface, which) -> beginUpdate())
            .setNeutralButton("Unduh lewat browser", (dialogInterface, which) -> openBrowserDownload())
            .setNegativeButton("Keluar", (dialogInterface, which) -> finishAndRemoveTask())
            .setOnCancelListener(dialogInterface -> finishAndRemoveTask())
            .create();
        dialog.setCancelable(false);
        dialog.setCanceledOnTouchOutside(false);
        dialog.show();
    }

    private void showOptionalUpdateDialog(String versionName, String notes) {
        new AlertDialog.Builder(this)
            .setTitle("Pembaruan Furina tersedia")
            .setMessage("Versi " + versionName + " tersedia. Model, memori, dan riwayat tidak dihapus saat APK diperbarui.\n\n" + notes)
            .setPositiveButton("Perbarui", (dialog, which) -> beginUpdate())
            .setNegativeButton("Nanti", null)
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
            File downloads = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            if (downloads == null) throw new IllegalStateException("Folder unduhan aplikasi tidak tersedia.");
            File stale = new File(downloads, UPDATE_FILE);
            if (stale.exists() && !stale.delete()) throw new IllegalStateException("File pembaruan lama tidak dapat diganti.");

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
        if (pendingApkUrl.isEmpty()) {
            showDownloadFailedDialog("Alamat unduhan belum tersedia.");
            return;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(pendingApkUrl)));
        } catch (Exception error) {
            showDownloadFailedDialog(error.getMessage());
        }
    }

    private void showDownloadFailedDialog(String reason) {
        if (isFinishing() || isDestroyed()) return;
        String details = reason == null || reason.trim().isEmpty() ? "Unduhan tidak dapat diselesaikan." : reason;
        AlertDialog.Builder builder = new AlertDialog.Builder(this)
            .setTitle("Pembaruan gagal")
            .setMessage(details + "\n\nModel offline, memori, dan riwayat tetap tersimpan di perangkat.")
            .setPositiveButton("Coba lagi", (dialog, which) -> beginUpdate())
            .setNeutralButton("Unduh lewat browser", (dialog, which) -> openBrowserDownload());
        if (updateRequired) {
            setRequiredUpdateGate(true);
            builder.setNegativeButton("Keluar", (dialog, which) -> finishAndRemoveTask()).setCancelable(false);
        } else {
            builder.setNegativeButton("Gunakan aplikasi", null);
        }
        builder.show();
    }

    private void showLoadError(String message) {
        if (isFinishing() || isDestroyed()) return;
        new AlertDialog.Builder(this)
            .setTitle("Furina tidak dapat dibuka")
            .setMessage(message)
            .setPositiveButton("Muat ulang", (dialog, which) -> {
                attachBridgeForUrl(LOCAL_URL);
                webView.loadUrl(LOCAL_URL);
            })
            .setNeutralButton("Buka versi online", (dialog, which) -> webView.loadUrl(HOME_URL))
            .setNegativeButton("Keluar", (dialog, which) -> finish())
            .show();
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

    @Override protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override protected void onDestroy() {
        if (receiverRegistered) {
            try {
                unregisterReceiver(downloadReceiver);
            } catch (Exception ignored) {}
            receiverRegistered = false;
        }
        if (pendingPermissionRequest != null) {
            pendingPermissionRequest.deny();
            pendingPermissionRequest = null;
        }
        if (fileCallback != null) {
            fileCallback.onReceiveValue(null);
            fileCallback = null;
        }
        detachBridge();
        if (offlineAiBridge != null) offlineAiBridge.destroy();
        if (webView != null) {
            webView.stopLoading();
            webView.clearHistory();
            webView.removeAllViews();
            webView.destroy();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
