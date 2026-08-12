package com.wynndev.furinaagentbridge;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class LocalBridgeServer {
    private final Context context;
    private ExecutorService pool;
    private volatile boolean running;
    private ServerSocket serverSocket;
    private Thread acceptThread;

    public LocalBridgeServer(Context context) {
        this.context = context.getApplicationContext();
    }

    public synchronized void start() {
        if (running) return;
        running = true;
        pool = Executors.newFixedThreadPool(3);
        acceptThread = new Thread(this::acceptLoop, "furina-bridge-listener");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    public synchronized void stop() {
        running = false;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        serverSocket = null;
        if (pool != null) pool.shutdownNow();
        pool = null;
    }

    public boolean isRunning() { return running; }

    private void acceptLoop() {
        try {
            serverSocket = new ServerSocket(8765, 8, InetAddress.getByName("127.0.0.1"));
            BridgeRuntime.setLastServerError(null);
            while (running) {
                Socket s = serverSocket.accept();
                if (!s.getInetAddress().isLoopbackAddress()) {
                    s.close();
                    continue;
                }
                ExecutorService p = pool;
                if (p != null) p.submit(() -> handle(s));
                else s.close();
            }
        } catch (Exception e) {
            if (running) BridgeRuntime.setLastServerError(e);
            running = false;
        }
    }

    private void handle(Socket socket) {
        try (Socket s = socket; InputStream in = s.getInputStream(); OutputStream out = s.getOutputStream()) {
            s.setSoTimeout(15000);
            byte[] headerRaw = readUntilHeaders(in, 32768);
            if (headerRaw == null) return;
            String headerText = new String(headerRaw, StandardCharsets.ISO_8859_1);
            String[] lines = headerText.split("\\r\\n");
            if (lines.length == 0) return;
            String[] first = lines[0].split(" ");
            if (first.length < 2) return;
            String method = first[0].toUpperCase(Locale.ROOT);
            String path = first[1].split("\\?")[0];
            Map<String, String> headers = new HashMap<>();
            for (int i = 1; i < lines.length; i++) {
                int p = lines[i].indexOf(':');
                if (p > 0) headers.put(lines[i].substring(0, p).trim().toLowerCase(Locale.ROOT), lines[i].substring(p + 1).trim());
            }
            int len = 0;
            try { len = Integer.parseInt(headers.getOrDefault("content-length", "0")); } catch (Exception ignored) {}
            if (len < 0 || len > 1_000_000) {
                writeJson(out, 413, new JSONObject().put("ok", false).put("error", "payload_too_large"));
                return;
            }
            byte[] body = readExact(in, len);
            if (body == null) {
                writeJson(out, 400, new JSONObject().put("ok", false).put("error", "incomplete_body"));
                return;
            }

            if ("GET".equals(method) && "/bootstrap".equals(path)) {
                if (!BridgePrefs.consumeBootstrapWindow(context)) {
                    writeJson(out, 403, new JSONObject().put("ok", false).put("error", "bootstrap_closed")
                            .put("hint", "Buka aplikasi Furina Bridge lalu coba lagi."));
                    return;
                }
                String token = BridgePrefs.getToken(context);
                BridgeRuntime.markAuthorizedClient();
                writeJson(out, 200, new JSONObject().put("ok", true).put("token", token).put("mode", "auto-pair"));
                return;
            }

            if (!"/health".equals(path) && !constantTimeEquals(BridgePrefs.getToken(context), headers.getOrDefault("x-furina-token", ""))) {
                writeJson(out, 401, new JSONObject().put("ok", false).put("error", "unauthorized"));
                return;
            }
            if (!"/health".equals(path)) BridgeRuntime.markAuthorizedClient();

            if ("GET".equals(method) && "/health".equals(path)) {
                writeJson(out, 200, BridgeRuntime.health(context));
                return;
            }
            if ("GET".equals(method) && "/apps".equals(path)) {
                writeJson(out, 200, installedApps());
                return;
            }

            FurinaAccessibilityService service = BridgeRuntime.accessibility();
            if (service == null) {
                writeJson(out, 503, new JSONObject()
                        .put("ok", false)
                        .put("error", "accessibility_unbound")
                        .put("hint", "Buka Furina Bridge lalu aktifkan ulang Accessibility jika HyperOS memutus servicenya."));
                return;
            }

            if ("GET".equals(method) && "/screen".equals(path)) {
                writeJson(out, 200, service.screenSnapshot());
            } else if ("GET".equals(method) && "/screenshot".equals(path)) {
                writeJson(out, 200, service.screenshot());
            } else if ("POST".equals(method) && "/action".equals(path)) {
                JSONObject action = new JSONObject(new String(body, StandardCharsets.UTF_8));
                writeJson(out, 200, service.performAction(action));
            } else {
                writeJson(out, 404, new JSONObject().put("ok", false).put("error", "not_found"));
            }
        } catch (Exception e) {
            BridgeRuntime.setLastServerError(e);
        }
    }


    private JSONObject installedApps() throws Exception {
        PackageManager pm = context.getPackageManager();
        Intent launcher = new Intent(Intent.ACTION_MAIN, null);
        launcher.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> resolved = new ArrayList<>(pm.queryIntentActivities(launcher, 0));
        resolved.sort(Comparator.comparing(r -> String.valueOf(r.loadLabel(pm)), String.CASE_INSENSITIVE_ORDER));
        JSONArray apps = new JSONArray();
        java.util.HashSet<String> seen = new java.util.HashSet<>();
        for (ResolveInfo r : resolved) {
            if (r.activityInfo == null || r.activityInfo.packageName == null) continue;
            String pkg = r.activityInfo.packageName;
            if (!seen.add(pkg)) continue;
            String label = String.valueOf(r.loadLabel(pm));
            apps.put(new JSONObject().put("label", label).put("package", pkg));
            if (apps.length() >= 250) break;
        }
        return new JSONObject().put("ok", true).put("apps", apps);
    }

    private byte[] readExact(InputStream in, int len) throws Exception {
        if (len == 0) return new byte[0];
        byte[] out = new byte[len];
        int offset = 0;
        while (offset < len) {
            int read = in.read(out, offset, len - offset);
            if (read < 0) return null;
            if (read == 0) continue;
            offset += read;
        }
        return out;
    }

    private byte[] readUntilHeaders(InputStream in, int limit) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        int state = 0;
        while (bos.size() < limit) {
            int b = in.read();
            if (b < 0) return null;
            bos.write(b);
            if ((state == 0 || state == 2) && b == '\r') state++;
            else if ((state == 1 || state == 3) && b == '\n') state++;
            else state = (b == '\r') ? 1 : 0;
            if (state == 4) return bos.toByteArray();
        }
        return null;
    }

    private void writeJson(OutputStream out, int status, JSONObject obj) throws Exception {
        byte[] body = obj.toString().getBytes(StandardCharsets.UTF_8);
        String reason;
        switch (status) {
            case 200: reason = "OK"; break;
            case 401: reason = "Unauthorized"; break;
            case 403: reason = "Forbidden"; break;
            case 404: reason = "Not Found"; break;
            case 413: reason = "Payload Too Large"; break;
            case 503: reason = "Service Unavailable"; break;
            default: reason = "Error";
        }
        String h = "HTTP/1.1 " + status + " " + reason + "\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: " + body.length + "\r\n" +
                "Connection: close\r\n\r\n";
        out.write(h.getBytes(StandardCharsets.ISO_8859_1));
        out.write(body);
        out.flush();
    }

    private boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null || a.length() != b.length()) return false;
        int v = 0;
        for (int i = 0; i < a.length(); i++) v |= a.charAt(i) ^ b.charAt(i);
        return v == 0;
    }
}
