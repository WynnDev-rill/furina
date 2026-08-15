package com.wynndev.furinaagentbridge;

import android.Manifest;
import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.provider.OpenableColumns;
import android.provider.MediaStore;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.util.Base64;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String HUB_URL = "http://127.0.0.1:8787/";
    private static final String APP_ORIGIN = "https://app.furinahub.local/";
    private static final String RUN_COMMAND = "com.termux.permission.RUN_COMMAND";
    private static final String RUN_COMMAND_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT";
    private static final String TERMUX_RESULT_ACTION = "com.wynndev.furinaagentbridge.CORE_UPDATE_RESULT";
    private static final String CORE_RECOVERY_COMMAND =
            "set -o pipefail; target=\"$HOME/.furina-agent/run/furinahub-native-update.sh\"; " +
            "url='https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh'; " +
            "mkdir -p \"$(dirname \"$target\")\"; " +
            "if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 4 \"$url\" -o \"$target\"; " +
            "elif command -v python >/dev/null 2>&1; then python -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1],sys.argv[2])' \"$url\" \"$target\"; " +
            "else echo 'curl dan python tidak tersedia di Termux' >&2; exit 127; fi; " +
            "bash \"$target\" --update";
    private static final int REQ_NOTIFICATION = 22;
    private static final int REQ_RUN_COMMAND = 23;
    private static final int REQ_PICK_ATTACHMENT = 24;
    private static final int REQ_PICK_IMAGE = 25;
    private static final int REQ_CAMERA = 26;
    private static final int MAX_ATTACHMENT_BYTES = 1_500_000;
    private static final int MAX_IMAGE_BYTES = 6_000_000;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private WebView web;
    private BridgeUpdater bridgeUpdater;
    private TextView hiddenUpdateStatus;
    private Button hiddenUpdateButton;
    private SharedPreferences prefs;

    private volatile String hubToken = "";
    private volatile String connectionState = "disconnected";
    private volatile String connectionMessage = "Furina Core belum terhubung.";
    private volatile boolean connectionBusy;
    private volatile String appUpdateState = "Belum diperiksa.";
    private volatile boolean appUpdateBusy;
    private volatile String coreUpdateState = "Belum diperiksa.";
    private volatile boolean coreUpdateBusy;
    private volatile boolean pendingCoreUpdatePermission;

    private final BroadcastReceiver termuxResultReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (intent == null || !TERMUX_RESULT_ACTION.equals(intent.getAction())) return;
            Bundle result = intent.getBundleExtra("result");
            int exitCode = result == null ? -1 : result.getInt("exitCode", -1);
            String stdout = result == null ? "" : String.valueOf(result.getString("stdout", ""));
            String stderr = result == null ? "" : String.valueOf(result.getString("stderr", ""));
            handleCoreUpdateResult(exitCode, stdout, stderr);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("furinahub", MODE_PRIVATE);
        IntentFilter resultFilter = new IntentFilter(TERMUX_RESULT_ACTION);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(termuxResultReceiver, resultFilter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(termuxResultReceiver, resultFilter);
        BridgeForegroundService.start(this);
        requestNotificationsIfNeeded();
        setContentView(buildRoot());
        bridgeUpdater = new BridgeUpdater(this, hiddenUpdateStatus, hiddenUpdateButton);
        loadBundledShell();
        probeSavedCore();
    }

    @Override
    protected void onResume() {
        super.onResume();
        BridgePrefs.openBootstrapWindow(this, 120_000L);
        if (bridgeUpdater != null) bridgeUpdater.onResume();
        if (web != null) web.evaluateJavascript("window.FurinaHubNative&&window.FurinaHubNative.onResume&&window.FurinaHubNative.onResume()", null);
    }

    @Override
    protected void onDestroy() {
        try { unregisterReceiver(termuxResultReceiver); } catch (Throwable ignored) { }
        if (web != null) {
            web.removeJavascriptInterface("FurinaNative");
            web.destroy();
        }
        io.shutdownNow();
        super.onDestroy();
    }

    private FrameLayout buildRoot() {
        FrameLayout root = new FrameLayout(this);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(false);
        if (Build.VERSION.SDK_INT >= 21) s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new NativeApi(), "FurinaNative");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !request.getUrl().toString().startsWith(APP_ORIGIN);
            }
            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return url == null || !url.startsWith(APP_ORIGIN);
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        hiddenUpdateStatus = new TextView(this);
        hiddenUpdateStatus.setVisibility(TextView.GONE);
        hiddenUpdateButton = new Button(this);
        hiddenUpdateButton.setVisibility(Button.GONE);
        root.addView(hiddenUpdateStatus, new FrameLayout.LayoutParams(1, 1));
        root.addView(hiddenUpdateButton, new FrameLayout.LayoutParams(1, 1));
        return root;
    }

    private void loadBundledShell() {
        try (InputStream in = getAssets().open("furinahub/index.html"); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
            String html = out.toString("UTF-8");
            web.loadDataWithBaseURL(APP_ORIGIN, html, "text/html", "UTF-8", null);
        } catch (Throwable t) {
            Toast.makeText(this, "UI FurinaHub tidak dapat dimuat.", Toast.LENGTH_LONG).show();
        }
    }

    private void probeSavedCore() {
        final String saved = prefs.getString("hub_token", "");
        if (saved == null || saved.length() < 24) {
            setConnection("disconnected", "Furina Core belum terhubung.", false);
            return;
        }
        io.execute(() -> {
            if (health(saved)) {
                hubToken = saved;
                setConnection("connected", "Furina Core terhubung.", false);
            } else {
                setConnection("disconnected", "Core tidak aktif. Hubungkan kembali dari Pengaturan.", false);
            }
        });
    }

    private void beginConnect() {
        if (connectionBusy) return;
        pendingCoreUpdatePermission = false;
        if (!isTermuxInstalled()) {
            setConnection("termux_missing", "Termux belum terpasang.", false);
            return;
        }
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_COMMAND) != PackageManager.PERMISSION_GRANTED) {
            setConnection("permission_required", "Izinkan FurinaHub menjalankan Furina Core melalui Termux.", false);
            requestPermissions(new String[]{RUN_COMMAND}, REQ_RUN_COMMAND);
            return;
        }
        startCoreConnection();
    }

    private void startCoreConnection() {
        if (connectionBusy) return;
        connectionBusy = true;
        setConnection("connecting", "Menyalakan Furina Core…", true);
        final String token = UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "");
        io.execute(() -> {
            try {
                runFixedTermux("/data/data/com.termux/files/usr/bin/furina-hub", new String[]{"--replace", "--token", token});
            } catch (SecurityException security) {
                setConnection("permission_required", "Izin Run commands in Termux environment belum diberikan.", false);
                return;
            } catch (Throwable t) {
                setConnection("termux_blocked", "Termux menolak integrasi. Jalankan installer FurinaHub sekali dari Termux.", false);
                return;
            }

            long deadline = System.currentTimeMillis() + 35_000L;
            while (System.currentTimeMillis() < deadline && !Thread.currentThread().isInterrupted()) {
                if (health(token)) {
                    hubToken = token;
                    prefs.edit().putString("hub_token", token).apply();
                    setConnection("connected", "Furina Core terhubung.", false);
                    return;
                }
                try { Thread.sleep(650L); } catch (InterruptedException e) { return; }
            }
            setConnection("core_start_failed", "Core belum merespons. Buka Termux sekali, lalu coba Hubungkan lagi.", false);
        });
    }

    private void setConnection(String state, String message, boolean busy) {
        connectionState = state;
        connectionMessage = message;
        connectionBusy = busy;
        handler.post(this::notifyShellConnection);
    }

    private void notifyShellConnection() {
        if (web == null) return;
        String payload = connectionStatusJson();
        String js = "window.FurinaHubNative&&window.FurinaHubNative.onConnectionChanged(" + JSONObject.quote(payload) + ")";
        web.evaluateJavascript(js, null);
    }

    private String connectionStatusJson() {
        try {
            JSONObject o = new JSONObject();
            o.put("state", connectionState);
            o.put("message", connectionMessage);
            o.put("busy", connectionBusy);
            o.put("connected", "connected".equals(connectionState));
            o.put("termux_installed", isTermuxInstalled());
            o.put("run_command_granted", Build.VERSION.SDK_INT < 23 || checkSelfPermission(RUN_COMMAND) == PackageManager.PERMISSION_GRANTED);
            return o.toString();
        } catch (Throwable ignored) {
            return "{\"state\":\"error\",\"connected\":false}";
        }
    }

    private boolean isTermuxInstalled() {
        try {
            getPackageManager().getPackageInfo("com.termux", 0);
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private boolean health(String token) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(HUB_URL + "health?access=" + token).openConnection();
            c.setConnectTimeout(900);
            c.setReadTimeout(900);
            c.setUseCaches(false);
            return c.getResponseCode() == 200;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private String coreRequest(String method, String path, String body) throws Exception {
        if (hubToken == null || hubToken.length() < 24 || !path.startsWith("/api/")) {
            throw new IllegalStateException("Furina Core belum terhubung");
        }
        String m = String.valueOf(method == null ? "GET" : method).toUpperCase(Locale.ROOT);
        if (!m.equals("GET") && !m.equals("POST")) throw new IllegalArgumentException("method tidak didukung");
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL("http://127.0.0.1:8787" + path).openConnection();
            c.setConnectTimeout(2500);
            c.setReadTimeout(300_000);
            c.setUseCaches(false);
            c.setRequestMethod(m);
            c.setRequestProperty("X-FurinaHub-Token", hubToken);
            c.setRequestProperty("Accept", "application/json");
            if (m.equals("POST")) {
                byte[] data = String.valueOf(body == null ? "{}" : body).getBytes(StandardCharsets.UTF_8);
                if (data.length > 2_000_000) throw new IllegalArgumentException("request terlalu besar");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                c.setFixedLengthStreamingMode(data.length);
                try (OutputStream out = c.getOutputStream()) { out.write(data); }
            }
            int code = c.getResponseCode();
            InputStream stream = code >= 200 && code < 400 ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            if (stream != null) {
                byte[] buf = new byte[8192]; int n;
                while ((n = stream.read(buf)) >= 0) out.write(buf, 0, n);
                stream.close();
            }
            String response = out.toString("UTF-8");
            if (code == 401 || code == 403) {
                setConnection("disconnected", "Sesi Core berakhir. Hubungkan kembali.", false);
            }
            if (code < 200 || code >= 300) throw new IllegalStateException(response.isEmpty() ? "HTTP " + code : response);
            return response.isEmpty() ? "{}" : response;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void runFixedTermux(String path, String[] args) {
        Intent intent = new Intent();
        intent.setComponent(new ComponentName("com.termux", "com.termux.app.RunCommandService"));
        intent.setAction("com.termux.RUN_COMMAND");
        intent.putExtra("com.termux.RUN_COMMAND_PATH", path);
        intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args);
        intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
        intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
        startService(intent);
    }

    private void runTermuxWithResult(String path, String[] args) {
        Intent callback = new Intent(TERMUX_RESULT_ACTION).setPackage(getPackageName());
        int flags = PendingIntent.FLAG_CANCEL_CURRENT;
        if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
        PendingIntent pending = PendingIntent.getBroadcast(this, 38022, callback, flags);
        Intent intent = new Intent();
        intent.setComponent(new ComponentName("com.termux", "com.termux.app.RunCommandService"));
        intent.setAction("com.termux.RUN_COMMAND");
        intent.putExtra("com.termux.RUN_COMMAND_PATH", path);
        intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args);
        intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
        intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
        intent.putExtra(RUN_COMMAND_PENDING_INTENT, pending);
        startService(intent);
    }

    private void startCoreRecoveryUpdate() {
        if (coreUpdateBusy) return;
        if (!isTermuxInstalled()) {
            coreUpdateState = "Termux belum terpasang.";
            return;
        }
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_COMMAND) != PackageManager.PERMISSION_GRANTED) {
            coreUpdateState = "Izin RUN_COMMAND Termux diperlukan.";
            pendingCoreUpdatePermission = true;
            requestPermissions(new String[]{RUN_COMMAND}, REQ_RUN_COMMAND);
            return;
        }
        coreUpdateBusy = true;
        coreUpdateState = "Menjalankan recovery updater langsung di Termux…";
        try {
            runTermuxWithResult("/data/data/com.termux/files/usr/bin/bash", new String[]{"-lc", CORE_RECOVERY_COMMAND});
            handler.postDelayed(() -> {
                if (coreUpdateBusy) {
                    coreUpdateBusy = false;
                    coreUpdateState = "Updater tidak mengirim hasil dalam 15 menit. Buka Termux untuk melihat prosesnya.";
                }
            }, 900_000L);
        } catch (Throwable error) {
            coreUpdateBusy = false;
            coreUpdateState = "Termux menolak updater: " + String.valueOf(error.getMessage());
        }
    }

    private static String usefulTail(String stdout, String stderr) {
        String raw = (String.valueOf(stdout) + "\n" + String.valueOf(stderr))
                .replaceAll("\\u001B\\[[;\\d]*[ -/]*[@-~]", "")
                .replace('\r', '\n');
        String[] lines = raw.split("\\n");
        StringBuilder out = new StringBuilder();
        for (int i = Math.max(0, lines.length - 8); i < lines.length; i++) {
            String line = lines[i].trim().replaceAll("\\s+", " ");
            if (line.isEmpty()) continue;
            if (out.length() > 0) out.append(" · ");
            out.append(line);
        }
        String value = out.toString();
        return value.length() > 560 ? value.substring(value.length() - 560) : value;
    }

    private void handleCoreUpdateResult(int exitCode, String stdout, String stderr) {
        coreUpdateBusy = false;
        if (exitCode != 0) {
            String detail = usefulTail(stdout, stderr);
            coreUpdateState = "Update gagal (kode " + exitCode + ")" + (detail.isEmpty() ? "." : ": " + detail);
            return;
        }
        coreUpdateState = "Core & dependency diperbarui. Menghubungkan ulang Core…";
        final String token = hubToken == null || hubToken.length() < 24
                ? UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "")
                : hubToken;
        io.execute(() -> {
            try {
                runFixedTermux("/data/data/com.termux/files/usr/bin/furina-hub", new String[]{"--replace", "--token", token});
                long deadline = System.currentTimeMillis() + 35_000L;
                while (System.currentTimeMillis() < deadline && !Thread.currentThread().isInterrupted()) {
                    if (health(token)) {
                        hubToken = token;
                        prefs.edit().putString("hub_token", token).apply();
                        coreUpdateState = "Core & dependency berhasil diperbarui dan terhubung.";
                        setConnection("connected", "Furina Core terhubung.", false);
                        return;
                    }
                    try { Thread.sleep(650L); } catch (InterruptedException stop) { return; }
                }
                coreUpdateState = "Update selesai, tetapi Core belum terhubung kembali. Tekan Hubungkan ulang.";
            } catch (Throwable error) {
                coreUpdateState = "Update selesai; hubungkan ulang Core: " + String.valueOf(error.getMessage());
            }
        });
    }

    private void openTermux() {
        try {
            Intent launch = getPackageManager().getLaunchIntentForPackage("com.termux");
            if (launch != null) startActivity(launch);
        } catch (Throwable ignored) { }
    }

    private void pickAttachment() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"text/plain", "text/markdown", "text/csv", "application/json"});
        startActivityForResult(intent, REQ_PICK_ATTACHMENT);
    }

    private void pickImage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
        startActivityForResult(intent, REQ_PICK_IMAGE);
    }

    private void takePhoto() {
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        if (intent.resolveActivity(getPackageManager()) == null) {
            Toast.makeText(this, "Aplikasi kamera tidak tersedia.", Toast.LENGTH_LONG).show();
            return;
        }
        startActivityForResult(intent, REQ_CAMERA);
    }

    private void openConnectorConsole(String rawUrl) {
        try {
            Uri uri = Uri.parse(String.valueOf(rawUrl));
            String host = uri.getHost();
            if (!"http".equalsIgnoreCase(uri.getScheme()) || !("127.0.0.1".equals(host) || "localhost".equalsIgnoreCase(host))) {
                throw new IllegalArgumentException("Console OpenConnector harus memakai alamat loopback HTTP.");
            }
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Throwable error) {
            Toast.makeText(this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show();
        }
    }

    private void readAttachment(Uri uri) {
        io.execute(() -> {
            try {
                String name = "lampiran.txt";
                long declared = -1L;
                try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) {
                        int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                        int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                        if (nameIndex >= 0) name = cursor.getString(nameIndex);
                        if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) declared = cursor.getLong(sizeIndex);
                    }
                }
                if (declared > MAX_ATTACHMENT_BYTES) throw new IllegalArgumentException("Lampiran maksimal 1,5 MB.");
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                try (InputStream in = getContentResolver().openInputStream(uri)) {
                    if (in == null) throw new IllegalArgumentException("Lampiran tidak dapat dibuka.");
                    byte[] buffer = new byte[8192]; int read; int total = 0;
                    while ((read = in.read(buffer)) >= 0) {
                        total += read;
                        if (total > MAX_ATTACHMENT_BYTES) throw new IllegalArgumentException("Lampiran maksimal 1,5 MB.");
                        out.write(buffer, 0, read);
                    }
                }
                byte[] bytes = out.toByteArray();
                String content = new String(bytes, StandardCharsets.UTF_8);
                if (content.indexOf('\u0000') >= 0) throw new IllegalArgumentException("Hanya file teks yang didukung pada rilis ini.");
                JSONObject payload = new JSONObject();
                payload.put("name", name == null ? "lampiran.txt" : name);
                payload.put("size", bytes.length);
                payload.put("mime", String.valueOf(getContentResolver().getType(uri)));
                payload.put("content", content);
                payload.put("kind", "text");
                emitMedia(payload);
            } catch (Throwable error) {
                handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
            }
        });
    }

    private void readImage(Uri uri) {
        io.execute(() -> {
            try {
                String name = "gambar";
                long declared = -1L;
                try (Cursor cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) {
                        int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                        int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                        if (nameIndex >= 0) name = cursor.getString(nameIndex);
                        if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) declared = cursor.getLong(sizeIndex);
                    }
                }
                if (declared > MAX_IMAGE_BYTES) throw new IllegalArgumentException("Gambar maksimal 6 MB.");
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                try (InputStream in = getContentResolver().openInputStream(uri)) {
                    if (in == null) throw new IllegalArgumentException("Gambar tidak dapat dibuka.");
                    byte[] buffer = new byte[8192]; int read; int total = 0;
                    while ((read = in.read(buffer)) >= 0) {
                        total += read;
                        if (total > MAX_IMAGE_BYTES) throw new IllegalArgumentException("Gambar maksimal 6 MB.");
                        out.write(buffer, 0, read);
                    }
                }
                String mime = String.valueOf(getContentResolver().getType(uri));
                if (!("image/jpeg".equals(mime) || "image/png".equals(mime) || "image/webp".equals(mime))) {
                    throw new IllegalArgumentException("Gunakan gambar JPEG, PNG, atau WebP.");
                }
                emitImage(name, mime, out.toByteArray());
            } catch (Throwable error) {
                handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
            }
        });
    }

    private void emitImage(String name, String mime, byte[] bytes) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("kind", "image");
        payload.put("name", name == null ? "gambar" : name);
        payload.put("size", bytes.length);
        payload.put("mime", mime);
        payload.put("base64", Base64.encodeToString(bytes, Base64.NO_WRAP));
        emitMedia(payload);
    }

    private void emitMedia(JSONObject payload) {
        String js = "window.FurinaHubNative&&window.FurinaHubNative.onMediaPicked(" + JSONObject.quote(payload.toString()) + ")";
        handler.post(() -> web.evaluateJavascript(js, null));
    }

    private void replyToShell(String requestId, boolean ok, String payload) {
        handler.post(() -> {
            if (web == null) return;
            String js = "window.FurinaHubNative&&window.FurinaHubNative.resolveRequest(" +
                    JSONObject.quote(requestId) + "," + (ok ? "true" : "false") + "," + JSONObject.quote(payload) + ")";
            web.evaluateJavascript(js, null);
        });
    }

    private void monitorAppUpdate(int attempt) {
        if (bridgeUpdater == null) {
            appUpdateBusy = false;
            appUpdateState = "Updater belum siap.";
            return;
        }
        String message = String.valueOf(hiddenUpdateStatus.getText());
        String button = String.valueOf(hiddenUpdateButton.getText());
        if (message != null && !message.trim().isEmpty()) appUpdateState = message.trim();
        if (hiddenUpdateButton.isEnabled()) {
            if (button.startsWith("Perbarui ke ")) {
                hiddenUpdateButton.setEnabled(false);
                bridgeUpdater.checkOrInstall();
                handler.postDelayed(() -> monitorAppUpdate(attempt + 1), 500L);
                return;
            }
            appUpdateBusy = false;
            return;
        }
        if (button.contains("Installer dibuka")) { appUpdateBusy = false; return; }
        if (attempt >= 120) {
            appUpdateBusy = false;
            if (appUpdateState.startsWith("Memeriksa")) appUpdateState = "Pemeriksaan update membutuhkan waktu terlalu lama.";
            return;
        }
        handler.postDelayed(() -> monitorAppUpdate(attempt + 1), 500L);
    }

    private void requestNotificationsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATION);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_RUN_COMMAND) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            boolean update = pendingCoreUpdatePermission;
            pendingCoreUpdatePermission = false;
            if (granted && update) startCoreRecoveryUpdate();
            else if (granted) startCoreConnection();
            else setConnection("permission_required", "Izin Termux diperlukan agar FurinaHub dapat menyalakan Core.", false);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK_ATTACHMENT && resultCode == RESULT_OK && data != null && data.getData() != null) {
            readAttachment(data.getData());
        } else if (requestCode == REQ_PICK_IMAGE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            readImage(data.getData());
        } else if (requestCode == REQ_CAMERA && resultCode == RESULT_OK && data != null && data.getExtras() != null) {
            Object raw = data.getExtras().get("data");
            if (raw instanceof Bitmap) {
                io.execute(() -> {
                    try {
                        ByteArrayOutputStream out = new ByteArrayOutputStream();
                        ((Bitmap) raw).compress(Bitmap.CompressFormat.JPEG, 92, out);
                        emitImage("kamera.jpg", "image/jpeg", out.toByteArray());
                    } catch (Throwable error) {
                        handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
                    }
                });
            }
        }
    }

    public class NativeApi {
        @JavascriptInterface public String connectionStatus() { return connectionStatusJson(); }

        @JavascriptInterface public void connectCore() { handler.post(MainActivity.this::beginConnect); }

        @JavascriptInterface public void openTermux() { handler.post(MainActivity.this::openTermux); }

        @JavascriptInterface public void openAccessibility() {
            handler.post(() -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        }

        @JavascriptInterface public void pickAttachment() { handler.post(MainActivity.this::pickAttachment); }

        @JavascriptInterface public void pickImage() { handler.post(MainActivity.this::pickImage); }

        @JavascriptInterface public void takePhoto() { handler.post(MainActivity.this::takePhoto); }

        @JavascriptInterface public void openConnectorConsole(String url) { handler.post(() -> MainActivity.this.openConnectorConsole(url)); }

        @JavascriptInterface public void coreRequest(String requestId, String method, String path, String body) {
            if (requestId == null || requestId.length() > 80) return;
            io.execute(() -> {
                try { replyToShell(requestId, true, MainActivity.this.coreRequest(method, path, body)); }
                catch (Throwable t) { replyToShell(requestId, false, String.valueOf(t.getMessage())); }
            });
        }

        @JavascriptInterface public void checkAppUpdate() {
            handler.post(() -> {
                appUpdateBusy = true;
                appUpdateState = "Memeriksa update FurinaHub…";
                if (bridgeUpdater != null) bridgeUpdater.checkOrInstall();
                monitorAppUpdate(0);
            });
        }

        @JavascriptInterface public String appUpdateStatus() { return appUpdateState; }
        @JavascriptInterface public boolean appUpdateBusy() { return appUpdateBusy; }
        @JavascriptInterface public void startCoreUpdate() { handler.post(MainActivity.this::startCoreRecoveryUpdate); }
        @JavascriptInterface public String coreUpdateStatus() { return coreUpdateState; }
        @JavascriptInterface public boolean coreUpdateBusy() { return coreUpdateBusy; }
    }
}
