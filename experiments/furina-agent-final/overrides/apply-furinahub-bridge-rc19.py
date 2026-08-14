#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys

MAIN_ACTIVITY = 'package com.wynndev.furinaagentbridge;\n\nimport android.Manifest;\nimport android.app.Activity;\nimport android.content.Intent;\nimport android.content.pm.PackageManager;\nimport android.graphics.Color;\nimport android.graphics.Typeface;\nimport android.os.Build;\nimport android.os.Bundle;\nimport android.os.Handler;\nimport android.os.Looper;\nimport android.view.Gravity;\nimport android.view.View;\nimport android.webkit.JavascriptInterface;\nimport android.webkit.WebResourceRequest;\nimport android.webkit.WebSettings;\nimport android.webkit.WebView;\nimport android.webkit.WebViewClient;\nimport android.widget.Button;\nimport android.widget.LinearLayout;\nimport android.widget.ProgressBar;\nimport android.widget.TextView;\nimport android.widget.Toast;\n\nimport org.json.JSONObject;\n\nimport java.io.BufferedReader;\nimport java.io.InputStreamReader;\nimport java.net.HttpURLConnection;\nimport java.net.URL;\nimport java.security.SecureRandom;\nimport java.util.Locale;\nimport java.util.concurrent.ExecutorService;\nimport java.util.concurrent.Executors;\n\npublic class MainActivity extends Activity {\n    private static final String HUB_URL = "http://127.0.0.1:8787/";\n    private static final String HEALTH_URL = "http://127.0.0.1:8787/api/health";\n    private static final String RUN_PERMISSION = "com.termux.permission.RUN_COMMAND";\n    private static final int REQ_RUN = 77;\n    private static final int REQ_NOTIFY = 22;\n\n    private final Handler main = new Handler(Looper.getMainLooper());\n    private final ExecutorService io = Executors.newSingleThreadExecutor();\n    private WebView webView;\n    private TextView loadingText;\n    private TextView updateStatus;\n    private Button updateButton;\n    private BridgeUpdater bridgeUpdater;\n    private String hubToken;\n    private int pollAttempt = 0;\n\n    @Override protected void onCreate(Bundle savedInstanceState) {\n        super.onCreate(savedInstanceState);\n        BridgeForegroundService.start(this);\n        requestNotificationsIfNeeded();\n        hubToken = loadOrCreateHubToken();\n\n        updateStatus = new TextView(this);\n        updateButton = new Button(this);\n        bridgeUpdater = new BridgeUpdater(this, updateStatus, updateButton);\n        bridgeUpdater.check(false);\n\n        setContentView(buildLoadingView());\n        ensureRunPermissionAndStart();\n    }\n\n    @Override protected void onDestroy() {\n        main.removeCallbacksAndMessages(null);\n        io.shutdownNow();\n        if (webView != null) {\n            webView.removeJavascriptInterface("FurinaHubNative");\n            webView.destroy();\n        }\n        super.onDestroy();\n    }\n\n    private View buildLoadingView() {\n        LinearLayout root = new LinearLayout(this);\n        root.setOrientation(LinearLayout.VERTICAL);\n        root.setGravity(Gravity.CENTER);\n        root.setPadding(dp(28), dp(28), dp(28), dp(28));\n        root.setBackgroundColor(Color.rgb(248, 248, 252));\n\n        TextView brand = new TextView(this);\n        brand.setText("FurinaHub");\n        brand.setTextSize(30);\n        brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);\n        brand.setTextColor(Color.rgb(78, 67, 184));\n        root.addView(brand);\n\n        loadingText = new TextView(this);\n        loadingText.setText("Menyiapkan FurinaHub…");\n        loadingText.setTextSize(14);\n        loadingText.setTextColor(Color.rgb(102, 103, 118));\n        loadingText.setGravity(Gravity.CENTER);\n        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(\n                LinearLayout.LayoutParams.WRAP_CONTENT,\n                LinearLayout.LayoutParams.WRAP_CONTENT\n        );\n        lp.topMargin = dp(12);\n        root.addView(loadingText, lp);\n\n        ProgressBar progress = new ProgressBar(this);\n        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(dp(34), dp(34));\n        pp.topMargin = dp(20);\n        root.addView(progress, pp);\n\n        return root;\n    }\n\n    private void ensureRunPermissionAndStart() {\n        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_PERMISSION) != PackageManager.PERMISSION_GRANTED) {\n            try {\n                requestPermissions(new String[]{RUN_PERMISSION}, REQ_RUN);\n                loadingText.setText("Izinkan FurinaHub menjalankan Core di Termux.");\n                return;\n            } catch (Throwable t) {\n                showTermuxSetup("Permission RUN_COMMAND belum tersedia.");\n                return;\n            }\n        }\n        startHubThroughTermux();\n    }\n\n    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {\n        super.onRequestPermissionsResult(requestCode, permissions, grantResults);\n        if (requestCode == REQ_RUN) {\n            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {\n                startHubThroughTermux();\n            } else {\n                showTermuxSetup("FurinaHub membutuhkan izin Termux RUN_COMMAND untuk start otomatis.");\n            }\n        }\n    }\n\n    private void startHubThroughTermux() {\n        try {\n            Intent intent = new Intent();\n            intent.setClassName("com.termux", "com.termux.app.RunCommandService");\n            intent.setAction("com.termux.RUN_COMMAND");\n            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/furinahub");\n            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"serve", "--token", hubToken, "--replace"});\n            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");\n            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);\n            startService(intent);\n            loadingText.setText("Menyalakan Core lokal…");\n            pollAttempt = 0;\n            main.postDelayed(this::pollHub, 350);\n        } catch (SecurityException se) {\n            showTermuxSetup("Termux menolak RUN_COMMAND. Jalankan installer Furina terbaru sekali lagi.");\n        } catch (Throwable t) {\n            showTermuxSetup("Termux tidak ditemukan atau Core belum terpasang.");\n        }\n    }\n\n    private void pollHub() {\n        final int attempt = ++pollAttempt;\n        io.execute(() -> {\n            boolean ok = health();\n            main.post(() -> {\n                if (isFinishing()) return;\n                if (ok) {\n                    openHub();\n                } else if (attempt < 45) {\n                    loadingText.setText("Menyiapkan Core… " + Math.min(99, attempt * 2) + "%");\n                    main.postDelayed(this::pollHub, 450);\n                } else {\n                    showTermuxSetup("Core tidak merespons. Buka Termux lalu jalankan: furina doctor");\n                }\n            });\n        });\n    }\n\n    private boolean health() {\n        HttpURLConnection conn = null;\n        try {\n            conn = (HttpURLConnection) new URL(HEALTH_URL).openConnection();\n            conn.setConnectTimeout(600);\n            conn.setReadTimeout(900);\n            conn.setRequestMethod("GET");\n            if (conn.getResponseCode() != 200) return false;\n            BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream()));\n            String line = br.readLine();\n            br.close();\n            return line != null && line.contains("\\"ok\\": true");\n        } catch (Throwable t) {\n            return false;\n        } finally {\n            if (conn != null) conn.disconnect();\n        }\n    }\n\n    private void openHub() {\n        if (webView != null) return;\n        webView = new WebView(this);\n        WebSettings s = webView.getSettings();\n        s.setJavaScriptEnabled(true);\n        s.setDomStorageEnabled(true);\n        s.setAllowFileAccess(false);\n        s.setAllowContentAccess(false);\n        s.setJavaScriptCanOpenWindowsAutomatically(false);\n        s.setSupportMultipleWindows(false);\n        if (Build.VERSION.SDK_INT >= 21) s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);\n        if (Build.VERSION.SDK_INT >= 26) WebView.setSafeBrowsingEnabled(true);\n\n        webView.addJavascriptInterface(new NativeApi(), "FurinaHubNative");\n        webView.setWebViewClient(new WebViewClient() {\n            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {\n                String url = request.getUrl() == null ? "" : request.getUrl().toString();\n                return !url.startsWith(HUB_URL);\n            }\n\n            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {\n                return url == null || !url.startsWith(HUB_URL);\n            }\n\n            @Override public void onPageFinished(WebView view, String url) {\n                if (url != null && url.startsWith(HUB_URL)) {\n                    String quoted = JSONObject.quote(hubToken);\n                    view.evaluateJavascript(\n                            "window.FurinaHub&&window.FurinaHub.boot(" + quoted + ");",\n                            null\n                    );\n                }\n            }\n        });\n        setContentView(webView);\n        webView.loadUrl(HUB_URL);\n    }\n\n    private void showTermuxSetup(String detail) {\n        if (loadingText != null) {\n            loadingText.setText(detail + "\\n\\nCore dan CLI tetap dapat dipakai langsung dari Termux.");\n        }\n    }\n\n    private String loadOrCreateHubToken() {\n        String saved = getSharedPreferences("furinahub-ui", MODE_PRIVATE).getString("hub-token", "");\n        if (saved != null && saved.length() >= 32) return saved;\n        byte[] bytes = new byte[32];\n        new SecureRandom().nextBytes(bytes);\n        StringBuilder sb = new StringBuilder();\n        for (byte b : bytes) sb.append(String.format(Locale.US, "%02x", b & 0xff));\n        String token = sb.toString();\n        getSharedPreferences("furinahub-ui", MODE_PRIVATE).edit().putString("hub-token", token).apply();\n        return token;\n    }\n\n    private void requestNotificationsIfNeeded() {\n        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {\n            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFY);\n        }\n    }\n\n    public final class NativeApi {\n        @JavascriptInterface public void checkAppUpdate() {\n            main.post(() -> {\n                if (bridgeUpdater != null) bridgeUpdater.checkOrInstall();\n            });\n        }\n\n        @JavascriptInterface public String appUpdateStatus() {\n            String a = updateStatus == null ? "" : String.valueOf(updateStatus.getText());\n            String b = updateButton == null ? "" : String.valueOf(updateButton.getText());\n            return (a + (b.isEmpty() ? "" : " · " + b)).trim();\n        }\n\n        @JavascriptInterface public void openAccessibility() {\n            main.post(() -> {\n                try {\n                    startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS));\n                } catch (Throwable ignored) {}\n            });\n        }\n\n        @JavascriptInterface public void restartHub() {\n            main.post(() -> {\n                if (webView != null) {\n                    webView.removeJavascriptInterface("FurinaHubNative");\n                    webView.destroy();\n                    webView = null;\n                }\n                setContentView(buildLoadingView());\n                startHubThroughTermux();\n            });\n        }\n    }\n\n    private int dp(int value) {\n        return Math.round(value * getResources().getDisplayMetrics().density);\n    }\n}\n'

