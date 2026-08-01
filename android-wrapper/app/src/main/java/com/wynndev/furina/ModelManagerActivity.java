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
    private static final String PREFS = "furina_model_manager";
    private static final String ACTIVE_MODEL = "active_model";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, JSONObject> models = new HashMap<>();
    private final Map<String, ProgressBar> progressBars = new HashMap<>();
    private final Map<String, TextView> statusViews = new HashMap<>();
    private final Map<String, Button> primaryButtons = new HashMap<>();
    private final Map<String, Button> cancelButtons = new HashMap<>();
    private LinearLayout list;
    private JSONObject pendingModel;

    private final ActivityResultLauncher<String> notificationPermission = registerForActivityResult(
        new ActivityResultContracts.RequestPermission(), granted -> {
            if (pendingModel != null) {
                JSONObject model = pendingModel;
                pendingModel = null;
                startForegroundDownload(model);
                if (!granted) Toast.makeText(this, "Unduhan tetap berjalan, tetapi progres mungkin tidak terlihat di notifikasi.", Toast.LENGTH_LONG).show();
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
        list.setPadding(dp(18), dp(20), dp(18), dp(32));
        scroll.addView(list, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        list.addView(text("Model AI Furina", 25, TEXT, true));
        TextView intro = text("Unduh, pilih, dan hapus model offline. Unduhan memakai layanan foreground Furina agar tetap berjalan saat aplikasi ditutup, termasuk ketika DownloadManager Android salah menganggap Wi-Fi tidak tersedia.", 14, MUTED, false);
        intro.setPadding(0, dp(7), 0, dp(14));
        list.addView(intro);
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
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, dp(13));
        list.addView(card, params);
        card.addView(text(model.getString("name"), 18, TEXT, true));
        TextView subtitle = text(model.getString("subtitle"), 13, model.optBoolean("supportsImage") ? ACCENT : MUTED, true);
        subtitle.setPadding(0, dp(4), 0, dp(8));
        card.addView(subtitle);
        card.addView(text(model.getString("description"), 14, MUTED, false));
        String specs = String.format(Locale.US, "Ukuran ±%.1f GB • RAM minimum %d GB • disarankan %d GB\nPerangkat: %s",
            model.getLong("sizeBytes") / 1_000_000_000.0,
            model.getInt("minimumRamGb"), model.getInt("recommendedRamGb"), model.getString("recommendedDevice"));
        TextView specView = text(specs, 12, Color.rgb(133, 158, 181), false);
        specView.setPadding(0, dp(9), 0, dp(9));
        card.addView(specView);
        ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);
        card.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(7)));
        progressBars.put(id, progress);
        TextView status = text("Belum diunduh", 12, MUTED, false);
        status.setPadding(0, dp(7), 0, dp(8));
        card.addView(status);
        statusViews.put(id, status);
        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        Button primary = button("Unduh");
        primary.setOnClickListener(v -> onPrimary(model));
        actions.addView(primary);
        primaryButtons.put(id, primary);
        Button cancel = button("Batalkan");
        cancel.setVisibility(View.GONE);
        cancel.setOnClickListener(v -> cancelDownload(id));
        actions.addView(cancel);
        cancelButtons.put(id, cancel);
        if (modelFile(id).exists()) {
            Button delete = button("Hapus");
            delete.setOnClickListener(v -> confirmDelete(model));
            actions.addView(delete);
        }
        card.addView(actions);
        refreshOne(id);
    }

    private void onPrimary(JSONObject model) {
        String id = model.optString("id");
        if (modelFile(id).exists()) {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(ACTIVE_MODEL, id).apply();
            recreate();
            return;
        }
        if ("running".equals(downloadPrefs().getString(id + "_state", ""))) return;
        if (getFreeBytes() < model.optLong("sizeBytes") + 700_000_000L) {
            new AlertDialog.Builder(this).setTitle("Penyimpanan tidak cukup").setMessage("Kosongkan ruang tambahan sebelum mengunduh model ini.").setPositiveButton("Mengerti", null).show();
            return;
        }
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            pendingModel = model;
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
        } else {
            startForegroundDownload(model);
        }
    }

    private void startForegroundDownload(JSONObject model) {
        try {
            String id = model.getString("id");
            String url = model.getString("downloadUrl");
            if (url.isEmpty()) throw new IllegalStateException("URL model belum tersedia");
            Intent intent = new Intent(this, ModelDownloadService.class)
                .setAction(ModelDownloadService.ACTION_START)
                .putExtra(ModelDownloadService.EXTRA_ID, id)
                .putExtra(ModelDownloadService.EXTRA_NAME, model.getString("name"))
                .putExtra(ModelDownloadService.EXTRA_URL, url);
            ContextCompat.startForegroundService(this, intent);
            downloadPrefs().edit().putString(id + "_state", "running").putString(id + "_message", "Menghubungkan…").apply();
            refreshOne(id);
        } catch (Exception e) {
            Toast.makeText(this, "Unduhan gagal dimulai: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void cancelDownload(String id) {
        Intent intent = new Intent(this, ModelDownloadService.class).setAction(ModelDownloadService.ACTION_CANCEL).putExtra(ModelDownloadService.EXTRA_ID, id);
        startService(intent);
        downloadPrefs().edit().putString(id + "_state", "cancelled").putString(id + "_message", "Unduhan dibatalkan").apply();
        refreshOne(id);
    }

    private void refreshOne(String id) {
        File file = modelFile(id);
        String active = getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, "");
        SharedPreferences d = downloadPrefs();
        String state = d.getString(id + "_state", "");
        long done = d.getLong(id + "_done", 0);
        long total = d.getLong(id + "_total", 0);
        String message = d.getString(id + "_message", "");
        ProgressBar bar = progressBars.get(id);
        TextView status = statusViews.get(id);
        Button primary = primaryButtons.get(id);
        Button cancel = cancelButtons.get(id);
        if (file.exists()) {
            if (bar != null) bar.setVisibility(View.GONE);
            if (status != null) status.setText(id.equals(active) ? "Aktif dan siap dipakai" : "Terpasang");
            if (primary != null) primary.setText(id.equals(active) ? "Sedang digunakan" : "Gunakan");
            if (cancel != null) cancel.setVisibility(View.GONE);
            return;
        }
        if ("running".equals(state)) {
            if (bar != null) {
                bar.setVisibility(View.VISIBLE);
                bar.setIndeterminate(total <= 0);
                if (total > 0) bar.setProgress((int) Math.min(100, done * 100 / total));
            }
            if (status != null) status.setText(message + (total > 0 ? " • " + formatMb(done) + " / " + formatMb(total) + " (" + (done * 100 / total) + "%)" : ""));
            if (primary != null) primary.setText("Mengunduh…");
            if (cancel != null) cancel.setVisibility(View.VISIBLE);
        } else {
            if (bar != null) bar.setVisibility(View.GONE);
            if (status != null) status.setText("error".equals(state) ? "Gagal: " + message : "cancelled".equals(state) ? "Unduhan dibatalkan; tekan Unduh untuk melanjutkan" : "Belum diunduh");
            if (primary != null) primary.setText("Unduh");
            if (cancel != null) cancel.setVisibility(View.GONE);
        }
    }

    private final Runnable progressPoller = new Runnable() {
        @Override public void run() {
            for (String id : models.keySet()) refreshOne(id);
            handler.postDelayed(this, 1000);
        }
    };

    private void confirmDelete(JSONObject model) {
        new AlertDialog.Builder(this).setTitle("Hapus " + model.optString("name") + "?")
            .setMessage("Percakapan dan memori Furina tidak akan ikut terhapus.")
            .setPositiveButton("Hapus", (d, w) -> {
                String id = model.optString("id");
                modelFile(id).delete();
                new File(modelFile(id).getAbsolutePath() + ".part").delete();
                if (id.equals(getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, ""))) getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(ACTIVE_MODEL).apply();
                recreate();
            }).setNegativeButton("Batal", null).show();
    }

    private SharedPreferences downloadPrefs() { return getSharedPreferences(ModelDownloadService.PREFS, MODE_PRIVATE); }
    private File modelFile(String id) {
        File base = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models");
        if (!base.exists()) base.mkdirs();
        return new File(base, id + ".gguf");
    }
    private long getFreeBytes() {
        File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) dir = getFilesDir();
        return new StatFs(dir.getAbsolutePath()).getAvailableBytes();
    }
    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(sp); view.setTextColor(color);
        if (bold) view.setTypeface(view.getTypeface(), android.graphics.Typeface.BOLD);
        view.setLineSpacing(0, 1.15f); return view;
    }
    private Button button(String label) { Button b = new Button(this); b.setText(label); b.setAllCaps(false); b.setMinHeight(dp(44)); return b; }
    private String formatMb(long bytes) { return String.format(Locale.US, "%.1f MB", bytes / 1_000_000.0); }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); super.onDestroy(); }
}
