package com.wynndev.furina;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Environment;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ModelDownloadService extends Service {
    public static final String ACTION_START = "com.wynndev.furina.START_MODEL_DOWNLOAD";
    public static final String ACTION_CANCEL = "com.wynndev.furina.CANCEL_MODEL_DOWNLOAD";
    public static final String EXTRA_ID = "model_id";
    public static final String EXTRA_NAME = "model_name";
    public static final String EXTRA_URL = "model_url";
    public static final String EXTRA_FILE_NAME = "target_file_name";
    public static final String EXTRA_PREF_KEY = "download_pref_key";
    public static final String EXTRA_EXPECTED_SHA256 = "expected_sha256";
    public static final String EXTRA_EXPECTED_SIZE = "expected_size";
    public static final String PREFS = "furina_model_downloads";

    private static final String CHANNEL = "furina_model_downloads";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile String activeKey = "";
    private volatile String cancelKey = "";

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL,
                "Unduhan model AI",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Progres unduhan model dan komponen vision Furina");
            nm.createNotificationChannel(channel);
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;
        String action = intent.getAction();
        String id = safe(intent.getStringExtra(EXTRA_ID));
        String prefKey = safe(intent.getStringExtra(EXTRA_PREF_KEY));
        if (prefKey.isEmpty()) prefKey = id;

        if (ACTION_CANCEL.equals(action)) {
            cancelKey = prefKey;
            save(prefKey, "cancelled", 0, 0, "Membatalkan unduhan…");
            return START_NOT_STICKY;
        }
        if (!ACTION_START.equals(action) || id.isEmpty()) return START_NOT_STICKY;

        if (!activeKey.isEmpty()) {
            save(prefKey, "error", 0, 0, "Tunggu unduhan lain selesai atau batalkan terlebih dahulu.");
            return START_NOT_STICKY;
        }

        String name = safe(intent.getStringExtra(EXTRA_NAME));
        String url = safe(intent.getStringExtra(EXTRA_URL));
        String fileName = safeFileName(intent.getStringExtra(EXTRA_FILE_NAME));
        if (fileName.isEmpty()) fileName = id + ".gguf";
        String expectedSha = safe(intent.getStringExtra(EXTRA_EXPECTED_SHA256)).toLowerCase(Locale.US);
        long expectedSize = Math.max(0L, intent.getLongExtra(EXTRA_EXPECTED_SIZE, 0L));

        activeKey = prefKey;
        cancelKey = "";
        int notificationId = notificationId(prefKey);
        startForeground(notificationId, notification(prefKey, name, 0, 0, "Menghubungkan…", true, true));
        String finalPrefKey = prefKey;
        String finalFileName = fileName;
        worker.execute(() -> download(id, finalPrefKey, name, url, finalFileName, expectedSha, expectedSize));
        return START_NOT_STICKY;
    }

    private void download(
        String id,
        String prefKey,
        String name,
        String urlText,
        String fileName,
        String expectedSha,
        long expectedSize
    ) {
        File dir = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models");
        if (!dir.exists() && !dir.mkdirs()) {
            finishWithError(prefKey, name, "Folder model tidak dapat dibuat.");
            return;
        }

        File target = new File(dir, fileName);
        File partial = new File(dir, fileName + ".part");
        long existing = partial.isFile() ? partial.length() : 0L;
        HttpURLConnection connection = null;

        try {
            if (urlText.isEmpty()) throw new IllegalStateException("URL unduhan belum tersedia.");
            URL url = new URL(urlText);
            boolean connected = false;
            for (int redirects = 0; redirects < 10; redirects++) {
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(25_000);
                connection.setReadTimeout(45_000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("User-Agent", "Furina-Android/4.0");
                connection.setRequestProperty("Accept", "application/octet-stream,*/*");
                if (existing > 0) connection.setRequestProperty("Range", "bytes=" + existing + "-");

                int code = connection.getResponseCode();
                if (code >= 300 && code < 400) {
                    String location = connection.getHeaderField("Location");
                    connection.disconnect();
                    connection = null;
                    if (location == null || location.trim().isEmpty()) {
                        throw new IllegalStateException("Redirect unduhan tidak valid.");
                    }
                    url = new URL(url, location);
                    continue;
                }
                if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                    throw new IllegalStateException("Server mengembalikan HTTP " + code + ".");
                }
                connected = true;
                break;
            }
            if (!connected || connection == null) throw new IllegalStateException("Terlalu banyak redirect unduhan.");

            boolean append = connection.getResponseCode() == HttpURLConnection.HTTP_PARTIAL && existing > 0;
            if (!append) existing = 0L;
            long content = connection.getContentLengthLong();
            long total = content > 0 ? existing + content : expectedSize;
            save(prefKey, "running", existing, total, "Mengunduh");

            try (
                BufferedInputStream in = new BufferedInputStream(connection.getInputStream(), 256 * 1024);
                FileOutputStream out = new FileOutputStream(partial, append)
            ) {
                byte[] buffer = new byte[256 * 1024];
                long done = existing;
                long lastUpdate = 0L;
                int read;
                while ((read = in.read(buffer)) != -1) {
                    if (prefKey.equals(cancelKey)) throw new InterruptedException("cancelled");
                    out.write(buffer, 0, read);
                    done += read;
                    long now = System.currentTimeMillis();
                    if (now - lastUpdate >= 700L) {
                        save(prefKey, "running", done, total, "Mengunduh");
                        getSystemService(NotificationManager.class).notify(
                            notificationId(prefKey),
                            notification(prefKey, name, done, total, "Mengunduh", false, true)
                        );
                        lastUpdate = now;
                    }
                }
                out.getFD().sync();
            }

            long downloadedSize = partial.length();
            if (downloadedSize < 100_000_000L) {
                throw new IllegalStateException("File terlalu kecil dan kemungkinan tidak lengkap.");
            }
            if (expectedSize > 0L && downloadedSize < (long) (expectedSize * 0.70d)) {
                throw new IllegalStateException("Ukuran file belum lengkap.");
            }
            if (!expectedSha.isEmpty()) {
                save(prefKey, "verifying", downloadedSize, downloadedSize, "Memverifikasi file…");
                String actualSha = sha256(partial);
                if (!expectedSha.equalsIgnoreCase(actualSha)) {
                    partial.delete();
                    throw new IllegalStateException("Verifikasi SHA-256 gagal. Unduh ulang file.");
                }
            }

            if (target.exists() && !target.delete()) {
                throw new IllegalStateException("Versi model lama tidak dapat diganti.");
            }
            if (!partial.renameTo(target)) {
                throw new IllegalStateException("File unduhan tidak dapat disimpan.");
            }

            save(prefKey, "complete", target.length(), target.length(), "Selesai");
            getSystemService(NotificationManager.class).notify(
                notificationId(prefKey),
                notification(prefKey, name, target.length(), target.length(), "Selesai diunduh", false, false)
            );
        } catch (InterruptedException cancelled) {
            save(prefKey, "cancelled", partial.length(), expectedSize, "Unduhan dibatalkan; dapat dilanjutkan nanti.");
            getSystemService(NotificationManager.class).cancel(notificationId(prefKey));
        } catch (Exception error) {
            String message = error.getMessage() == null ? "Unduhan gagal." : error.getMessage();
            save(prefKey, "error", partial.length(), expectedSize, message);
            getSystemService(NotificationManager.class).notify(
                notificationId(prefKey),
                notification(prefKey, name, partial.length(), expectedSize, "Gagal: " + message, false, false)
            );
        } finally {
            if (connection != null) connection.disconnect();
            activeKey = "";
            cancelKey = "";
            stopForeground(false);
            stopSelf();
        }
    }

    private void finishWithError(String prefKey, String name, String message) {
        save(prefKey, "error", 0, 0, message);
        getSystemService(NotificationManager.class).notify(
            notificationId(prefKey),
            notification(prefKey, name, 0, 0, "Gagal: " + message, false, false)
        );
        activeKey = "";
        stopForeground(false);
        stopSelf();
    }

    private android.app.Notification notification(
        String prefKey,
        String name,
        long done,
        long total,
        String status,
        boolean indeterminate,
        boolean ongoing
    ) {
        Intent open = new Intent(this, ModelManagerActivity.class);
        PendingIntent content = PendingIntent.getActivity(
            this,
            1,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(ongoing ? android.R.drawable.stat_sys_download : android.R.drawable.stat_sys_download_done)
            .setContentTitle((ongoing ? "Mengunduh " : "Furina • ") + (name.isEmpty() ? "model AI" : name))
            .setContentText(status)
            .setOnlyAlertOnce(true)
            .setAutoCancel(!ongoing)
            .setOngoing(ongoing)
            .setContentIntent(content);

        if (ongoing) {
            Intent cancel = new Intent(this, ModelDownloadService.class)
                .setAction(ACTION_CANCEL)
                .putExtra(EXTRA_PREF_KEY, prefKey);
            PendingIntent cancelIntent = PendingIntent.getService(
                this,
                notificationId(prefKey),
                cancel,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            builder.addAction(0, "Batalkan", cancelIntent);
        }

        if (total > 0L) {
            builder.setProgress(100, (int) Math.min(100L, done * 100L / total), false);
        } else if (indeterminate || done == 0L) {
            builder.setProgress(0, 0, true);
        }
        return builder.build();
    }

    private void save(String key, String state, long done, long total, String message) {
        SharedPreferences.Editor editor = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
        editor.putString(key + "_state", state);
        editor.putLong(key + "_done", done);
        editor.putLong(key + "_total", total);
        editor.putString(key + "_message", message);
        editor.apply();
    }

    private String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
        }
        StringBuilder out = new StringBuilder(64);
        for (byte value : digest.digest()) out.append(String.format(Locale.US, "%02x", value));
        return out.toString();
    }

    private int notificationId(String key) {
        return 20_000 + Math.abs(key.hashCode() % 20_000);
    }

    private String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private String safeFileName(String value) {
        String name = safe(value);
        return name.matches("[A-Za-z0-9._-]+") ? name : "";
    }

    @Nullable @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
        worker.shutdownNow();
        super.onDestroy();
    }
}