NETWORK_SECURITY = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
"""


def rep_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC19 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-furinahub-bridge-rc19.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    java = app / "src/main/java/com/wynndev/furinaagentbridge"
    manifest = app / "src/main/AndroidManifest.xml"
    gradle = app / "build.gradle"
    updater = java / "BridgeUpdater.java"
    if not manifest.is_file() or not gradle.is_file() or not updater.is_file():
        raise SystemExit("missing RC18 Bridge project")

    g = gradle.read_text(encoding="utf-8")
    g = rep_once(g, "versionCode 10018", "versionCode 10019", "versionCode")
    g = rep_once(g, "versionName '1.0.0-rc18'", "versionName '1.0.0-rc19'", "versionName")
    gradle.write_text(g, encoding="utf-8")

    m = manifest.read_text(encoding="utf-8")
    m = rep_once(
        m,
        '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n',
        '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n'
        '    <uses-permission android:name="com.termux.permission.RUN_COMMAND" />\n',
        "RUN_COMMAND permission",
    )
    if '<package android:name="com.termux" />' not in m:
        m = rep_once(
            m,
            "    <queries>\n",
            '    <queries>\n        <package android:name="com.termux" />\n',
            "Termux package query",
        )
    m = rep_once(m, 'android:label="Furina Bridge"', 'android:label="FurinaHub"', "app label")
    m = rep_once(
        m,
        '        android:supportsRtl="true"\n        android:theme="@style/AppTheme">',
        '        android:supportsRtl="true"\n'
        '        android:networkSecurityConfig="@xml/network_security_config"\n'
        '        android:theme="@style/AppTheme">',
        "network security config",
    )
    manifest.write_text(m, encoding="utf-8")

    (java / "MainActivity.java").write_text(MAIN_ACTIVITY, encoding="utf-8")
    xml = app / "src/main/res/xml"
    xml.mkdir(parents=True, exist_ok=True)
    (xml / "network_security_config.xml").write_text(NETWORK_SECURITY, encoding="utf-8")

    u = updater.read_text(encoding="utf-8")
    u = u.replace("Furina Bridge", "FurinaHub")
    u = u.replace("furina-bridge-update.apk", "furinahub-update.apk")
    updater.write_text(u, encoding="utf-8")

    final_main = (java / "MainActivity.java").read_text(encoding="utf-8")
    required = (
        "http://127.0.0.1:8787/",
        "com.termux.permission.RUN_COMMAND",
        "/data/data/com.termux/files/usr/bin/furinahub",
        'new String[]{"serve", "--token", hubToken, "--replace"}',
        'addJavascriptInterface(new NativeApi(), "FurinaHubNative")',
        "setAllowFileAccess(false)",
        "setAllowContentAccess(false)",
    )
    missing = [x for x in required if x not in final_main]
    if missing:
        raise SystemExit("FurinaHub RC19 MainActivity incomplete: " + ", ".join(missing))
    forbidden = ("RUN_COMMAND_PATH\\\", command", "Runtime.getRuntime().exec", "ProcessBuilder(")
    for marker in forbidden:
        if marker in final_main:
            raise SystemExit("FurinaHub RC19 unsafe generic command marker: " + marker)

    for path in (manifest, gradle, updater, java / "MainActivity.java", xml / "network_security_config.xml"):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit("missing FurinaHub RC19 output: " + str(path))
    print("FurinaHub Bridge RC19 WebView shell + signed-update path: OK")


if __name__ == "__main__":
    main()
