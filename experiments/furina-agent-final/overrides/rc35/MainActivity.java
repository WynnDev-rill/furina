package com.wynndev.furinaagentbridge;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String HUB_URL = "http://127.0.0.1:8787/";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private WebView web;
    private LinearLayout bootstrap;
    private TextView status;
    private Button retry;
    private BridgeUpdater bridgeUpdater;
    private String hubToken = "";
    private TextView hiddenUpdateStatus;
    private Button hiddenUpdateButton;
    private volatile String appUpdateState = "Belum diperiksa.";
    private volatile boolean appUpdateBusy;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        BridgeForegroundService.start(this);
        requestNotificationsIfNeeded();
        setContentView(buildRoot());
        bridgeUpdater = new BridgeUpdater(this, hiddenUpdateStatus, hiddenUpdateButton);
        ensureHub();
    }

    @Override protected void onResume() {
        super.onResume();
        BridgePrefs.openBootstrapWindow(this, 120_000L);
        if (bridgeUpdater != null) bridgeUpdater.onResume();
    }

    @Override protected void onDestroy() {
        if (web != null) {
            web.removeJavascriptInterface("FurinaNative");
            web.destroy();
        }
        io.shutdownNow();
        super.onDestroy();
    }

    private View buildRoot() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(250, 250, 255));

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(false);
        if (Build.VERSION.SDK_INT >= 21) {
            s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        }
        web.addJavascriptInterface(new NativeApi(), "FurinaNative");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                return !isHubUrl(url);
            }
            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return !isHubUrl(url);
            }
        });
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        bootstrap = new LinearLayout(this);
        bootstrap.setOrientation(LinearLayout.VERTICAL);
        bootstrap.setGravity(Gravity.CENTER);
        bootstrap.setPadding(dp(28), dp(28), dp(28), dp(28));
        bootstrap.setBackgroundColor(Color.rgb(250, 250, 255));
        ProgressBar progress = new ProgressBar(this);
        bootstrap.addView(progress, new LinearLayout.LayoutParams(dp(42), dp(42)));
        TextView title = new TextView(this);
        title.setText("FurinaHub");
        title.setTextSize(25);
        title.setTextColor(Color.rgb(36, 34, 48));
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tp.topMargin = dp(18);
        bootstrap.addView(title, tp);
        status = new TextView(this);
        status.setText("Menghubungkan Core di Termux…");
        status.setTextSize(14);
        status.setTextColor(Color.rgb(104, 100, 122));
        status.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sp.topMargin = dp(9);
        bootstrap.addView(status, sp);
        retry = new Button(this);
        retry.setText("Coba lagi");
        retry.setAllCaps(false);
        retry.setVisibility(View.GONE);
        retry.setOnClickListener(v -> ensureHub());
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        rp.topMargin = dp(16);
        bootstrap.addView(retry, rp);
        root.addView(bootstrap, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        hiddenUpdateStatus = new TextView(this);
        hiddenUpdateStatus.setVisibility(View.GONE);
        hiddenUpdateButton = new Button(this);
        hiddenUpdateButton.setVisibility(View.GONE);
        root.addView(hiddenUpdateStatus, new FrameLayout.LayoutParams(1, 1));
        root.addView(hiddenUpdateButton, new FrameLayout.LayoutParams(1, 1));
        return root;
    }

    private boolean isHubUrl(String raw) {
        return raw != null && (
                raw.startsWith("http://127.0.0.1:8787/") ||
                raw.equals("http://127.0.0.1:8787") ||
                raw.startsWith("http://localhost:8787/") ||
                raw.equals("http://localhost:8787")
        );
    }

    private void ensureHub() {
        retry.setVisibility(View.GONE);
        bootstrap.setVisibility(View.VISIBLE);
        status.setText("Memeriksa Furina Core…");
        hubToken = UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "");
        final String token = hubToken;
        io.execute(() -> {
            runFixedTermux(
                    "/data/data/com.termux/files/usr/bin/furina-hub",
                    new String[]{"--replace", "--token", token}
            );
            long deadline = System.currentTimeMillis() + 35_000L;
            while (System.currentTimeMillis() < deadline && !Thread.currentThread().isInterrupted()) {
                if (health()) break;
                try { Thread.sleep(700L); } catch (InterruptedException e) { return; }
            }
            boolean ready = health();
            handler.post(() -> {
                if (ready) {
                    status.setText("Core siap.");
                    web.loadUrl(HUB_URL + "?access=" + token);
                    bootstrap.setVisibility(View.GONE);
                } else {
                    status.setText("Core belum dapat dinyalakan. Buka Termux sekali dan pastikan izin integrasi FurinaHub aktif.");
                    retry.setVisibility(View.VISIBLE);
                }
            });
        });
    }

    private boolean health() {
        HttpURLConnection c = null;
        try {
            String token = hubToken == null ? "" : hubToken;
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

    private void runFixedTermux(String path, String[] args) {
        try {
            Intent intent = new Intent();
            intent.setComponent(new ComponentName("com.termux", "com.termux.app.RunCommandService"));
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", path);
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args);
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            startService(intent);
        } catch (Throwable t) {
            handler.post(() -> Toast.makeText(
                    this,
                    "Termux belum mengizinkan integrasi eksternal. Jalankan installer FurinaHub dari Termux.",
                    Toast.LENGTH_LONG
            ).show());
        }
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
                // First tap fetched metadata; second fixed call starts the verified download.
                hiddenUpdateButton.setEnabled(false);
                bridgeUpdater.checkOrInstall();
                handler.postDelayed(() -> monitorAppUpdate(attempt + 1), 500L);
                return;
            }
            appUpdateBusy = false;
            return;
        }
        if (button.contains("Installer dibuka")) {
            appUpdateBusy = false;
            return;
        }
        if (attempt >= 120) {
            appUpdateBusy = false;
            if (appUpdateState.startsWith("Memeriksa")) appUpdateState = "Pemeriksaan update membutuhkan waktu terlalu lama.";
            return;
        }
        handler.postDelayed(() -> monitorAppUpdate(attempt + 1), 500L);
    }

    private void requestNotificationsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 22);
        }
    }

    public class NativeApi {
        @JavascriptInterface public void checkAppUpdate() {
            handler.post(() -> {
                appUpdateBusy = true;
                appUpdateState = "Memeriksa update FurinaHub…";
                Toast.makeText(MainActivity.this, appUpdateState, Toast.LENGTH_SHORT).show();
                if (bridgeUpdater != null) bridgeUpdater.checkOrInstall();
                monitorAppUpdate(0);
            });
        }

        @JavascriptInterface public String appUpdateStatus() {
            return appUpdateState;
        }

        @JavascriptInterface public boolean appUpdateBusy() {
            return appUpdateBusy;
        }

        @JavascriptInterface public void openAccessibility() {
            handler.post(() -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        }

        @JavascriptInterface public void reconnectCore() {
            handler.post(() -> ensureHub());
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
