#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"Bridge RC18 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"Bridge RC18 block marker missing {label}: start={a} end={b}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-device-control-bridge-rc18.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    java = app / "src/main/java/com/wynndev/furinaagentbridge"
    aidl = app / "src/main/aidl/com/wynndev/furinaagentbridge/IPrivilegedControl.aidl"
    service = java / "FurinaAccessibilityService.java"
    user_service = java / "PrivilegedUserService.java"
    privileged = java / "PrivilegedControl.java"
    gradle = app / "build.gradle"
    for path in (aidl, service, user_service, privileged, gradle):
        if not path.is_file():
            raise SystemExit(f"missing Bridge RC18 source: {path}")

    aidl.write_text(r'''package com.wynndev.furinaagentbridge;

interface IPrivilegedControl {
    boolean keyEvent(int keyCode);
    boolean tap(int x, int y);
    boolean swipe(int x1, int y1, int x2, int y2, int durationMs);
    boolean inputText(String text);
    String foregroundPackage();
    int uid();
    void destroy();
}
''', encoding="utf-8")

    user_service.write_text(r'''package com.wynndev.furinaagentbridge;

import android.os.SystemClock;
import android.system.Os;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.MotionEvent;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.lang.reflect.Method;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PrivilegedUserService extends IPrivilegedControl.Stub {
    private final Object lock = new Object();
    private final AtomicLong sequence = new AtomicLong();
    private Process shell;
    private BufferedWriter input;
    private BufferedReader output;
    private volatile Object inputManager;
    private volatile Method injectMethod;

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
        input = null;
        output = null;
        shell = null;
    }

    private String readLineUntil(long deadline) throws Exception {
        if (output == null) return null;
        StringBuilder line = new StringBuilder();
        while (SystemClock.uptimeMillis() < deadline) {
            if (output.ready()) {
                int c = output.read();
                if (c < 0) return null;
                if (c == '\n') return line.toString();
                if (c != '\r' && line.length() < 16000) line.append((char) c);
                continue;
            }
            if (shell == null || !shell.isAlive()) return null;
            SystemClock.sleep(8L);
        }
        throw new TimeoutException("privileged shell read timeout");
    }

    private boolean runFixed(String command) {
        synchronized (lock) {
            if (!ensureShell()) return false;
            String marker = "__FURINA_" + sequence.incrementAndGet() + "__";
            long deadline = SystemClock.uptimeMillis() + 1600L;
            try {
                input.write(command);
                input.write("\nprintf '" + marker + "%s\\n' $?\n");
                input.flush();
                while (SystemClock.uptimeMillis() < deadline) {
                    String line = readLineUntil(deadline);
                    if (line == null) break;
                    if (line.startsWith(marker)) {
                        return line.substring(marker.length()).trim().equals("0");
                    }
                }
            } catch (Throwable ignored) {}
            closeShell();
            return false;
        }
    }

    private String captureFixed(String command) {
        synchronized (lock) {
            if (!ensureShell()) return "";
            String marker = "__FURINA_CAPTURE_" + sequence.incrementAndGet() + "__";
            StringBuilder value = new StringBuilder();
            long deadline = SystemClock.uptimeMillis() + 2400L;
            try {
                input.write(command);
                input.write("\nprintf '\\n" + marker + "%s\\n' $?\n");
                input.flush();
                while (SystemClock.uptimeMillis() < deadline) {
                    String line = readLineUntil(deadline);
                    if (line == null) break;
                    if (line.startsWith(marker)) {
                        return line.substring(marker.length()).trim().equals("0") ? value.toString() : "";
                    }
                    if (value.length() < 12000) value.append(line).append('\n');
                }
            } catch (Throwable ignored) {}
            closeShell();
            return "";
        }
    }

    private boolean ensureInputManager() {
        if (inputManager != null && injectMethod != null) return true;
        synchronized (lock) {
            if (inputManager != null && injectMethod != null) return true;
            for (String className : new String[]{"android.hardware.input.InputManager", "android.hardware.input.InputManagerGlobal"}) {
                try {
                    Class<?> cls = Class.forName(className);
                    Method get = cls.getDeclaredMethod("getInstance");
                    get.setAccessible(true);
                    Object manager = get.invoke(null);
                    if (manager == null) continue;
                    for (Method method : manager.getClass().getMethods()) {
                        if (!"injectInputEvent".equals(method.getName()) || method.getParameterTypes().length != 2) continue;
                        method.setAccessible(true);
                        inputManager = manager;
                        injectMethod = method;
                        return true;
                    }
                    for (Method method : manager.getClass().getDeclaredMethods()) {
                        if (!"injectInputEvent".equals(method.getName()) || method.getParameterTypes().length != 2) continue;
                        method.setAccessible(true);
                        inputManager = manager;
                        injectMethod = method;
                        return true;
                    }
                } catch (Throwable ignored) {}
            }
            return false;
        }
    }

    private boolean inject(InputEvent event) {
        try {
            if (!ensureInputManager()) return false;
            Object result = injectMethod.invoke(inputManager, event, 2);
            return !(result instanceof Boolean) || Boolean.TRUE.equals(result);
        } catch (Throwable ignored) {
            inputManager = null;
            injectMethod = null;
            return false;
        }
    }

    private MotionEvent motion(long down, long now, int action, float x, float y) {
        MotionEvent event = MotionEvent.obtain(down, now, action, x, y, 0);
        event.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        return event;
    }

    private boolean injectTap(int x, int y) {
        long down = SystemClock.uptimeMillis();
        MotionEvent a = motion(down, down, MotionEvent.ACTION_DOWN, x, y);
        boolean first = inject(a);
        a.recycle();
        if (!first) return false;
        long upAt = Math.max(SystemClock.uptimeMillis(), down + 18L);
        MotionEvent b = motion(down, upAt, MotionEvent.ACTION_UP, x, y);
        boolean second = inject(b);
        b.recycle();
        return second;
    }

    private boolean injectSwipe(int x1, int y1, int x2, int y2, int durationMs) {
        int duration = Math.max(50, Math.min(durationMs, 3000));
        int steps = Math.max(3, Math.min(18, duration / 32));
        long down = SystemClock.uptimeMillis();
        MotionEvent start = motion(down, down, MotionEvent.ACTION_DOWN, x1, y1);
        boolean ok = inject(start);
        start.recycle();
        if (!ok) return false;
        for (int i = 1; i < steps; i++) {
            long target = down + ((long) duration * i / steps);
            long delay = target - SystemClock.uptimeMillis();
            if (delay > 0) SystemClock.sleep(delay);
            float f = i / (float) steps;
            MotionEvent move = motion(down, SystemClock.uptimeMillis(), MotionEvent.ACTION_MOVE,
                    x1 + (x2 - x1) * f, y1 + (y2 - y1) * f);
            ok = inject(move);
            move.recycle();
            if (!ok) return false;
        }
        long target = down + duration;
        long delay = target - SystemClock.uptimeMillis();
        if (delay > 0) SystemClock.sleep(delay);
        MotionEvent end = motion(down, SystemClock.uptimeMillis(), MotionEvent.ACTION_UP, x2, y2);
        ok = inject(end);
        end.recycle();
        return ok;
    }

    private boolean injectKey(int keyCode) {
        long now = SystemClock.uptimeMillis();
        KeyEvent down = new KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0);
        KeyEvent up = new KeyEvent(now, now + 10L, KeyEvent.ACTION_UP, keyCode, 0);
        return inject(down) && inject(up);
    }

    private boolean injectTextDirect(String text) {
        try {
            if (text == null || text.length() > 4000) return false;
            KeyCharacterMap map = KeyCharacterMap.load(KeyCharacterMap.VIRTUAL_KEYBOARD);
            KeyEvent[] events = map.getEvents(text.toCharArray());
            if (events == null || events.length == 0) return text.isEmpty();
            for (KeyEvent event : events) if (!inject(event)) return false;
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static String shellQuote(String value) {
        return "'" + String.valueOf(value).replace("'", "'\\''") + "'";
    }

    @Override public boolean keyEvent(int keyCode) {
        if (keyCode < 0 || keyCode > 300) return false;
        if (injectKey(keyCode)) return true;
        return runFixed("input keyevent " + keyCode);
    }

    @Override public boolean tap(int x, int y) {
        if (x < 0 || y < 0 || x > 10000 || y > 10000) return false;
        if (injectTap(x, y)) return true;
        return runFixed("input tap " + x + " " + y);
    }

    @Override public boolean swipe(int x1, int y1, int x2, int y2, int durationMs) {
        if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0 || x1 > 10000 || y1 > 10000 || x2 > 10000 || y2 > 10000) return false;
        int duration = Math.max(50, Math.min(durationMs, 3000));
        if (injectSwipe(x1, y1, x2, y2, duration)) return true;
        return runFixed("input swipe " + x1 + " " + y1 + " " + x2 + " " + y2 + " " + duration);
    }

    @Override public boolean inputText(String text) {
        if (text == null || text.length() > 4000) return false;
        if (injectTextDirect(text)) return true;
        if (text.indexOf('\n') >= 0 || text.indexOf('\r') >= 0) return false;
        return runFixed("input text " + shellQuote(text.replace(" ", "%s")));
    }

    @Override public String foregroundPackage() {
        String raw = captureFixed("dumpsys activity activities | grep -m 1 -E 'mResumedActivity|topResumedActivity'");
        Matcher m = Pattern.compile("([A-Za-z0-9_.$]+)/(?:[A-Za-z0-9_.$]+)").matcher(raw);
        return m.find() ? m.group(1) : "";
    }

    @Override public int uid() { return Os.getuid(); }

    @Override public void destroy() {
        synchronized (lock) { closeShell(); }
        System.exit(0);
    }
}
''', encoding="utf-8")

    privileged.write_text(r'''package com.wynndev.furinaagentbridge;

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
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import rikka.shizuku.Shizuku;

public final class PrivilegedControl {
    private static volatile IPrivilegedControl shizukuService;
    private static volatile boolean shizukuBinding;
    private static final Object SHIZUKU_LOCK = new Object();
    private static final RootShell ROOT = new RootShell();

    private PrivilegedControl() {}

    private static Shizuku.UserServiceArgs args(Context context) {
        return new Shizuku.UserServiceArgs(new ComponentName(context.getPackageName(), PrivilegedUserService.class.getName()))
                .daemon(true).processNameSuffix("privileged").tag("furina-control").version(10018);
    }

    private static final ServiceConnection CONNECTION = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            synchronized (SHIZUKU_LOCK) {
                shizukuService = IPrivilegedControl.Stub.asInterface(binder);
                shizukuBinding = false;
                SHIZUKU_LOCK.notifyAll();
            }
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            synchronized (SHIZUKU_LOCK) {
                shizukuService = null;
                shizukuBinding = false;
                SHIZUKU_LOCK.notifyAll();
            }
        }
    };

    public static boolean shizukuAvailable() {
        try { return Shizuku.pingBinder(); } catch (Throwable e) { return false; }
    }

    public static boolean shizukuPermission() {
        try { return shizukuAvailable() && Shizuku.checkSelfPermission() == PERMISSION_GRANTED; }
        catch (Throwable e) { return false; }
    }

    private static boolean binderAlive() {
        IPrivilegedControl service = shizukuService;
        if (service == null) return false;
        try { return service.asBinder().pingBinder(); } catch (Throwable e) { return false; }
    }

    public static synchronized boolean prepareShizuku(Context context, boolean requestPermission) {
        try {
            if (!shizukuAvailable()) return false;
            if (!shizukuPermission()) {
                if (requestPermission && !Shizuku.shouldShowRequestPermissionRationale()) Shizuku.requestPermission(1308);
                return false;
            }
            if (binderAlive()) return true;
            shizukuService = null;
            if (!shizukuBinding) {
                shizukuBinding = true;
                Shizuku.bindUserService(args(context), CONNECTION);
            }
            return false;
        } catch (Throwable e) {
            shizukuBinding = false;
            synchronized (SHIZUKU_LOCK) { SHIZUKU_LOCK.notifyAll(); }
            return false;
        }
    }

    private static IPrivilegedControl awaitShizuku(Context context, long maxWaitMs) {
        if (binderAlive()) return shizukuService;
        prepareShizuku(context, false);
        long wait = Math.max(0L, Math.min(maxWaitMs, 1200L));
        long deadline = android.os.SystemClock.uptimeMillis() + wait;
        synchronized (SHIZUKU_LOCK) {
            while (!binderAlive()) {
                long remaining = deadline - android.os.SystemClock.uptimeMillis();
                if (remaining <= 0L) break;
                try { SHIZUKU_LOCK.wait(Math.min(remaining, 250L)); }
                catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        return binderAlive() ? shizukuService : null;
    }

    public static boolean rootReady() { return ROOT.isReady(); }
    public static boolean prepareRoot() { return ROOT.prepare(); }

    public static boolean warm(Context context, String mode) {
        if ("normal".equals(mode)) return true;
        if ("shizuku".equals(mode)) return awaitShizuku(context, 900L) != null;
        if ("root".equals(mode)) return prepareRoot();
        return false;
    }

    public static boolean keyEvent(Context context, String mode, int code) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl service = awaitShizuku(context, 180L);
                return service != null && service.keyEvent(code);
            }
            if ("root".equals(mode)) return ROOT.keyEvent(code);
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean tap(Context context, String mode, int x, int y) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl service = awaitShizuku(context, 180L);
                return service != null && service.tap(x, y);
            }
            if ("root".equals(mode)) return ROOT.tap(x, y);
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean swipe(Context context, String mode, int x1, int y1, int x2, int y2, int duration) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl service = awaitShizuku(context, 180L);
                return service != null && service.swipe(x1, y1, x2, y2, duration);
            }
            if ("root".equals(mode)) return ROOT.swipe(x1, y1, x2, y2, duration);
        } catch (Throwable ignored) {}
        return false;
    }

    public static boolean inputText(Context context, String mode, String text) {
        try {
            if (text == null || text.length() > 4000) return false;
            if ("shizuku".equals(mode)) {
                IPrivilegedControl service = awaitShizuku(context, 180L);
                return service != null && service.inputText(text);
            }
            if ("root".equals(mode)) return ROOT.inputText(text);
        } catch (Throwable ignored) {}
        return false;
    }

    public static String foregroundPackage(Context context, String mode) {
        try {
            if ("shizuku".equals(mode)) {
                IPrivilegedControl service = awaitShizuku(context, 160L);
                return service == null ? "" : String.valueOf(service.foregroundPackage());
            }
            if ("root".equals(mode)) return ROOT.foregroundPackage();
        } catch (Throwable ignored) {}
        return "";
    }

    public static JSONObject status() throws Exception {
        JSONObject out = new JSONObject();
        out.put("ok", true);
        out.put("shizuku_available", shizukuAvailable());
        out.put("shizuku_permission", shizukuPermission());
        out.put("shizuku_ready", binderAlive());
        if (binderAlive()) try { out.put("shizuku_uid", shizukuService.uid()); } catch (Throwable ignored) {}
        out.put("root_ready", rootReady());
        return out;
    }

    private static String shellQuote(String value) {
        return "'" + String.valueOf(value).replace("'", "'\\''") + "'";
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
                    authorized = runLocked("test \"$(id -u)\" = 0", 8000L);
                    if (!authorized) close();
                    return authorized;
                } catch (Throwable e) {
                    close();
                    return false;
                }
            }
        }

        private String readLineUntil(long deadline) throws Exception {
            if (output == null) return null;
            StringBuilder line = new StringBuilder();
            while (android.os.SystemClock.uptimeMillis() < deadline) {
                if (output.ready()) {
                    int c = output.read();
                    if (c < 0) return null;
                    if (c == '\n') return line.toString();
                    if (c != '\r' && line.length() < 16000) line.append((char) c);
                    continue;
                }
                if (shell == null || !shell.isAlive()) return null;
                android.os.SystemClock.sleep(8L);
            }
            throw new TimeoutException("root shell read timeout");
        }

        private boolean runLocked(String command, long timeoutMs) {
            if (shell == null || !shell.isAlive() || input == null || output == null) return false;
            String marker = "__FURINA_ROOT_" + seq.incrementAndGet() + "__";
            long deadline = android.os.SystemClock.uptimeMillis() + Math.max(200L, timeoutMs);
            try {
                input.write(command);
                input.write("\nprintf '" + marker + "%s\\n' $?\n");
                input.flush();
                while (android.os.SystemClock.uptimeMillis() < deadline) {
                    String line = readLineUntil(deadline);
                    if (line == null) break;
                    if (line.startsWith(marker)) return line.substring(marker.length()).trim().equals("0");
                }
            } catch (Throwable ignored) {}
            return false;
        }

        private String captureLocked(String command, long timeoutMs) {
            if (shell == null || !shell.isAlive() || input == null || output == null) return "";
            String marker = "__FURINA_ROOT_CAPTURE_" + seq.incrementAndGet() + "__";
            StringBuilder value = new StringBuilder();
            long deadline = android.os.SystemClock.uptimeMillis() + Math.max(300L, timeoutMs);
            try {
                input.write(command);
                input.write("\nprintf '\\n" + marker + "%s\\n' $?\n");
                input.flush();
                while (android.os.SystemClock.uptimeMillis() < deadline) {
                    String line = readLineUntil(deadline);
                    if (line == null) break;
                    if (line.startsWith(marker)) return line.substring(marker.length()).trim().equals("0") ? value.toString() : "";
                    if (value.length() < 12000) value.append(line).append('\n');
                }
            } catch (Throwable ignored) {}
            return "";
        }

        private boolean run(String command) {
            synchronized (lock) {
                if (!isReady() && !prepare()) return false;
                boolean ok = runLocked(command, 1800L);
                if (!ok) close();
                return ok;
            }
        }

        private String capture(String command) {
            synchronized (lock) {
                if (!isReady() && !prepare()) return "";
                String value = captureLocked(command, 2600L);
                if (value.isEmpty() && (shell == null || !shell.isAlive())) close();
                return value;
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
            if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0 || x1 > 10000 || y1 > 10000 || x2 > 10000 || y2 > 10000) return false;
            int duration = Math.max(50, Math.min(durationMs, 3000));
            return run("input swipe " + x1 + " " + y1 + " " + x2 + " " + y2 + " " + duration);
        }
        boolean inputText(String text) {
            if (text == null || text.length() > 4000 || text.indexOf('\n') >= 0 || text.indexOf('\r') >= 0) return false;
            return run("input text " + shellQuote(text.replace(" ", "%s")));
        }
        String foregroundPackage() {
            String raw = capture("dumpsys activity activities | grep -m 1 -E 'mResumedActivity|topResumedActivity'");
            Matcher m = Pattern.compile("([A-Za-z0-9_.$]+)/(?:[A-Za-z0-9_.$]+)").matcher(raw);
            return m.find() ? m.group(1) : "";
        }
        private void close() {
            authorized = false;
            try { if (input != null) input.close(); } catch (Throwable ignored) {}
            try { if (output != null) output.close(); } catch (Throwable ignored) {}
            try { if (shell != null) shell.destroy(); } catch (Throwable ignored) {}
            input = null;
            output = null;
            shell = null;
        }
    }
}
''', encoding="utf-8")

    s = service.read_text(encoding="utf-8")

    s = rep(s, '    private static volatile String ACTIVE_CONTROL_MODE = "normal";\n', '', "remove global control mode")

    active = r'''    private String activeRootPackage() {
        return activeRootPackage("normal");
    }

    private String activeRootPackage(String explicitMode) {
        try {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root != null && root.getPackageName() != null) {
                String candidate = root.getPackageName().toString();
                if (!transientWindowPackage(candidate)) {
                    LAST_STABLE_PACKAGE = candidate;
                    return candidate;
                }
            }
        } catch (Throwable ignored) {}
        String mode = explicitMode == null ? "normal" : explicitMode.trim().toLowerCase(java.util.Locale.ROOT);
        if ("shizuku".equals(mode) || "root".equals(mode)) {
            try {
                String privilegedPackage = PrivilegedControl.foregroundPackage(this, mode);
                if (privilegedPackage != null && !privilegedPackage.isEmpty() && !transientWindowPackage(privilegedPackage)) {
                    LAST_STABLE_PACKAGE = privilegedPackage;
                    return privilegedPackage;
                }
            } catch (Throwable ignored) {}
        }
        if (LAST_STABLE_PACKAGE != null && !LAST_STABLE_PACKAGE.isEmpty()) return LAST_STABLE_PACKAGE;
        try {
            String persisted = sessionPrefs().getString(KEY_STABLE_FOREGROUND, "");
            if (persisted != null && !persisted.isEmpty()) {
                LAST_STABLE_PACKAGE = persisted;
                return persisted;
            }
        } catch (Throwable ignored) {}
        return "";
    }
'''
    s = block(s, "    private String activeRootPackage() {\n", "    private String stableForegroundPackage(AccessibilityEvent event) {\n", active, "explicit foreground capability")

    helpers = r'''    private String fastControlMode(JSONObject action) {
        String mode = action == null ? "normal" : action.optString("mode", "normal");
        mode = mode == null ? "normal" : mode.trim().toLowerCase(java.util.Locale.ROOT);
        return ("shizuku".equals(mode) || "root".equals(mode)) ? mode : "normal";
    }

    private boolean privilegedTapNode(JSONObject action, AccessibilityNodeInfo node) {
        String mode = fastControlMode(action);
        if ("normal".equals(mode) || node == null) return false;
        AccessibilityNodeInfo current = node;
        for (int depth = 0; depth < 6 && current != null; depth++) {
            Rect rect = new Rect();
            try { current.getBoundsInScreen(rect); } catch (Throwable ignored) {}
            if (!rect.isEmpty() && PrivilegedControl.tap(this, mode, rect.centerX(), rect.centerY())) return true;
            try { current = current.getParent(); } catch (Throwable ignored) { current = null; }
        }
        return false;
    }

    private boolean privilegedSwipeRect(JSONObject action, Rect rect, boolean backward, int durationMs) {
        String mode = fastControlMode(action);
        if ("normal".equals(mode) || rect == null || rect.isEmpty()) return false;
        int x = rect.centerX();
        int margin = Math.max(40, rect.height() / 5);
        int top = Math.min(rect.bottom - 1, rect.top + margin);
        int bottom = Math.max(rect.top + 1, rect.bottom - margin);
        if (bottom <= top) return false;
        return backward
                ? PrivilegedControl.swipe(this, mode, x, top, x, bottom, Math.max(120, durationMs))
                : PrivilegedControl.swipe(this, mode, x, bottom, x, top, Math.max(120, durationMs));
    }

    private boolean tapAction(JSONObject action) {
        int x = action.optInt("x", -1), y = action.optInt("y", -1);
        String mode = fastControlMode(action);
        if (!"normal".equals(mode) && PrivilegedControl.tap(this, mode, x, y)) return true;
        return tap(x, y);
    }

    private boolean swipeAction(JSONObject action) {
        int x1 = action.optInt("x1", -1), y1 = action.optInt("y1", -1);
        int x2 = action.optInt("x2", -1), y2 = action.optInt("y2", -1);
        int duration = action.optInt("duration_ms", 350);
        String mode = fastControlMode(action);
        if (!"normal".equals(mode) && PrivilegedControl.swipe(this, mode, x1, y1, x2, y2, duration)) return true;
        return swipe(x1, y1, x2, y2, duration);
    }
'''
    s = block(s, "    private String fastControlMode(JSONObject action) {\n", "    private static String fastNorm(String value) {\n", helpers, "explicit capability helpers")

    tap_node = r'''    private boolean tapNode(JSONObject action) {
        AccessibilityNodeInfo node = resolveNode(action);
        if (node == null) return false;
        AccessibilityNodeInfo current = node;
        for (int i = 0; i < 6 && current != null; i++) {
            if (current.isEnabled() && current.isClickable()
                    && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
            try { current = current.getParent(); } catch (Throwable ignored) { current = null; }
        }
        if (privilegedTapNode(action, node)) return true;
        Rect rect = new Rect();
        node.getBoundsInScreen(rect);
        return !rect.isEmpty() && tap(rect.centerX(), rect.centerY());
    }
'''
    s = block(s, "    private boolean tapNode(JSONObject action) {\n", "    private AccessibilityNodeInfo editableNode(AccessibilityNodeInfo start) {\n", tap_node, "semantic-first generic tap")

    generic_text = r'''    private boolean setText(JSONObject action, String text) {
        String mode = fastControlMode(action);
        if (isTermuxPackageFast(activeRootPackage(mode))) return false;
        AccessibilityNodeInfo node = editableNode(resolveNode(action));
        if (node == null) return false;
        if (textMatches(node, text)) return true;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);

        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                && waitForExactText(action, node, text, 650L)) return true;

        AccessibilityNodeInfo current = refreshEditable(action, node);
        if (textMatches(current, text)) return true;
        if (current == null) return false;
        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
                current = refreshEditable(action, current);
                if (current != null) {
                    if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                    boolean pasted = current.performAction(AccessibilityNodeInfo.ACTION_PASTE);
                    if (pasted && waitForExactText(action, current, text, 800L)) return true;
                }
            }
        } catch (Throwable ignored) {}
        current = refreshEditable(action, current);
        if (textMatches(current, text)) return true;
        if (current == null || "normal".equals(mode)) return false;
        if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        return PrivilegedControl.inputText(this, mode, text)
                && waitForExactText(action, current, text, 900L);
    }
'''
    s = block(s, "    private boolean setText(JSONObject action, String text) {\n", "    private boolean longPress(JSONObject action) {\n", generic_text, "semantic-first generic text")

    s = rep(s, "        String stablePackage = activeRootPackage();\n", "        String stablePackage = activeRootPackage(fastControlMode(action));\n", "mode-aware result package")

    tap_fast = r'''    private boolean tapTextFast(JSONObject action) {
        configureAgentAccessibility();
        int maxScrolls = Math.max(0, Math.min(action.optInt("max_scrolls", 0), 6));
        String mode = fastControlMode(action);
        for (int attempt = 0; attempt <= maxScrolls; attempt++) {
            if (isTermuxPackageFast(activeRootPackage(mode))) return false;
            AccessibilityNodeInfo node = fastFind(action);
            if (node != null) {
                AccessibilityNodeInfo current = node;
                for (int i = 0; i < 6 && current != null; i++) {
                    if (current.isEnabled() && current.isClickable()
                            && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
                    try { current = current.getParent(); } catch (Throwable ignored) { current = null; }
                }
                if (privilegedTapNode(action, node)) return true;
                Rect rect = new Rect();
                node.getBoundsInScreen(rect);
                if (!rect.isEmpty() && tap(rect.centerX(), rect.centerY())) return true;
            }
            if (attempt >= maxScrolls) break;
            long sequence = currentEventSeq();
            try {
                JSONObject scroll = new JSONObject().put("direction", "forward").put("mode", mode);
                if (!scrollBestFast(scroll)) break;
            } catch (Throwable ignored) { break; }
            waitFastEvent(sequence, 650L);
        }
        return false;
    }
'''
    s = block(s, "    private boolean tapTextFast(JSONObject action) {\n", "    private String fastEditableMeta(AccessibilityNodeInfo node) {\n", tap_fast, "semantic-first fast tap")

    fast_text = r'''    private boolean setTextFast(JSONObject action) {
        String mode = fastControlMode(action);
        if (isTermuxPackageFast(activeRootPackage(mode))) return false;
        String text = action.optString("text", "");
        if (text.length() > 4000) return false;
        AccessibilityNodeInfo node = fastEditable(action);
        if (node == null) return false;
        if (textMatches(node, text)) return true;
        if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);

        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            long deadline = System.currentTimeMillis() + 520L;
            while (System.currentTimeMillis() < deadline) {
                AccessibilityNodeInfo current = fastEditable(action);
                if (textMatches(current != null ? current : node, text)) return true;
                waitFastEvent(currentEventSeq(), 45L);
            }
        }
        AccessibilityNodeInfo current = fastEditable(action);
        if (textMatches(current, text)) return true;
        if (current == null) return false;
        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        try {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("Furina", text));
                current = fastEditable(action);
                if (current != null) {
                    if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                    if (current.performAction(AccessibilityNodeInfo.ACTION_PASTE)) {
                        long deadline = System.currentTimeMillis() + 800L;
                        while (System.currentTimeMillis() < deadline) {
                            AccessibilityNodeInfo check = fastEditable(action);
                            if (textMatches(check != null ? check : current, text)) return true;
                            waitFastEvent(currentEventSeq(), 55L);
                        }
                    }
                }
            }
        } catch (Throwable ignored) {}
        current = fastEditable(action);
        if (textMatches(current, text)) return true;
        if (current == null || "normal".equals(mode)) return false;
        if (!current.isFocused()) current.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        if (!nodeText(current).isEmpty() && !selectAllForReplace(current)) return false;
        if (!PrivilegedControl.inputText(this, mode, text)) return false;
        long deadline = System.currentTimeMillis() + 900L;
        while (System.currentTimeMillis() < deadline) {
            AccessibilityNodeInfo check = fastEditable(action);
            if (textMatches(check != null ? check : current, text)) return true;
            waitFastEvent(currentEventSeq(), 55L);
        }
        return textMatches(fastEditable(action), text);
    }
'''
    s = block(s, "    private boolean setTextFast(JSONObject action) {\n", "    private boolean imeFast(JSONObject action) {\n", fast_text, "semantic-first privileged text fallback")

    ime = r'''    private boolean imeFast(JSONObject action) {
        String mode = fastControlMode(action);
        if (isTermuxPackageFast(activeRootPackage(mode))) return false;
        configureAgentAccessibility();
        String optionalTarget = action == null ? "" : action.optString("optional_if_target_visible", "").trim();
        if (!optionalTarget.isEmpty()) {
            try {
                JSONObject resultProbe = new JSONObject().put("target", optionalTarget).put("result_mode", true).put("mode", mode);
                long sequence = currentEventSeq();
                long deadline = System.currentTimeMillis() + 850L;
                while (System.currentTimeMillis() < deadline) {
                    if (fastFind(resultProbe) != null) return true;
                    waitFastEvent(sequence, Math.min(100L, Math.max(1L, deadline - System.currentTimeMillis())));
                    sequence = currentEventSeq();
                }
            } catch (Throwable ignored) {}
        }
        AccessibilityNodeInfo node = fastEditable(action);
        if (node != null) {
            if (!node.isFocused()) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                    && node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId())) return true;
        }
        String role = action == null ? "" : action.optString("role", "");
        if ("search".equals(fastNorm(role)) && !"normal".equals(mode)
                && PrivilegedControl.keyEvent(this, mode, 66)) return true;
        try {
            if ("search".equals(fastNorm(role))) return tapTextFast(new JSONObject().put("role", "search").put("max_scrolls", 0).put("mode", mode));
        } catch (Throwable ignored) {}
        return false;
    }
'''
    s = block(s, "    private boolean imeFast(JSONObject action) {\n", "    private boolean scrollBestFast(JSONObject action) {\n", ime, "semantic-first IME")

    scroll = r'''    private boolean scrollBestFast(JSONObject action) {
        String mode = fastControlMode(action);
        if (isTermuxPackageFast(activeRootPackage(mode))) return false;
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        boolean backward = "backward".equalsIgnoreCase(action.optString("direction", "forward"));
        int semantic = backward ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD;
        Queue<AccessibilityNodeInfo> q = new ArrayDeque<>();
        q.add(root);
        AccessibilityNodeInfo best = null;
        long bestArea = -1L;
        int seen = 0;
        while (!q.isEmpty() && seen++ < 520) {
            AccessibilityNodeInfo node = q.remove();
            if (node.isScrollable() && node.isEnabled()) {
                Rect rect = new Rect();
                node.getBoundsInScreen(rect);
                long area = Math.max(0, rect.width()) * (long) Math.max(0, rect.height());
                if (area > bestArea) { best = node; bestArea = area; }
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) q.add(child);
            }
        }
        if (best != null && best.performAction(semantic)) return true;
        if (!"normal".equals(mode)) {
            Rect privilegedRect = new Rect();
            try { (best != null ? best : root).getBoundsInScreen(privilegedRect); } catch (Throwable ignored) {}
            if (privilegedSwipeRect(action, privilegedRect, backward, action.optInt("duration_ms", 320))) return true;
        }
        return scrollGlobal(action);
    }
'''
    s = block(s, "    private boolean scrollBestFast(JSONObject action) {\n", "    private boolean waitFastEvent(long afterSequence, long timeoutMs) {\n", scroll, "semantic-first scroll")

    sequence = r'''    private JSONObject runUiSequence(JSONObject action) throws JSONException {
        configureAgentAccessibility();
        JSONArray steps = action.optJSONArray("steps");
        JSONObject out = new JSONObject().put("type", "run_ui_sequence").put("ok", false).put("completed_steps", 0);
        if (steps == null || steps.length() == 0 || steps.length() > 18) return out.put("error", "invalid_sequence");

        String requestedMode = fastControlMode(action);
        boolean privilegedReady = "normal".equals(requestedMode) || PrivilegedControl.warm(this, requestedMode);
        String executionMode = privilegedReady ? requestedMode : "normal";
        out.put("requested_mode", requestedMode).put("execution_mode", executionMode).put("privileged_ready", privilegedReady);

        long started = System.currentTimeMillis();
        boolean leftTermux = false;
        for (int i = 0; i < steps.length(); i++) {
            String foregroundBefore = activeRootPackage(executionMode);
            if (foregroundBefore != null && !foregroundBefore.isEmpty() && !isTermuxPackageFast(foregroundBefore)) leftTermux = true;
            else if (leftTermux && isTermuxPackageFast(foregroundBefore)) {
                return out.put("cancelled_user_return", true).put("completed_steps", i).put("elapsed_ms", System.currentTimeMillis() - started);
            }
            JSONObject step = steps.optJSONObject(i);
            if (step == null) return out.put("failed_step", i).put("error", "invalid_step");
            if (!step.has("mode")) step.put("mode", executionMode);
            String type = step.optString("type", "");
            long eventSequence = currentEventSeq();
            long uiSignatureBefore = fastUiSignature();
            boolean ok;
            if ("open_app".equals(type)) ok = openApp(step.optString("package", ""));
            else if ("tap_text".equals(type)) ok = tapTextFast(step);
            else if ("set_text_best".equals(type)) ok = setTextFast(step);
            else if ("ime_best".equals(type)) ok = imeFast(step);
            else if ("scroll_best".equals(type)) ok = scrollBestFast(step);
            else if ("wait_text".equals(type)) ok = waitFastText(step, step.optLong("timeout_ms", 1100L));
            else if ("wait_package".equals(type)) ok = waitFastPackage(step.optString("package", ""), step.optLong("timeout_ms", 1300L));
            else if ("back".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_BACK);
                if (!ok && !"normal".equals(executionMode)) ok = PrivilegedControl.keyEvent(this, executionMode, 4);
            } else if ("home".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_HOME);
                if (!ok && !"normal".equals(executionMode)) ok = PrivilegedControl.keyEvent(this, executionMode, 3);
            } else if ("recents".equals(type)) {
                ok = performGlobalAction(GLOBAL_ACTION_RECENTS);
                if (!ok && !"normal".equals(executionMode)) ok = PrivilegedControl.keyEvent(this, executionMode, 187);
            } else return out.put("failed_step", i).put("failed_type", type).put("error", "unsupported_step");

            if (!ok) return out.put("failed_step", i).put("failed_type", type).put("error", "step_failed")
                    .put("package", activeRootPackage(executionMode)).put("event_seq", currentEventSeq())
                    .put("elapsed_ms", System.currentTimeMillis() - started);
            if (step.optBoolean("require_change", false)
                    && !waitFastUiChange(uiSignatureBefore, eventSequence, step.optLong("transition_timeout_ms", 2200L))) {
                return out.put("failed_step", i).put("failed_type", type).put("error", "transition_not_observed")
                        .put("package", activeRootPackage(executionMode)).put("event_seq", currentEventSeq())
                        .put("elapsed_ms", System.currentTimeMillis() - started);
            }
            out.put("completed_steps", i + 1);
            String foregroundAfter = activeRootPackage(executionMode);
            if (foregroundAfter != null && !foregroundAfter.isEmpty() && !isTermuxPackageFast(foregroundAfter)) leftTermux = true;
            else if (leftTermux && isTermuxPackageFast(foregroundAfter)) {
                return out.put("cancelled_user_return", true).put("completed_steps", i + 1)
                        .put("elapsed_ms", System.currentTimeMillis() - started);
            }
            if (i + 1 < steps.length() && !"wait_text".equals(type) && !"wait_package".equals(type)) {
                long nextTimeout;
                if ("open_app".equals(type) || "ime_best".equals(type)) nextTimeout = 3200L;
                else if ("tap_text".equals(type) || "set_text_best".equals(type)) nextTimeout = 1800L;
                else nextTimeout = 0L;
                if (nextTimeout > 0L) awaitFastNext(steps, i + 1, eventSequence, nextTimeout);
            }
        }
        return out.put("ok", true).put("elapsed_ms", System.currentTimeMillis() - started)
                .put("package", activeRootPackage(executionMode));
    }
'''
    s = block(s, "    private JSONObject runUiSequence(JSONObject action) throws JSONException {\n", "    private boolean scrollGlobal(JSONObject action) {\n", sequence, "explicit mode semantic sequence")

    service.write_text(s, encoding="utf-8")

    g = gradle.read_text(encoding="utf-8")
    g = rep(g, "        versionCode 10017", "        versionCode 10018", "Bridge versionCode")
    g = rep(g, "        versionName '1.0.0-rc17'", "        versionName '1.0.0-rc18'", "Bridge versionName")
    gradle.write_text(g, encoding="utf-8")

    final = service.read_text(encoding="utf-8")
    checks = (
        'return activeRootPackage("normal")', 'activeRootPackage(executionMode)',
        'performAction(AccessibilityNodeInfo.ACTION_CLICK)', 'if (privilegedTapNode(action, node)) return true',
        'if (best != null && best.performAction(semantic)) return true', 'PrivilegedControl.inputText(this, mode, text)',
        'ok = performGlobalAction(GLOBAL_ACTION_BACK)', 'requested_mode', 'execution_mode',
    )
    missing = [needle for needle in checks if needle not in final]
    if missing:
        raise SystemExit("Bridge RC18 service incomplete: " + ", ".join(missing))
    if "ACTIVE_CONTROL_MODE" in final:
        raise SystemExit("Bridge RC18 leaked global control mode remains")

    p = privileged.read_text(encoding="utf-8")
    u = user_service.read_text(encoding="utf-8")
    required_priv = (
        ".version(10018)", "SHIZUKU_LOCK.wait", "SHIZUKU_LOCK.notifyAll", "awaitShizuku(context, 900L)",
        "boolean inputText(Context context", "readLineUntil", "TimeoutException",
    )
    if any(x not in p for x in required_priv):
        raise SystemExit("Bridge RC18 privileged controller incomplete")
    required_user = ("boolean inputText(String text)", "KeyCharacterMap", "injectTextDirect", "readLineUntil", "TimeoutException")
    if any(x not in u for x in required_user):
        raise SystemExit("Bridge RC18 UserService incomplete")
    if "while ((line = output.readLine())" in p or "while ((line = output.readLine())" in u:
        raise SystemExit("Bridge RC18 unbounded shell read remains")
    if "versionCode 10018" not in g or "versionName '1.0.0-rc18'" not in g:
        raise SystemExit("Bridge RC18 version missing")
    print("Furina Bridge RC18 semantic-first bounded privileged control: OK")


if __name__ == "__main__":
    main()
