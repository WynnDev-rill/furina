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
import java.io.FileOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ModelDownloadService extends Service {
    public static final String ACTION_START = "com.wynndev.furina.START_MODEL_DOWNLOAD";
    public static final String ACTION_CANCEL = "com.wynndev.furina.CANCEL_MODEL_DOWNLOAD";
    public static final String EXTRA_ID = "model_id";
    public static final String EXTRA_NAME = "model_name";
    public static final String EXTRA_URL = "model_url";
    public static final String PREFS = "furina_model_downloads";
    private static final String CHANNEL = "furina_model_downloads";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile boolean cancelled;

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL, "Unduhan model AI", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Progres unduhan model AI offline Furina");
            nm.createNotificationChannel(channel);
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;
        String action = intent.getAction();
        String id = intent.getStringExtra(EXTRA_ID);
        if (ACTION_CANCEL.equals(action)) {
            cancelled = true;
            if (id != null) save(id, "cancelled", 0, 0, "Unduhan dibatalkan");
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!ACTION_START.equals(action) || id == null) return START_NOT_STICKY;

        String name = intent.getStringExtra(EXTRA_NAME);
        String url = intent.getStringExtra(EXTRA_URL);
        cancelled = false;
        startForeground(id.hashCode(), notification(id, name, 0, 0, "Menghubungkan…", true));
        worker.execute(() -> download(id, name, url));
        return START_REDELIVER_INTENT;
    }

    private void download(String id, String name, String urlText) {
        File dir = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models");
        if (!dir.exists()) dir.mkdirs();
        File target = new File(dir, id + ".gguf");
        File partial = new File(dir, id + ".gguf.part");
        long existing = partial.exists() ? partial.length() : 0L;
        HttpURLConnection connection = null;
        try {
            URL url = new URL(urlText);
            for (int redirects = 0; redirects < 8; redirects++) {
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(20_000);
                connection.setReadTimeout(30_000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("User-Agent", "Furina-Android/1.0");
                connection.setRequestProperty("Accept", "application/octet-stream,*/*");
                if (existing > 0) connection.setRequestProperty("Range", "bytes=" + existing + "-");
                int code = connection.getResponseCode();
                if (code >= 300 && code < 400) {
                    String location = connection.getHeaderField("Location");
                    connection.disconnect();
                    if (location == null) throw new IllegalStateException("Redirect unduhan tidak valid");
                    url = new URL(url, location);
                    continue;
                }
                if (code != 200 && code != 206) throw new IllegalStateException("Server mengembalikan HTTP " + code);
                break;
            }

            boolean append = connection.getResponseCode() == 206 && existing > 0;
            if (!append) existing = 0;
            long content = connection.getContentLengthLong();
            long total = content > 0 ? existing + content : 0;
            save(id, "running", existing, total, "Mengunduh");

            try (BufferedInputStream in = new BufferedInputStream(connection.getInputStream(), 256 * 1024);
                 FileOutputStream out = new FileOutputStream(partial, append)) {
                byte[] buffer = new byte[256 * 1024];
                long done = existing;
                long lastUpdate = 0;
                int read;
                while ((read = in.read(buffer)) != -1) {
                    if (cancelled) throw new InterruptedException("cancelled");
                    out.write(buffer, 0, read);
                    done += read;
                    long now = System.currentTimeMillis();
                    if (now - lastUpdate >= 750) {
                        save(id, "running", done, total, "Mengunduh");
                        getSystemService(NotificationManager.class).notify(id.hashCode(), notification(id, name, done, total, "Mengunduh", false));
                        lastUpdate = now;
                    }
                }
                out.getFD().sync();
            }

            if (target.exists()) target.delete();
            if (!partial.renameTo(target)) throw new IllegalStateException("File unduhan tidak dapat disimpan");
            save(id, "complete", target.length(), target.length(), "Selesai");
            getSystemService(NotificationManager.class).notify(id.hashCode(), notification(id, name, target.length(), target.length(), "Selesai diunduh", false));
        } catch (InterruptedException e) {
            save(id, "cancelled", partial.length(), 0, "Unduhan dibatalkan");
        } catch (Exception e) {
            save(id, "error", partial.length(), 0, e.getMessage() == null ? "Unduhan gagal" : e.getMessage());
            getSystemService(NotificationManager.class).notify(id.hashCode(), notification(id, name, 0, 0, "Gagal: " + (e.getMessage() == null ? "kesalahan jaringan" : e.getMessage()), false));
        } finally {
            if (connection != null) connection.disconnect();
            stopForeground(false);
            stopSelf();
        }
    }

    private android.app.Notification notification(String id, String name, long done, long total, String status, boolean indeterminate) {
        Intent open = new Intent(this, ModelManagerActivity.class);
        PendingIntent content = PendingIntent.getActivity(this, 1, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent cancel = new Intent(this, ModelDownloadService.class).setAction(ACTION_CANCEL).putExtra(EXTRA_ID, id);
        PendingIntent cancelIntent = PendingIntent.getService(this, id.hashCode(), cancel, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Mengunduh " + name)
            .setContentText(status)
            .setOnlyAlertOnce(true)
            .setOngoing(!"Selesai diunduh".equals(status) && !status.startsWith("Gagal"))
            .setContentIntent(content)
            .addAction(0, "Batal", cancelIntent);
        if (total > 0) b.setProgress(100, (int) Math.min(100, done * 100 / total), false);
        else if (indeterminate || done == 0) b.setProgress(0, 0, true);
        return b.build();
    }

    private void save(String id, String state, long done, long total, String message) {
        SharedPreferences.Editor e = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
        e.putString(id + "_state", state);
        e.putLong(id + "_done", done);
        e.putLong(id + "_total", total);
        e.putString(id + "_message", message);
        e.apply();
    }

    @Nullable @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
