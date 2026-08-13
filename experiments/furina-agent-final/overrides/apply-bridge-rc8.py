#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Bridge RC8 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-bridge-rc8.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    java = app / "src/main/java/com/wynndev/furinaagentbridge"
    aidl = app / "src/main/aidl/com/wynndev/furinaagentbridge"
    gradle = app / "build.gradle"
    manifest = app / "src/main/AndroidManifest.xml"
    server = java / "LocalBridgeServer.java"
    runtime = java / "BridgeRuntime.java"
    boot = java / "BootReceiver.java"
    for p in (gradle, manifest, server, runtime, boot):
        if not p.is_file():
            raise SystemExit(f"missing Bridge RC8 source: {p}")

    gradle_props = root / "gradle.properties"
    props = gradle_props.read_text(encoding="utf-8") if gradle_props.exists() else ""
    if not any(line.strip() == "android.useAndroidX=true" for line in props.splitlines()):
        props = props.rstrip() + "\nandroid.useAndroidX=true\n"
        gradle_props.write_text(props, encoding="utf-8")

    # Shizuku's current design prefers a persistent Binder UserService over
    # spawning a remote shell process for every action.
    g = gradle.read_text(encoding="utf-8")
    g = replace_once(g, "        versionCode 10007", "        versionCode 10008", "versionCode")
    g = replace_once(g, "        versionName '1.0.0-rc7'", "        versionName '1.0.0-rc8'", "versionName")
    g = replace_once(
        g,
        '''    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}''',
        '''    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }

    buildFeatures {
        aidl true
    }
}

dependencies {
    implementation 'dev.rikka.shizuku:api:13.1.5'
    implementation 'dev.rikka.shizuku:provider:13.1.5'
}''',
        "Shizuku dependencies",
    )
    gradle.write_text(g, encoding="utf-8")

    m = manifest.read_text(encoding="utf-8")
    m = replace_once(
        m,
        '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n',
        '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />\n',
        "exact alarm permission",
    )
    m = replace_once(
        m,
        '''        <provider
            android:name=".UpdateFileProvider"
            android:authorities="${applicationId}.updateprovider"
            android:exported="false"
            android:grantUriPermissions="true" />
''',
        '''        <provider
            android:name=".UpdateFileProvider"
            android:authorities="${applicationId}.updateprovider"
            android:exported="false"
            android:grantUriPermissions="true" />

        <provider
            android:name="rikka.shizuku.ShizukuProvider"
            android:authorities="${applicationId}.shizuku"
            android:enabled="true"
            android:exported="true"
            android:multiprocess="false"
            android:permission="android.permission.INTERACT_ACROSS_USERS_FULL" />
''',
        "Shizuku provider",
    )
    m = replace_once(
        m,
        '''        <receiver
            android:name=".BootReceiver"''',
        '''        <receiver
            android:name=".ReminderReceiver"
            android:enabled="true"
            android:exported="false" />

        <receiver
            android:name=".BootReceiver"''',
        "reminder receiver",
    )
    manifest.write_text(m, encoding="utf-8")

    aidl.mkdir(parents=True, exist_ok=True)
    (aidl / "IPrivilegedControl.aidl").write_text(r'''package com.wynndev.furinaagentbridge;

interface IPrivilegedControl {
    boolean keyEvent(int keyCode);
    boolean tap(int x, int y);
    boolean swipe(int x1, int y1, int x2, int y2, int durationMs);
    int uid();
    void destroy();
}
''', encoding="utf-8")

    (java / "PrivilegedUserService.java").write_text(r'''package com.wynndev.furinaagentbridge;

import android.system.Os;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.concurrent.atomic.AtomicLong;

public class PrivilegedUserService extends IPrivilegedControl.Stub {
    private final Object lock = new Object();
    private final AtomicLong sequence = new AtomicLong();
    private Process shell;
    private BufferedWriter input;
    private BufferedReader output;

    public PrivilegedUserService() {}

    private boolean ensureShell() {
        synchronized (lock) {
            try {
                if (shell != null && shell.isAlive() && input != null && output != null) return true;
                closeShell();
                shell = new ProcessBuilder("sh").redirectErrorStream(true).start();
                input = new BufferedWriter(new OutputStreamWriter(shell.getOutputStream()));
                output = new BufferedReader(new InputStreamReader(shell.getInputStream()));
                return shell.isAlive();
            } catch (Throwable e) {
                closeShell();
                return false;
            }
        }
    }

    private void closeShell() {
        try { if (input != null) input.close(); } catch (Throwable ignored) {}
        try { if (output != null) output.close(); } catch (Throwable ignored) {}
        try { if (shell != null) shell.destroy(); } catch (Throwable ignored) {}
        input = null; output = null; shell = null;
    }

    private boolean runFixed(String command) {
        synchronized (lock) {
            if (!ensureShell()) return false;
            String marker = "__FURINA_" + sequence.incrementAndGet() + "__";
            try {
                input.write(command);
                input.write("\nprintf '" + marker + "%s\\n' $?\n");
                input.flush();
                String line;
                while ((line = output.readLine()) != null) {
                    if (line.startsWith(marker)) return line.substring(marker.length()).trim().equals("0");
                }
            } catch (Throwable ignored) {}
            closeShell();
            return false;
        }
    }

    @Override public boolean keyEvent(int keyCode) {
        if (keyCode < 0 || keyCode > 300) return false;
        return runFixed("input keyevent " + keyCode);
    }

    @Override public boolean tap(int x, int y) {
        if (x < 0 || y < 0 || x > 10000 || y > 10000) return false;
        return runFixed("input tap " + x + " " + y);
    }

    @Override public boolean swipe(int x1, int y1, int x2, int y2, int durationMs) {
        if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0) return false;
        int duration = Math.max(50, Math.min(durationMs, 3000));
        return runFixed("input swipe " + x1 + " " + y1 + " " + x2 + " " + y2 + " " + duration);
    }

    @Override public int uid() { return Os.getuid(); }

    @Override public void destroy() {
        synchronized (lock) { closeShell(); }
        System.exit(0);
    }
}
''', encoding="utf-8")

    (java / "PrivilegedControl.java").write_text(r'''package com.wynndev.furinaagentbridge;

import static android.content.pm.PackageManager.PERMISSION_GRANTED;

import android.content.ComponentName;
import android.content.Context;
import android.content.ServiceConnection;
import android.os.IBinder;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.concurrent.atomic.AtomicLong;

import rikka.shizuku.Shizuku;

public final class PrivilegedControl {
    private static volatile IPrivilegedControl shizukuService;
    private static volatile boolean shizukuBinding;
    private static final RootShell ROOT = new RootShell();

    private PrivilegedControl() {}

    private static Shizuku.UserServiceArgs args(Context context) {
        return new Shizuku.UserServiceArgs(new ComponentName(context.getPackageName(), PrivilegedUserService.class.getName()))
                .daemon(true).processNameSuffix("privileged").tag("furina-control").version(10008);
    }

    private static final ServiceConnection CONNECTION = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            shizukuService = IPrivilegedControl.Stub.asInterface(binder);
            shizukuBinding = false;
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            shizukuService = null;
            shizukuBinding = false;
        }
    };

    public static boolean shizukuAvailable() {
        try { return Shizuku.pingBinder(); } catch (Throwable e) { return false; }
    }

    public static boolean shizukuPermission() {
        try { return shizukuAvailable() && Shizuku.checkSelfPermission() == PERMISSION_GRANTED; }
        catch (Throwable e) { return false; }
    }

    public static synchronized boolean prepareShizuku(Context context, boolean requestPermission) {
        try {
            if (!shizukuAvailable()) return false;
            if (!shizukuPermission()) {
                if (requestPermission && !Shizuku.shouldShowRequestPermissionRationale()) Shizuku.requestPermission(1308);
                return false;
            }
            if (shizukuService != null) {
                try { if (shizukuService.asBinder().pingBinder()) return true; } catch (Throwable ignored) {}
                shizukuService = null;
            }
            if (!shizukuBinding) {
                shizukuBinding = true;
                Shizuku.bindUserService(args(context), CONNECTION);
            }
            return shizukuService != null;
        } catch (Throwable e) {
            shizukuBinding = false;
            return false;
        }
    }

    private static IPrivilegedControl shizuku(Context context) {
        prepareShizuku(context, false);
        return shizukuService;
    }

    public static boolean rootReady() { return ROOT.isReady(); }
    public static boolean prepareRoot() { return ROOT.prepare(); }

    public static boolean keyEvent(Context context, String mode, int code) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl s = shizuku(context);
                return s != null && s.keyEvent(code);
            }
            if ("root".equals(mode)) return ROOT.keyEvent(code);
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean tap(Context context, String mode, int x, int y) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl s = shizuku(context);
                return s != null && s.tap(x, y);
            }
            if ("root".equals(mode)) return ROOT.tap(x, y);
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean swipe(Context context, String mode, int x1, int y1, int x2, int y2, int duration) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl s = shizuku(context);
                return s != null && s.swipe(x1, y1, x2, y2, duration);
            }
            if ("root".equals(mode)) return ROOT.swipe(x1, y1, x2, y2, duration);
        } catch (Throwable ignored) {}
        return false;
    }

    public static JSONObject status() throws Exception {
        JSONObject out = new JSONObject();
        out.put("ok", true);
        out.put("shizuku_available", shizukuAvailable());
        out.put("shizuku_permission", shizukuPermission());
        out.put("shizuku_ready", shizukuPermission());
        out.put("root_ready", rootReady());
        return out;
    }

    private static final class RootShell {
        private final Object lock = new Object();
        private final AtomicLong seq = new AtomicLong();
        private Process shell;
        private BufferedWriter input;
        private BufferedReader output;
        private boolean authorized;

        boolean isReady() {
            synchronized (lock) { return authorized && shell != null && shell.isAlive(); }
        }

        boolean prepare() {
            synchronized (lock) {
                if (isReady()) return true;
                try {
                    close();
                    shell = new ProcessBuilder("su").redirectErrorStream(true).start();
                    input = new BufferedWriter(new OutputStreamWriter(shell.getOutputStream()));
                    output = new BufferedReader(new InputStreamReader(shell.getInputStream()));
                    authorized = runLocked("test \"$(id -u)\" = 0");
                    return authorized;
                } catch (Throwable e) {
                    close();
                    return false;
                }
            }
        }

        private boolean runLocked(String command) {
            if (shell == null || !shell.isAlive() || input == null || output == null) return false;
            String marker = "__FURINA_ROOT_" + seq.incrementAndGet() + "__";
            try {
                input.write(command);
                input.write("\nprintf '" + marker + "%s\\n' $?\n");
                input.flush();
                String line;
                while ((line = output.readLine()) != null) {
                    if (line.startsWith(marker)) return line.substring(marker.length()).trim().equals("0");
                }
            } catch (Throwable ignored) {}
            return false;
        }

        private boolean run(String command) {
            synchronized (lock) {
                if (!isReady() && !prepare()) return false;
                boolean ok = runLocked(command);
                if (!ok && (shell == null || !shell.isAlive())) close();
                return ok;
            }
        }

        boolean keyEvent(int keyCode) {
            if (keyCode < 0 || keyCode > 300) return false;
            return run("input keyevent " + keyCode);
        }
        boolean tap(int x, int y) {
            if (x < 0 || y < 0 || x > 10000 || y > 10000) return false;
            return run("input tap " + x + " " + y);
        }
        boolean swipe(int x1, int y1, int x2, int y2, int durationMs) {
            if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0) return false;
            int d = Math.max(50, Math.min(durationMs, 3000));
            return run("input swipe " + x1 + " " + y1 + " " + x2 + " " + y2 + " " + d);
        }
        private void close() {
            authorized = false;
            try { if (input != null) input.close(); } catch (Throwable ignored) {}
            try { if (output != null) output.close(); } catch (Throwable ignored) {}
            try { if (shell != null) shell.destroy(); } catch (Throwable ignored) {}
            input = null; output = null; shell = null;
        }
    }
}
''', encoding="utf-8")

    (java / "ReminderScheduler.java").write_text(r'''package com.wynndev.furinaagentbridge;

import android.app.AlarmManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.atomic.AtomicInteger;

public final class ReminderScheduler {
    private static final String PREF = "furina_reminders";
    private static final String KEY = "items";
    private static final String CHANNEL = "furina_reminders";
    private static final AtomicInteger SEQ = new AtomicInteger((int)(System.currentTimeMillis() & 0x3fffffff));

    private ReminderScheduler() {}

    public static synchronized JSONObject schedule(Context context, long atMs, String text) throws Exception {
        if (atMs <= System.currentTimeMillis() + 500L) return new JSONObject().put("ok", false).put("error", "invalid_time");
        int id = SEQ.incrementAndGet() & 0x7fffffff;
        String body = text == null || text.trim().isEmpty() ? "Pengingat" : text.trim();
        JSONObject item = new JSONObject().put("id", id).put("at_ms", atMs).put("text", body.substring(0, Math.min(500, body.length())));
        JSONArray items = load(context);
        items.put(item);
        save(context, items);
        arm(context, item);
        return new JSONObject().put("ok", true).put("id", id).put("at_ms", atMs);
    }

    private static PendingIntent pending(Context context, JSONObject item) {
        int id = item.optInt("id", 1);
        Intent intent = new Intent(context, ReminderReceiver.class)
                .setAction("com.wynndev.furinaagentbridge.REMINDER." + id)
                .putExtra("id", id)
                .putExtra("text", item.optString("text", "Pengingat"));
        return PendingIntent.getBroadcast(context, id, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void arm(Context context, JSONObject item) throws Exception {
        AlarmManager alarm = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarm == null) throw new IllegalStateException("alarm_unavailable");
        long at = item.getLong("at_ms");
        PendingIntent pi = pending(context, item);
        if (Build.VERSION.SDK_INT >= 31 && alarm.canScheduleExactAlarms()) {
            alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
        } else if (Build.VERSION.SDK_INT >= 23) {
            alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
        } else {
            alarm.set(AlarmManager.RTC_WAKEUP, at, pi);
        }
    }

    public static synchronized void restoreAll(Context context) {
        try {
            JSONArray old = load(context);
            JSONArray keep = new JSONArray();
            long now = System.currentTimeMillis();
            for (int i = 0; i < old.length(); i++) {
                JSONObject item = old.optJSONObject(i);
                if (item == null || item.optLong("at_ms", 0L) <= now) continue;
                try { arm(context, item); keep.put(item); } catch (Throwable ignored) {}
            }
            save(context, keep);
        } catch (Throwable ignored) {}
    }

    public static synchronized void fire(Context context, int id, String text) {
        ensureChannel(context);
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            android.app.Notification.Builder b = Build.VERSION.SDK_INT >= 26
                    ? new android.app.Notification.Builder(context, CHANNEL)
                    : new android.app.Notification.Builder(context);
            b.setContentTitle("Furina")
                    .setContentText(text == null || text.isEmpty() ? "Pengingat" : text)
                    .setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setAutoCancel(true);
            try { nm.notify(id, b.build()); } catch (Throwable ignored) {}
        }
        try {
            JSONArray old = load(context), keep = new JSONArray();
            for (int i = 0; i < old.length(); i++) {
                JSONObject item = old.optJSONObject(i);
                if (item != null && item.optInt("id", -1) != id) keep.put(item);
            }
            save(context, keep);
        } catch (Throwable ignored) {}
    }

    private static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL, "Pengingat Furina", NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Pengingat yang dijadwalkan Furina");
        nm.createNotificationChannel(channel);
    }

    private static JSONArray load(Context context) {
        SharedPreferences p = context.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        try { return new JSONArray(p.getString(KEY, "[]")); } catch (Throwable e) { return new JSONArray(); }
    }

    private static void save(Context context, JSONArray array) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().putString(KEY, array.toString()).apply();
    }
}
''', encoding="utf-8")

    (java / "ReminderReceiver.java").write_text(r'''package com.wynndev.furinaagentbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class ReminderReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        ReminderScheduler.fire(context, intent.getIntExtra("id", 1), intent.getStringExtra("text"));
    }
}
''', encoding="utf-8")

    (java / "DeviceControl.java").write_text(r'''package com.wynndev.furinaagentbridge;

import android.content.Context;
import android.content.Intent;

import org.json.JSONObject;

public final class DeviceControl {
    private DeviceControl() {}

    public static JSONObject status(Context context) throws Exception {
        JSONObject out = PrivilegedControl.status();
        out.put("normal_ready", true);
        out.put("accessibility", BridgeRuntime.accessibilityBound());
        return out;
    }

    public static JSONObject perform(Context context, JSONObject action) throws Exception {
        String type = action.optString("type", "");
        String mode = action.optString("mode", "normal").toLowerCase();
        if (!mode.equals("normal") && !mode.equals("shizuku") && !mode.equals("root")) mode = "normal";

        if ("status".equals(type)) return status(context);
        if ("prepare_shizuku".equals(type)) {
            boolean ready = PrivilegedControl.prepareShizuku(context, true);
            return status(context).put("ok", ready || PrivilegedControl.shizukuPermission())
                    .put("message", ready ? "Shizuku siap" : (PrivilegedControl.shizukuPermission() ? "Shizuku sedang disiapkan" : "Izinkan Furina Bridge di Shizuku"));
        }
        if ("prepare_root".equals(type)) {
            boolean ready = PrivilegedControl.prepareRoot();
            return status(context).put("ok", ready).put("message", ready ? "Root siap" : "Izin root belum diberikan");
        }
        if ("schedule_reminder".equals(type)) {
            return ReminderScheduler.schedule(context, action.optLong("at_ms", 0L), action.optString("text", "Pengingat"));
        }
        if ("open_app".equals(type)) {
            String pkg = action.optString("package", "");
            Intent launch = pkg.isEmpty() ? null : context.getPackageManager().getLaunchIntentForPackage(pkg);
            if (launch == null) return new JSONObject().put("ok", false).put("error", "app_not_found");
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(launch);
            return new JSONObject().put("ok", true).put("type", type).put("path", "native");
        }

        int key = "back".equals(type) ? 4 : "home".equals(type) ? 3 : "recents".equals(type) ? 187 : -1;
        if (key >= 0) {
            boolean ok = !mode.equals("normal") && PrivilegedControl.keyEvent(context, mode, key);
            if (!ok) ok = accessibility(context, new JSONObject().put("type", type));
            return new JSONObject().put("ok", ok).put("type", type).put("path", ok && !mode.equals("normal") ? mode : "accessibility");
        }
        if ("tap".equals(type)) {
            int x = action.optInt("x", -1), y = action.optInt("y", -1);
            boolean ok = !mode.equals("normal") && PrivilegedControl.tap(context, mode, x, y);
            if (!ok) ok = accessibility(context, action);
            return new JSONObject().put("ok", ok).put("type", type);
        }
        if ("swipe".equals(type)) {
            int x1=action.optInt("x1",-1), y1=action.optInt("y1",-1), x2=action.optInt("x2",-1), y2=action.optInt("y2",-1);
            int d=action.optInt("duration_ms",350);
            boolean ok = !mode.equals("normal") && PrivilegedControl.swipe(context, mode, x1,y1,x2,y2,d);
            if (!ok) ok = accessibility(context, action);
            return new JSONObject().put("ok", ok).put("type", type);
        }
        return new JSONObject().put("ok", false).put("error", "unsupported_control");
    }

    private static boolean accessibility(Context context, JSONObject action) {
        FurinaAccessibilityService service = BridgeRuntime.accessibility();
        if (service == null) return false;
        try { return service.performAction(action).optBoolean("ok", false); }
        catch (Throwable e) { return false; }
    }
}
''', encoding="utf-8")

    # Authenticated direct endpoint is evaluated before Accessibility presence,
    # so reminders/native/privileged control remain available independently.
    s = server.read_text(encoding="utf-8")
    s = replace_once(
        s,
        '''            if ("GET".equals(method) && "/apps".equals(path)) {
                writeJson(out, 200, installedApps());
                return;
            }

            FurinaAccessibilityService service = BridgeRuntime.accessibility();
''',
        '''            if ("GET".equals(method) && "/apps".equals(path)) {
                writeJson(out, 200, installedApps());
                return;
            }
            if ("GET".equals(method) && "/control/status".equals(path)) {
                writeJson(out, 200, DeviceControl.status(context));
                return;
            }
            if ("POST".equals(method) && "/control".equals(path)) {
                JSONObject control = new JSONObject(new String(body, StandardCharsets.UTF_8));
                writeJson(out, 200, DeviceControl.perform(context, control));
                return;
            }

            FurinaAccessibilityService service = BridgeRuntime.accessibility();
''',
        "control endpoint before Accessibility gate",
    )
    server.write_text(s, encoding="utf-8")

    r = runtime.read_text(encoding="utf-8")
    if 'out.put("version", "1.0.0-rc1");' in r:
        r = r.replace('out.put("version", "1.0.0-rc1");', 'out.put("version", "1.0.0-rc8");', 1)
    elif 'out.put("version", "1.0.0-rc7");' in r:
        r = r.replace('out.put("version", "1.0.0-rc7");', 'out.put("version", "1.0.0-rc8");', 1)
    else:
        raise SystemExit("Bridge RC8 runtime version anchor missing")
    runtime.write_text(r, encoding="utf-8")

    bt = boot.read_text(encoding="utf-8")
    bt = replace_once(
        bt,
        '''    public void onReceive(Context context, Intent intent) {
        if (BridgePrefs.isPersistentEnabled(context)) {
''',
        '''    public void onReceive(Context context, Intent intent) {
        ReminderScheduler.restoreAll(context);
        if (BridgePrefs.isPersistentEnabled(context)) {
''',
        "restore reminders on boot",
    )
    boot.write_text(bt, encoding="utf-8")

    required = [
        (gradle, "dev.rikka.shizuku:api:13.1.5"),
        (gradle, "versionCode 10008"),
        (manifest, "rikka.shizuku.ShizukuProvider"),
        (manifest, ".ReminderReceiver"),
        (server, '"/control"'),
        (runtime, '"1.0.0-rc8"'),
        (boot, "ReminderScheduler.restoreAll(context)"),
        (java / "DeviceControl.java", "prepare_shizuku"),
        (java / "PrivilegedControl.java", "Shizuku.bindUserService"),
        (java / "ReminderScheduler.java", "setExactAndAllowWhileIdle"),
        (aidl / "IPrivilegedControl.aidl", "boolean keyEvent"),
    ]
    missing = [needle for pth, needle in required if needle not in pth.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("Bridge RC8 incomplete: " + ", ".join(missing))
    print("Furina Bridge RC8 direct control + Shizuku/root + persistent reminder transform: OK")


if __name__ == "__main__":
    main()
