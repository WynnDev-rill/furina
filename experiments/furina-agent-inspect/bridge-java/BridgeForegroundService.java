package com.wynndev.furinaagentbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

public class BridgeForegroundService extends Service {
    private static final int NOTIFICATION_ID = 8765;
    private static final String CHANNEL_ID = "furina_bridge_persistent";
    private static volatile BridgeForegroundService instance;
    private LocalBridgeServer server;

    public static void start(Context context) {
        BridgePrefs.setPersistentEnabled(context, true);
        Intent intent = new Intent(context, BridgeForegroundService.class);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent);
            else context.startService(intent);
        } catch (Throwable t) {
            BridgeRuntime.setLastServerError(t);
        }
    }

    public static void stopPersistent(Context context) {
        BridgePrefs.setPersistentEnabled(context, false);
        try { context.stopService(new Intent(context, BridgeForegroundService.class)); } catch (Throwable ignored) {}
    }

    public static void refreshNotification() {
        BridgeForegroundService s = instance;
        if (s != null) s.updateNotification();
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        createChannel();
        startForeground(NOTIFICATION_ID, buildNotification());
        BridgeRuntime.setForegroundAlive(true);
        startServer();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        BridgeRuntime.setForegroundAlive(true);
        if (server == null || !server.isRunning()) startServer();
        updateNotification();
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (server != null) server.stop();
        server = null;
        BridgeRuntime.setForegroundAlive(false);
        instance = null;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    private synchronized void startServer() {
        if (server != null) server.stop();
        server = new LocalBridgeServer(getApplicationContext());
        server.start();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Furina Bridge",
                NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("Menjaga bridge lokal Furina tetap tersedia untuk Termux.");
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(channel);
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
                this,
                0,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        boolean accessibility = BridgeRuntime.accessibilityBound();
        String text = accessibility
                ? "Bridge lokal aktif • Accessibility terhubung"
                : "Bridge lokal aktif • Accessibility terputus";
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("Furina Bridge")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .setContentIntent(pending)
                .build();
    }

    private void updateNotification() {
        try {
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.notify(NOTIFICATION_ID, buildNotification());
        } catch (Throwable ignored) {}
    }
}
