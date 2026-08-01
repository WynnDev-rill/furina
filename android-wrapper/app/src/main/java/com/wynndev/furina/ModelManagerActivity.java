package com.wynndev.furina;

import android.Manifest;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ModelManagerActivity extends AppCompatActivity {
    private static final int BG = Color.rgb(8, 17, 31);
    private static final int CARD = Color.rgb(17, 31, 49);
    private static final int TEXT = Color.rgb(238, 246, 255);
    private static final int MUTED = Color.rgb(163, 184, 204);
    private static final int ACCENT = Color.rgb(138, 216, 255);
    private static final String PREFS = "furina_model_manager";
    private static final String ACTIVE_MODEL = "active_model";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Map<String, Long> downloadIds = new HashMap<>();
    private final Map<String, ProgressBar> progressBars = new HashMap<>();
    private final Map<String, TextView> statusViews = new HashMap<>();
    private final Map<String, JSONObject> models = new HashMap<>();
    private LinearLayout list;
    private boolean receiverRegistered;
    private JSONObject pendingDownloadModel;

    private final ActivityResultLauncher<String> notificationPermission = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(), granted -> {
            JSONObject pending = pendingDownloadModel;
            pendingDownloadModel = null;
            if (pending != null) {
                if (!granted) {
                    Toast.makeText(this, "Unduhan tetap berjalan, tetapi progres mungkin tidak terlihat di notifikasi.", Toast.LENGTH_LONG).show();
                }
                startDownloadInternal(pending);
            }
        }
    );

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
            for (Map.Entry<String, Long> entry : downloadIds.entrySet()) {
                if (entry.getValue() == id) {
                    finishDownload(entry.getKey(), id);
                    break;
                }
            }
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        registerReceiverSafely();
        buildUi();
        loadCatalog();
        handler.post(progressPoller);
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(dp(18), dp(20), dp(18), dp(32));
        scroll.addView(list, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        list.addView(text("Model AI Furina", 25, TEXT, true));
        TextView intro = text("Unduh, pilih, dan hapus model offline. Unduhan memakai sistem Android sehingga tetap berjalan saat aplikasi ditutup.", 14, MUTED, false);
        intro.setPadding(0, dp(7), 0, dp(8));
        list.addView(intro);
        TextView downloadInfo = text("Progres tampil di halaman ini dan di notifikasi Android. Jika sistem menjeda unduhan, Android akan melanjutkannya otomatis saat jaringan tersedia.", 13, MUTED, false);
        downloadInfo.setPadding(0, 0, 0, dp(14));
        list.addView(downloadInfo);

        ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
        ((ActivityManager) getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(memory);
        long ramGb = Math.max(1, Math.round(memory.totalMem / 1073741824.0));
        long freeGb = getFreeBytes() / 1073741824L;
        TextView device = text("Perangkat ini: sekitar " + ramGb + " GB RAM • " + freeGb + " GB penyimpanan kosong", 13, ACCENT, true);
        device.setPadding(0, 0, 0, dp(18));
        list.addView(device);
        setContentView(scroll);
    }

    private void loadCatalog() {
        try {
            StringBuilder out = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(getAssets().open("model_catalog.json"), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) out.append(line);
            }
            JSONArray array = new JSONObject(out.toString()).getJSONArray("models");
            for (int i = 0; i < array.length(); i++) {
                JSONObject model = array.getJSONObject(i);
                models.put(model.getString("id"), model);
                addModelCard(model);
            }
        } catch (Exception e) {
            list.addView(text("Katalog model gagal dimuat.", 15, Color.rgb(255, 150, 150), true));
        }
    }

    private void addModelCard(JSONObject model) throws Exception {
        String id = model.getString("id");
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(15), dp(16), dp(15));
        card.setBackgroundColor(CARD);
        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cardParams.setMargins(0, 0, 0, dp(13));
        list.addView(card, cardParams);

        card.addView(text(model.getString("name"), 18, TEXT, true));
        TextView subtitle = text(model.getString("subtitle"), 13, model.optBoolean("supportsImage") ? ACCENT : MUTED, true);
        subtitle.setPadding(0, dp(4), 0, dp(8));
        card.addView(subtitle);
        card.addView(text(model.getString("description"), 14, MUTED, false));

        String specs = String.format(Locale.US, "Ukuran ±%.1f GB • RAM minimum %d GB • disarankan %d GB\nPerangkat: %s",
            model.getLong("sizeBytes") / 1_000_000_000.0,
            model.getInt("minimumRamGb"),
            model.getInt("recommendedRamGb"),
            model.getString("recommendedDevice"));
        TextView specView = text(specs, 12, Color.rgb(133, 158, 181), false);
        specView.setPadding(0, dp(9), 0, dp(9));
        card.addView(specView);

        ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);
        card.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(7)));
        progressBars.put(id, progress);

        TextView status = text(statusFor(model), 12, MUTED, false);
        status.setPadding(0, dp(7), 0, dp(8));
        card.addView(status);
        statusViews.put(id, status);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.END);
        card.addView(actions);

        Button primary = button(primaryLabel(model));
        primary.setOnClickListener(v -> onPrimary(model));
        actions.addView(primary);

        if (modelFile(id).exists()) {
            Button delete = button("Hapus");
            delete.setOnClickListener(v -> confirmDelete(model));
            actions.addView(delete);
        }
    }

    private String statusFor(JSONObject model) {
        String id = model.optString("id");
        if (id.equals(activeModel()) && modelFile(id).exists()) return "Aktif dan siap dipakai";
        if (modelFile(id).exists()) return "Terpasang";
        if (model.optString("downloadUrl").isEmpty()) return "Paket model belum tersedia";
        return "Belum diunduh";
    }

    private String primaryLabel(JSONObject model) {
        String id = model.optString("id");
        if (modelFile(id).exists()) return id.equals(activeModel()) ? "Sedang digunakan" : "Gunakan";
        return model.optString("downloadUrl").isEmpty() ? "Belum tersedia" : "Unduh";
    }

    private void onPrimary(JSONObject model) {
        String id = model.optString("id");
        if (modelFile(id).exists()) {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(ACTIVE_MODEL, id).apply();
            recreate();
            return;
        }
        if (model.optString("downloadUrl").isEmpty()) {
            Toast.makeText(this, "Paket model belum tersedia.", Toast.LENGTH_LONG).show();
            return;
        }
        startDownload(model);
    }

    private void startDownload(JSONObject model) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            pendingDownloadModel = model;
            if (shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)) {
                new AlertDialog.Builder(this)
                    .setTitle("Izinkan notifikasi unduhan")
                    .setMessage("Notifikasi diperlukan agar progres model tetap dapat dipantau setelah kamu keluar dari aplikasi.")
                    .setPositiveButton("Izinkan", (d, w) -> notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS))
                    .setNegativeButton("Lanjut tanpa notifikasi", (d, w) -> {
                        JSONObject pending = pendingDownloadModel;
                        pendingDownloadModel = null;
                        if (pending != null) startDownloadInternal(pending);
                    })
                    .show();
            } else {
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
            }
            return;
        }
        startDownloadInternal(model);
    }

    private void startDownloadInternal(JSONObject model) {
        try {
            String id = model.getString("id");
            long size = model.getLong("sizeBytes");
            long required = size + Math.max(700_000_000L, size / 4);
            if (getFreeBytes() < required) {
                new AlertDialog.Builder(this)
                    .setTitle("Penyimpanan tidak cukup")
                    .setMessage("Kosongkan setidaknya " + formatGb(required) + " sebelum mengunduh model ini.")
                    .setPositiveButton("Mengerti", null).show();
                return;
            }
            File target = modelFile(id);
            if (target.exists()) target.delete();
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(model.getString("downloadUrl")));
            request.setTitle("Mengunduh " + model.getString("name"));
            request.setDescription("Model AI Furina • unduhan latar belakang");
            request.setAllowedOverRoaming(false);
            request.setAllowedOverMetered(true);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, "models/" + id + ".gguf");
            long downloadId = ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request);
            downloadIds.put(id, downloadId);
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putLong("download_" + id, downloadId).apply();
            ProgressBar bar = progressBars.get(id);
            if (bar != null) bar.setVisibility(View.VISIBLE);
            setStatus(id, "Mengunduh di latar belakang…");
        } catch (Exception e) {
            Toast.makeText(this, "Unduhan gagal dimulai.", Toast.LENGTH_LONG).show();
        }
    }

    private void finishDownload(String id, long downloadId) {
        DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        try (Cursor cursor = manager.query(new DownloadManager.Query().setFilterById(downloadId))) {
            if (cursor == null || !cursor.moveToFirst()) return;
            int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            if (status != DownloadManager.STATUS_SUCCESSFUL) {
                setStatus(id, "Unduhan gagal. Coba lagi.");
                return;
            }
        }
        JSONObject model = models.get(id);
        if (model == null) return;
        String expected = model.optString("sha256");
        if (expected.isEmpty()) {
            setStatus(id, "Terunduh");
            recreate();
            return;
        }
        setStatus(id, "Memverifikasi file…");
        executor.execute(() -> {
            boolean valid = expected.equalsIgnoreCase(sha256(modelFile(id)));
            runOnUiThread(() -> {
                if (!valid) {
                    modelFile(id).delete();
                    setStatus(id, "Verifikasi gagal; file telah dihapus");
                } else {
                    Toast.makeText(this, "Model berhasil dipasang.", Toast.LENGTH_LONG).show();
                    recreate();
                }
            });
        });
    }

    private void confirmDelete(JSONObject model) {
        new AlertDialog.Builder(this)
            .setTitle("Hapus " + model.optString("name") + "?")
            .setMessage("Percakapan dan memori Furina tidak akan ikut terhapus.")
            .setPositiveButton("Hapus", (d, w) -> {
                String id = model.optString("id");
                modelFile(id).delete();
                if (id.equals(activeModel())) getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(ACTIVE_MODEL).apply();
                recreate();
            })
            .setNegativeButton("Batal", null)
            .show();
    }

    private final Runnable progressPoller = new Runnable() {
        @Override public void run() {
            restoreDownloads();
            DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            for (Map.Entry<String, Long> entry : downloadIds.entrySet()) {
                try (Cursor c = manager.query(new DownloadManager.Query().setFilterById(entry.getValue()))) {
                    if (c != null && c.moveToFirst()) {
                        int status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                        long done = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                        long total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                        ProgressBar bar = progressBars.get(entry.getKey());
                        if (bar != null && (status == DownloadManager.STATUS_RUNNING || status == DownloadManager.STATUS_PENDING || status == DownloadManager.STATUS_PAUSED)) {
                            bar.setVisibility(View.VISIBLE);
                            if (total > 0) bar.setProgress((int) Math.min(100, done * 100 / total));
                            String amount = total > 0 ? formatMb(done) + " / " + formatMb(total) + " (" + (done * 100 / total) + "%)" : formatMb(done);
                            setStatus(entry.getKey(), status == DownloadManager.STATUS_PAUSED ? "Unduhan dijeda sistem • " + amount : "Mengunduh • " + amount);
                        }
                    }
                } catch (Exception ignored) {}
            }
            handler.postDelayed(this, 1500);
        }
    };

    private void restoreDownloads() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        for (String id : models.keySet()) {
            long value = prefs.getLong("download_" + id, -1L);
            if (value > 0 && !downloadIds.containsKey(id)) downloadIds.put(id, value);
        }
    }

    private void setStatus(String id, String value) {
        TextView view = statusViews.get(id);
        if (view != null) view.setText(value);
    }

    private String activeModel() {
        return getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, "");
    }

    private File modelFile(String id) {
        File base = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models");
        if (!base.exists()) base.mkdirs();
        return new File(base, id + ".gguf");
    }

    private long getFreeBytes() {
        File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) dir = getFilesDir();
        StatFs stat = new StatFs(dir.getAbsolutePath());
        return stat.getAvailableBytes();
    }

    private static String sha256(File file) {
        try (FileInputStream input = new FileInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = input.read(buffer)) > 0) digest.update(buffer, 0, read);
            StringBuilder out = new StringBuilder();
            for (byte b : digest.digest()) out.append(String.format(Locale.US, "%02x", b));
            return out.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(view.getTypeface(), android.graphics.Typeface.BOLD);
        view.setLineSpacing(0, 1.15f);
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setMinHeight(dp(44));
        return button;
    }

    private String formatGb(long bytes) {
        return String.format(Locale.US, "%.1f GB", bytes / 1_000_000_000.0);
    }

    private String formatMb(long bytes) {
        return String.format(Locale.US, "%.1f MB", bytes / 1_000_000.0);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void registerReceiverSafely() {
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED);
        else registerReceiver(receiver, filter);
        receiverRegistered = true;
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        executor.shutdownNow();
        if (receiverRegistered) {
            try { unregisterReceiver(receiver); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }
}
