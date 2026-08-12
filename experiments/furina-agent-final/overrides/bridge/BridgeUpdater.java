package com.wynndev.furinaagentbridge;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;

final class BridgeUpdater {
    private static final String MANIFEST_URL = "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json";
    private static final long AUTO_CHECK_INTERVAL_MS = 15 * 60_000L;
    private static final long MAX_APK_BYTES = 50L * 1024L * 1024L;

    private final Activity activity;
    private final TextView status;
    private final Button button;

    private volatile boolean busy;
    private volatile boolean pendingInstallPermission;
    private long lastCheckAt;
    private long remoteVersionCode;
    private String remoteVersionName = "";
    private String apkUrl = "";
    private String expectedSha256 = "";
    private String expectedSignerSha256 = "";
    private String expectedPackage = "";

    BridgeUpdater(Activity activity, TextView status, Button button) {
        this.activity = activity;
        this.status = status;
        this.button = button;
    }

    void onResume() {
        if (pendingInstallPermission && activity.getPackageManager().canRequestPackageInstalls()) {
            pendingInstallPermission = false;
            if (remoteVersionCode > currentVersionCode()) downloadAndInstall();
            return;
        }
        check(false);
    }

    void checkOrInstall() {
        if (busy) return;
        if (remoteVersionCode > currentVersionCode() && !apkUrl.isEmpty()) {
            ensureInstallPermissionThenDownload();
        } else {
            check(true);
        }
    }

    void check(boolean userInitiated) {
        if (busy) return;
        long now = System.currentTimeMillis();
        if (!userInitiated && lastCheckAt > 0 && now - lastCheckAt < AUTO_CHECK_INTERVAL_MS) return;
        busy = true;
        setUi("Memeriksa versi terbaru…", "Memeriksa…", false);
        new Thread(() -> {
            try {
                JSONObject manifest = new JSONObject(readText(MANIFEST_URL, 256 * 1024));
                long latestCode = manifest.optLong("bridge_version_code", 0L);
                String latestName = manifest.optString("bridge_version", "").trim();
                String releaseBase = manifest.optString("bridge_release_base", "").trim();
                if (latestCode <= 0 || latestName.isEmpty() || releaseBase.isEmpty()) {
                    throw new IllegalStateException("metadata update tidak lengkap");
                }

                JSONObject bridgeMeta = new JSONObject(readText(releaseBase + "/bridge.json", 256 * 1024));
                String packageName = bridgeMeta.optString("package_name", "").trim();
                long metaCode = bridgeMeta.optLong("version_code", 0L);
                String metaName = bridgeMeta.optString("version", "").trim();
                String url = bridgeMeta.optString("apk_url", "").trim();
                String sha = normalizeDigest(bridgeMeta.optString("sha256", ""));
                String signer = normalizeDigest(bridgeMeta.optString("signer_sha256", ""));

                if (!activity.getPackageName().equals(packageName) || metaCode != latestCode || !latestName.equals(metaName)) {
                    throw new IllegalStateException("metadata release tidak konsisten");
                }
                if (!url.startsWith("https://github.com/WynnDev-rill/furina/releases/download/") || sha.length() != 64 || signer.length() != 64) {
                    throw new IllegalStateException("metadata keamanan update tidak valid");
                }

                remoteVersionCode = latestCode;
                remoteVersionName = latestName;
                apkUrl = url;
                expectedSha256 = sha;
                expectedSignerSha256 = signer;
                expectedPackage = packageName;
                lastCheckAt = System.currentTimeMillis();

                long current = currentVersionCode();
                String currentName = currentVersionName();
                if (latestCode > current) {
                    setUi("Update tersedia: " + currentName + " → " + latestName + "\nAPK akan diverifikasi SHA-256, package, versi, dan signature sebelum installer dibuka.", "Perbarui ke " + latestName, true);
                } else {
                    setUi("Versi terpasang " + currentName + " sudah yang terbaru.", "Periksa lagi", true);
                }
            } catch (Throwable t) {
                setUi("Tidak dapat memeriksa update: " + shortError(t), "Coba lagi", true);
            } finally {
                busy = false;
            }
        }, "furina-bridge-update-check").start();
    }

