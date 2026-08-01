package com.wynndev.furina;

import android.Manifest;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
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
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public class ModelManagerActivity extends AppCompatActivity {
    private static final int BG = Color.rgb(8, 17, 31);
    private static final int CARD = Color.rgb(17, 31, 49);
    private static final int TEXT = Color.rgb(238, 246, 255);
    private static final int MUTED = Color.rgb(163, 184, 204);
    private static final int ACCENT = Color.rgb(138, 216, 255);
    private static final int ERROR = Color.rgb(255, 155, 155);
    private static final String PREFS = "furina_model_manager";
    private static final String ACTIVE_MODEL = "active_model";
    private static final String MODE_PREFS = "furina_ai_mode";
    private static final String ACTIVE_MODE = "active_mode";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, JSONObject> models = new HashMap<>();
    private final Map<String, ProgressBar> progressBars = new HashMap<>();
    private final Map<String, TextView> statusViews = new HashMap<>();
    private final Map<String, Button> primaryButtons = new HashMap<>();
    private final Map<String, Button> visionButtons = new HashMap<>();
    private final Map<String, Button> cancelButtons = new HashMap<>();
    private final Map<String, Button> deleteButtons = new HashMap<>();

    private LinearLayout list;
    private JSONObject pendingModel;
    private boolean pendingVision;

    private final ActivityResultLauncher<String> notificationPermission = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(), granted -> {
            if (pendingModel != null) {
                JSONObject model = pendingModel;
                boolean vision = pendingVision;
                pendingModel = null;
                pendingVision = false;
                startForegroundDownload(model, vision);
                if (!granted) {
                    Toast.makeText(
                        this,
                        "Unduhan tetap berjalan, tetapi progres mungkin tidak terlihat di notifikasi.",
                        Toast.LENGTH_LONG
                    ).show();
                }
            }
        }
    );

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
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
        list.setPadding(dp(18), dp(20), dp(18), dp(36));
        scroll.addView(
            list,
            new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        );

        list.addView(text("Model AI Furina", 25, TEXT, true));
        TextView intro = text(
            "Model tersimpan di perangkat. Kamu dapat mengganti atau melepas model aktif tanpa menghapus file. " +
                "Qwen3.5 membutuhkan paket vision tambahan agar dapat membaca gambar.",
            14,
            MUTED,
            false
        );
        intro.setPadding(0, dp(7), 0, dp(14));
        list.addView(intro);

        ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
        ((ActivityManager) getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(memory);
        long ramGb = Math.max(1, Math.round(memory.totalMem / 1073741824.0));
        long freeGb = getFreeBytes() / 1073741824L;
        TextView device = text(
            "Perangkat ini: sekitar " + ramGb + " GB RAM • " + freeGb + " GB penyimpanan kosong",
            13,
            ACCENT,
            true
        );
        device.setPadding(0, 0, 0, dp(18));
        list.addView(device);
        setContentView(scroll);
    }

    private void loadCatalog() {
        try {
            StringBuilder out = new StringBuilder();
            try (
                BufferedReader reader = new BufferedReader(
                    new InputStreamReader(getAssets().open("model_catalog.json"), StandardCharsets.UTF_8)
                )
            ) {
                String line;
                while ((line = reader.readLine()) != null) out.append(line);
            }

            JSONArray array = new JSONObject(out.toString()).getJSONArray("models");
            for (int i = 0; i < array.length(); i++) {
                JSONObject model = array.getJSONObject(i);
                models.put(model.getString("id"), model);
                addModelCard(model);
            }
        } catch (Exception error) {
            list.addView(text("Katalog model gagal dimuat: " + error.getMessage(), 14, ERROR, true));
        }
    }

    private void addModelCard(JSONObject model) throws Exception {
        String id = model.getString("id");

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(15), dp(16), dp(15));
        card.setBackgroundColor(CARD);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 0, 0, dp(13));
        list.addView(card, params);

        card.addView(text(model.getString("name"), 18, TEXT, true));
        TextView subtitle = text(
            model.getString("subtitle"),
            13,
            model.optBoolean("supportsImage") ? ACCENT : MUTED,
            true
        );
        subtitle.setPadding(0, dp(4), 0, dp(8));
        card.addView(subtitle);
        card.addView(text(model.getString("description"), 14, MUTED, false));

        long mainSize = model.optLong("sizeBytes", 0L);
        long projectorSize = model.optLong("projectorSizeBytes", 0L);
        String totalSize = projectorSize > 0L
            ? String.format(Locale.US, "±%.1f GB + vision %.0f MB", mainSize / 1_000_000_000.0, projectorSize / 1_000_000.0)
            : String.format(Locale.US, "±%.1f GB", mainSize / 1_000_000_000.0);
        String specs = totalSize +
            " • RAM minimum " + model.optInt("minimumRamGb", 8) + " GB" +
            " • disarankan " + model.optInt("recommendedRamGb", 12) + " GB\nPerangkat: " +
            model.optString("recommendedDevice", "Android arm64 kelas menengah atas");
        TextView specView = text(specs, 12, Color.rgb(133, 158, 181), false);
        specView.setPadding(0, dp(9), 0, dp(9));
        card.addView(specView);

        ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);
        card.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(7)));
        progressBars.put(id, progress);

        TextView status = text("Memeriksa model…", 12, MUTED, false);
        status.setPadding(0, dp(7), 0, dp(8));
        card.addView(status);
        statusViews.put(id, status);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        actions.setOrientation(LinearLayout.HORIZONTAL);

        Button vision = button("Unduh fitur gambar");
        vision.setVisibility(View.GONE);
        vision.setOnClickListener(v -> requestDownload(model, true));
        actions.addView(vision);
        visionButtons.put(id, vision);

        Button primary = button("Unduh");
        primary.setOnClickListener(v -> onPrimary(model));
        actions.addView(primary);
        primaryButtons.put(id, primary);

        Button cancel = button("Batalkan");
        cancel.setVisibility(View.GONE);
        cancel.setOnClickListener(v -> cancelDownload(id));
        actions.addView(cancel);
        cancelButtons.put(id, cancel);

        Button delete = button("Hapus");
        delete.setVisibility(View.GONE);
        delete.setOnClickListener(v -> confirmDelete(model));
        actions.addView(delete);
        deleteButtons.put(id, delete);

        card.addView(actions);
        refreshOne(id);
    }

    private void onPrimary(JSONObject model) {
        String id = model.optString("id");
        if (modelFile(id).isFile()) {
            SharedPreferences modelPrefs = getSharedPreferences(PREFS, MODE_PRIVATE);
            String active = modelPrefs.getString(ACTIVE_MODEL, "");
            if (id.equals(active)) {
                modelPrefs.edit().remove(ACTIVE_MODEL).apply();
                getSharedPreferences(MODE_PREFS, MODE_PRIVATE)
                    .edit()
                    .putString(ACTIVE_MODE, "online")
                    .apply();
                Toast.makeText(this, "Model dilepas. Furina kembali memakai mode online saat dipilih.", Toast.LENGTH_SHORT).show();
            } else {
                modelPrefs.edit().putString(ACTIVE_MODEL, id).apply();
                getSharedPreferences(MODE_PREFS, MODE_PRIVATE)
                    .edit()
                    .putString(ACTIVE_MODE, "offline")
                    .apply();
                Toast.makeText(this, model.optString("name") + " sekarang aktif.", Toast.LENGTH_SHORT).show();
            }
            refreshAll();
            return;
        }
        requestDownload(model, false);
    }

    private void requestDownload(JSONObject model, boolean vision) {
        String id = model.optString("id");
        String key = downloadKey(id, vision);
        String state = downloadPrefs().getString(key + "_state", "");
        if ("running".equals(state) || "verifying".equals(state)) return;

        long expectedSize = vision
            ? model.optLong("projectorSizeBytes", 0L)
            : model.optLong("sizeBytes", 0L);
        if (expectedSize <= 0L) {
            Toast.makeText(this, "Paket ini belum tersedia untuk diunduh.", Toast.LENGTH_LONG).show();
            return;
        }
        if (getFreeBytes() < expectedSize + 700_000_000L) {
            new AlertDialog.Builder(this)
                .setTitle("Penyimpanan tidak cukup")
                .setMessage("Kosongkan setidaknya " + formatGb(expectedSize + 700_000_000L) + " sebelum mengunduh paket ini.")
                .setPositiveButton("Mengerti", null)
                .show();
            return;
        }

        if (
            Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            pendingModel = model;
            pendingVision = vision;
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
        } else {
            startForegroundDownload(model, vision);
        }
    }

    private void startForegroundDownload(JSONObject model, boolean vision) {
        try {
            String id = model.getString("id");
            String url = vision ? model.optString("projectorUrl") : model.optString("downloadUrl");
            String sha = vision ? model.optString("projectorSha256") : model.optString("sha256");
            long expectedSize = vision
                ? model.optLong("projectorSizeBytes", 0L)
                : model.optLong("sizeBytes", 0L);
            String key = downloadKey(id, vision);
            String fileName = vision ? id + "-mmproj.gguf" : id + ".gguf";
            String displayName = model.getString("name") + (vision ? " • fitur gambar" : "");

            if (url.trim().isEmpty()) throw new IllegalStateException("URL paket belum tersedia.");

            Intent intent = new Intent(this, ModelDownloadService.class)
                .setAction(ModelDownloadService.ACTION_START)
                .putExtra(ModelDownloadService.EXTRA_ID, id)
                .putExtra(ModelDownloadService.EXTRA_NAME, displayName)
                .putExtra(ModelDownloadService.EXTRA_URL, url)
                .putExtra(ModelDownloadService.EXTRA_FILE_NAME, fileName)
                .putExtra(ModelDownloadService.EXTRA_PREF_KEY, key)
                .putExtra(ModelDownloadService.EXTRA_EXPECTED_SHA256, sha)
                .putExtra(ModelDownloadService.EXTRA_EXPECTED_SIZE, expectedSize);
            ContextCompat.startForegroundService(this, intent);

            downloadPrefs()
                .edit()
                .putString(key + "_state", "running")
                .putString(key + "_message", "Menghubungkan…")
                .putLong(key + "_done", 0L)
                .putLong(key + "_total", expectedSize)
                .apply();
            refreshOne(id);
        } catch (Exception error) {
            Toast.makeText(this, "Unduhan gagal dimulai: " + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void cancelDownload(String id) {
        String key = runningKey(id);
        if (key.isEmpty()) return;
        Intent intent = new Intent(this, ModelDownloadService.class)
            .setAction(ModelDownloadService.ACTION_CANCEL)
            .putExtra(ModelDownloadService.EXTRA_PREF_KEY, key);
        startService(intent);
        downloadPrefs()
            .edit()
            .putString(key + "_state", "cancelled")
            .putString(key + "_message", "Membatalkan unduhan…")
            .apply();
        refreshOne(id);
    }

    private void refreshAll() {
        for (String id : models.keySet()) refreshOne(id);
    }

    private void refreshOne(String id) {
        JSONObject model = models.get(id);
        if (model == null) return;

        boolean mainInstalled = modelFile(id).isFile() && modelFile(id).length() > 100_000_000L;
        boolean supportsImage = model.optBoolean("supportsImage", false);
        boolean visionInstalled = projectorFile(id).isFile() && projectorFile(id).length() > 100_000_000L;
        String active = getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, "");
        String runningKey = runningKey(id);

        ProgressBar bar = progressBars.get(id);
        TextView status = statusViews.get(id);
        Button primary = primaryButtons.get(id);
        Button vision = visionButtons.get(id);
        Button cancel = cancelButtons.get(id);
        Button delete = deleteButtons.get(id);

        if (!runningKey.isEmpty()) {
            SharedPreferences downloads = downloadPrefs();
            String state = downloads.getString(runningKey + "_state", "running");
            long done = downloads.getLong(runningKey + "_done", 0L);
            long total = downloads.getLong(runningKey + "_total", 0L);
            String message = downloads.getString(runningKey + "_message", "Mengunduh");
            boolean isVision = runningKey.endsWith(":vision");

            if (bar != null) {
                bar.setVisibility(View.VISIBLE);
                bar.setIndeterminate(total <= 0L || "verifying".equals(state));
                if (total > 0L && !"verifying".equals(state)) {
                    bar.setProgress((int) Math.min(100L, done * 100L / total));
                }
            }
            if (status != null) {
                String progress = total > 0L
                    ? " • " + formatMb(done) + " / " + formatMb(total) + " (" + Math.min(100L, done * 100L / total) + "%)"
                    : "";
                status.setText((isVision ? "Fitur gambar: " : "Model: ") + message + progress);
                status.setTextColor(ACCENT);
            }
            if (primary != null) primary.setVisibility(View.GONE);
            if (vision != null) vision.setVisibility(View.GONE);
            if (cancel != null) cancel.setVisibility(View.VISIBLE);
            if (delete != null) delete.setVisibility(View.GONE);
            return;
        }

        if (bar != null) bar.setVisibility(View.GONE);
        if (cancel != null) cancel.setVisibility(View.GONE);
        if (primary != null) primary.setVisibility(View.VISIBLE);
        if (delete != null) delete.setVisibility(mainInstalled ? View.VISIBLE : View.GONE);

        if (mainInstalled) {
            String stateText;
            if (id.equals(active)) {
                stateText = supportsImage && visionInstalled
                    ? "Aktif • teks dan gambar siap digunakan"
                    : supportsImage
                        ? "Aktif • teks siap, paket gambar belum dipasang"
                        : "Aktif dan siap digunakan";
            } else {
                stateText = supportsImage && visionInstalled
                    ? "Terpasang • teks dan gambar tersedia"
                    : supportsImage
                        ? "Terpasang • teks tersedia, paket gambar belum dipasang"
                        : "Terpasang, tidak aktif";
            }
            if (status != null) {
                status.setText(stateText);
                status.setTextColor(id.equals(active) ? ACCENT : MUTED);
            }
            if (primary != null) primary.setText(id.equals(active) ? "Lepas" : "Gunakan");
            if (vision != null) {
                vision.setVisibility(supportsImage && !visionInstalled ? View.VISIBLE : View.GONE);
                vision.setText("Unduh fitur gambar");
            }
        } else {
            String key = downloadKey(id, false);
            String state = downloadPrefs().getString(key + "_state", "");
            String message = downloadPrefs().getString(key + "_message", "");
            if (status != null) {
                if ("error".equals(state)) {
                    status.setText("Gagal: " + message);
                    status.setTextColor(ERROR);
                } else if ("cancelled".equals(state)) {
                    status.setText("Unduhan dibatalkan; tekan Unduh untuk melanjutkan.");
                    status.setTextColor(MUTED);
                } else {
                    status.setText("Belum diunduh");
                    status.setTextColor(MUTED);
                }
            }
            if (primary != null) primary.setText("Unduh");
            if (vision != null) vision.setVisibility(View.GONE);
        }
    }

    private String runningKey(String id) {
        SharedPreferences downloads = downloadPrefs();
        String main = downloadKey(id, false);
        String vision = downloadKey(id, true);
        String mainState = downloads.getString(main + "_state", "");
        if ("running".equals(mainState) || "verifying".equals(mainState)) return main;
        String visionState = downloads.getString(vision + "_state", "");
        if ("running".equals(visionState) || "verifying".equals(visionState)) return vision;
        return "";
    }

    private final Runnable progressPoller = new Runnable() {
        @Override public void run() {
            refreshAll();
            handler.postDelayed(this, 850L);
        }
    };

    private void confirmDelete(JSONObject model) {
        new AlertDialog.Builder(this)
            .setTitle("Hapus " + model.optString("name") + "?")
            .setMessage("File model dan paket gambarnya akan dihapus. Percakapan, memori, dan pengaturan Furina tidak ikut terhapus.")
            .setPositiveButton("Hapus", (dialog, which) -> {
                String id = model.optString("id");
                modelFile(id).delete();
                projectorFile(id).delete();
                new File(modelFile(id).getAbsolutePath() + ".part").delete();
                new File(projectorFile(id).getAbsolutePath() + ".part").delete();
                if (id.equals(getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, ""))) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(ACTIVE_MODEL).apply();
                    getSharedPreferences(MODE_PREFS, MODE_PRIVATE)
                        .edit()
                        .putString(ACTIVE_MODE, "online")
                        .apply();
                }
                refreshAll();
            })
            .setNegativeButton("Batal", null)
            .show();
    }

    private String downloadKey(String id, boolean vision) {
        return vision ? id + ":vision" : id;
    }

    private SharedPreferences downloadPrefs() {
        return getSharedPreferences(ModelDownloadService.PREFS, MODE_PRIVATE);
    }

    private File modelDirectory() {
        File base = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models");
        if (!base.exists()) base.mkdirs();
        return base;
    }

    private File modelFile(String id) {
        return new File(modelDirectory(), id + ".gguf");
    }

    private File projectorFile(String id) {
        return new File(modelDirectory(), id + "-mmproj.gguf");
    }

    private long getFreeBytes() {
        File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) dir = getFilesDir();
        return new StatFs(dir.getAbsolutePath()).getAvailableBytes();
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

    private String formatMb(long bytes) {
        return String.format(Locale.US, "%.1f MB", bytes / 1_000_000.0);
    }

    private String formatGb(long bytes) {
        return String.format(Locale.US, "%.1f GB", bytes / 1_000_000_000.0);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