    private void ensureInstallPermissionThenDownload() {
        if (!activity.getPackageManager().canRequestPackageInstalls()) {
            pendingInstallPermission = true;
            setUi("Android perlu mengizinkan Furina Bridge memasang update. Aktifkan 'Izinkan dari sumber ini', lalu kembali; update akan dilanjutkan otomatis.", "Menunggu izin…", false);
            try {
                Intent intent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + activity.getPackageName()));
                activity.startActivity(intent);
            } catch (Throwable t) {
                pendingInstallPermission = false;
                setUi("Tidak dapat membuka izin instalasi: " + shortError(t), "Coba lagi", true);
            }
            return;
        }
        downloadAndInstall();
    }

    private void downloadAndInstall() {
        if (busy) return;
        busy = true;
        setUi("Mengunduh update " + remoteVersionName + "…", "Mengunduh…", false);
        new Thread(() -> {
            try {
                File dir = new File(activity.getCacheDir(), "updates");
                if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("cache update tidak dapat dibuat");
                File apk = new File(dir, "Furina-Agent-Bridge-update.apk");
                File part = new File(dir, "Furina-Agent-Bridge-update.apk.part");
                downloadFile(apkUrl, part);
                String actualSha = sha256(part);
                if (!actualSha.equals(expectedSha256)) throw new SecurityException("checksum APK tidak cocok");
                if (apk.exists() && !apk.delete()) throw new IllegalStateException("APK lama tidak dapat diganti");
                if (!part.renameTo(apk)) throw new IllegalStateException("APK update tidak dapat difinalkan");
                verifyArchive(apk);
                openInstaller(apk);
                setUi("APK " + remoteVersionName + " sudah diverifikasi. Selesaikan konfirmasi installer Android.", "Installer dibuka", false);
            } catch (Throwable t) {
                setUi("Update gagal: " + shortError(t), "Coba lagi", true);
            } finally {
                busy = false;
            }
        }, "furina-bridge-update-download").start();
    }

    private void verifyArchive(File apk) throws Exception {
        PackageManager pm = activity.getPackageManager();
        PackageInfo archive = pm.getPackageArchiveInfo(apk.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES);
        if (archive == null) throw new SecurityException("APK tidak dapat dibaca Android");
        if (!expectedPackage.equals(archive.packageName)) throw new SecurityException("package APK berbeda");
        if (archive.getLongVersionCode() != remoteVersionCode) throw new SecurityException("versionCode APK berbeda");

        String archiveSigner = signerDigest(archive);
        PackageInfo installed = pm.getPackageInfo(activity.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
        String installedSigner = signerDigest(installed);
        if (!archiveSigner.equals(expectedSignerSha256)) throw new SecurityException("signature APK tidak sesuai metadata");
        if (!archiveSigner.equals(installedSigner)) throw new SecurityException("signature APK berbeda dari Furina Bridge terpasang");
    }

    private void openInstaller(File apk) {
        Uri uri = Uri.parse("content://" + activity.getPackageName() + ".updateprovider/update.apk");
        activity.grantUriPermission("com.google.android.packageinstaller", uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        activity.startActivity(intent);
    }

    private long currentVersionCode() {
        try {
            return activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0).getLongVersionCode();
        } catch (Throwable t) {
            return 0L;
        }
    }

    private String currentVersionName() {
        try {
            PackageInfo info = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0);
            return info.versionName == null ? String.valueOf(info.getLongVersionCode()) : info.versionName;
        } catch (Throwable t) {
            return "unknown";
        }
    }

    private static String signerDigest(PackageInfo info) throws Exception {
        if (info.signingInfo == null) throw new SecurityException("signature info tidak tersedia");
        Signature[] signatures = info.signingInfo.getApkContentsSigners();
        if (signatures == null || signatures.length == 0) throw new SecurityException("signature APK kosong");
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        return hex(md.digest(signatures[0].toByteArray()));
    }

    private static void downloadFile(String url, File target) throws Exception {
        HttpURLConnection conn = open(url);
        long declared = conn.getContentLengthLong();
        if (declared > MAX_APK_BYTES) throw new IllegalStateException("APK terlalu besar");
        long total = 0;
        try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(target, false)) {
            byte[] buf = new byte[32 * 1024];
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (n == 0) continue;
                total += n;
                if (total > MAX_APK_BYTES) throw new IllegalStateException("APK melewati batas ukuran");
                out.write(buf, 0, n);
            }
            out.getFD().sync();
        } finally {
            conn.disconnect();
        }
        if (total <= 0) throw new IllegalStateException("APK kosong");
    }

    private static String readText(String url, int limit) throws Exception {
        HttpURLConnection conn = open(url);
        try (InputStream in = conn.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int total = 0;
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (n == 0) continue;
                total += n;
                if (total > limit) throw new IllegalStateException("respons metadata terlalu besar");
                out.write(buf, 0, n);
            }
            return out.toString("UTF-8");
        } finally {
            conn.disconnect();
        }
    }

    private static HttpURLConnection open(String value) throws Exception {
        URL url = new URL(value);
        if (!"https".equalsIgnoreCase(url.getProtocol())) throw new SecurityException("update harus melalui HTTPS");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(10_000);
        conn.setReadTimeout(30_000);
        conn.setInstanceFollowRedirects(true);
        conn.setRequestProperty("User-Agent", "FurinaBridge-Updater/1");
        int code = conn.getResponseCode();
        if (code < 200 || code >= 300) {
            conn.disconnect();
            throw new IllegalStateException("HTTP " + code);
        }
        return conn;
    }

    private static String sha256(File file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new java.io.FileInputStream(file)) {
            byte[] buf = new byte[32 * 1024];
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (n > 0) md.update(buf, 0, n);
            }
        }
        return hex(md.digest());
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) sb.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return sb.toString();
    }

    private static String normalizeDigest(String value) {
        return value == null ? "" : value.toLowerCase(Locale.ROOT).replace(":", "").trim();
    }

    private static String shortError(Throwable t) {
        String msg = t.getMessage();
        if (msg == null || msg.trim().isEmpty()) msg = t.getClass().getSimpleName();
        msg = msg.replace('\n', ' ').replace('\r', ' ').trim();
        return msg.length() > 180 ? msg.substring(0, 180) : msg;
    }

    private void setUi(String message, String buttonText, boolean enabled) {
        activity.runOnUiThread(() -> {
            status.setText(message);
            button.setText(buttonText);
            button.setEnabled(enabled);
        });
    }
}
