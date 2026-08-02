package com.wynndev.furina;

import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.StatFs;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Offline model manager. Models are imported from local storage; no download client exists. */
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
    private static final long MIN_MODEL_BYTES = 100_000_000L;

    private final Map<String, JSONObject> models = new HashMap<>();
    private final Map<String, TextView> statusViews = new HashMap<>();
    private final Map<String, Button> activateButtons = new HashMap<>();
    private final Map<String, Button> importButtons = new HashMap<>();
    private final Map<String, Button> visionButtons = new HashMap<>();
    private final Map<String, Button> deleteButtons = new HashMap<>();

    private LinearLayout list;
    private String pendingModelId = "";
    private boolean pendingVision;
    private boolean importing;

    private final ActivityResultLauncher<String[]> modelPicker = registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),
        uri -> {
            if (uri == null || pendingModelId.isEmpty()) {
                pendingModelId = "";
                pendingVision = false;
                return;
            }
            importSelectedFile(uri, pendingModelId, pendingVision);
        }
    );

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildUi();
        loadCatalog();
    }

    @Override protected void onResume() {
        super.onResume();
        refreshAll();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(dp(18), dp(20), dp(18), dp(36));
        scroll.addView(list, new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        list.addView(text("Model Lokal Furina", 25, TEXT, true));
        TextView intro = text(
            "Furina tidak mengunduh model dari internet. Siapkan file GGUF secara terpisah, lalu impor dari penyimpanan perangkat. File disalin ke ruang privat aplikasi dan tetap tersimpan setelah pembaruan APK.",
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
            "Perangkat: sekitar " + ramGb + " GB RAM • " + freeGb + " GB penyimpanan kosong",
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
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                getAssets().open("model_catalog.json"), StandardCharsets.UTF_8
            ))) {
                String line;
                while ((line = reader.readLine()) != null) out.append(line);
            }
            JSONArray array = new JSONObject(out.toString()).getJSONArray("models");
            for (int index = 0; index < array.length(); index++) {
                JSONObject model = array.getJSONObject(index);
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
        TextView subtitle = text(model.getString("subtitle"), 13, model.optBoolean("supportsImage") ? ACCENT : MUTED, true);
        subtitle.setPadding(0, dp(4), 0, dp(8));
        card.addView(subtitle);
        card.addView(text(model.getString("description"), 14, MUTED, false));

        long mainSize = model.optLong("sizeBytes", 0L);
        long projectorSize = model.optLong("projectorSizeBytes", 0L);
        String totalSize = projectorSize > 0L
            ? String.format(Locale.US, "±%.1f GB + projector %.0f MB", mainSize / 1_000_000_000.0, projectorSize / 1_000_000.0)
            : String.format(Locale.US, "±%.1f GB", mainSize / 1_000_000_000.0);
        TextView specs = text(
            totalSize + " • RAM minimum " + model.optInt("minimumRamGb", 8) + " GB\n" +
                model.optString("recommendedDevice", "Android arm64 kelas menengah atas"),
            12,
            Color.rgb(133, 158, 181),
            false
        );
        specs.setPadding(0, dp(9), 0, dp(9));
        card.addView(specs);

        TextView status = text("Memeriksa file lokal…", 12, MUTED, false);
        status.setPadding(0, dp(7), 0, dp(8));
        card.addView(status);
        statusViews.put(id, status);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        actions.setOrientation(LinearLayout.HORIZONTAL);

        Button importModel = button("Impor GGUF");
        importModel.setOnClickListener(view -> pickModel(id, false));
        actions.addView(importModel);
        importButtons.put(id, importModel);

        Button importVision = button("Impor projector");
        importVision.setVisibility(model.optBoolean("supportsImage") ? View.VISIBLE : View.GONE);
        importVision.setOnClickListener(view -> pickModel(id, true));
        actions.addView(importVision);
        visionButtons.put(id, importVision);

        Button activate = button("Gunakan");
        activate.setOnClickListener(view -> toggleActive(id));
        actions.addView(activate);
        activateButtons.put(id, activate);

        Button delete = button("Hapus");
        delete.setOnClickListener(view -> confirmDelete(id));
        actions.addView(delete);
        deleteButtons.put(id, delete);

        card.addView(actions);
        refreshOne(id);
    }

    private void pickModel(String id, boolean vision) {
        if (importing) {
            Toast.makeText(this, "Tunggu proses impor selesai.", Toast.LENGTH_SHORT).show();
            return;
        }
        pendingModelId = id;
        pendingVision = vision;
        modelPicker.launch(new String[]{"application/octet-stream", "application/x-gguf", "*/*"});
    }

    private void importSelectedFile(Uri uri, String id, boolean vision) {
        importing = true;
        setButtonsEnabled(false);
        TextView status = statusViews.get(id);
        if (status != null) {
            status.setText(vision ? "Menyalin projector dari penyimpanan…" : "Menyalin model dari penyimpanan…");
            status.setTextColor(ACCENT);
        }

        new Thread(() -> {
            File target = vision ? projectorFile(id) : modelFile(id);
            File temporary = new File(target.getAbsolutePath() + ".importing");
            String error = null;
            try {
                if (!target.getParentFile().exists() && !target.getParentFile().mkdirs()) {
                    throw new IllegalStateException("Folder model tidak dapat dibuat.");
                }
                long copied = 0L;
                try (InputStream input = getContentResolver().openInputStream(uri);
                     FileOutputStream output = new FileOutputStream(temporary, false)) {
                    if (input == null) throw new IllegalStateException("File tidak dapat dibuka.");
                    byte[] buffer = new byte[1024 * 1024];
                    int read;
                    while ((read = input.read(buffer)) >= 0) {
                        output.write(buffer, 0, read);
                        copied += read;
                    }
                    output.flush();
                }
                if (copied < MIN_MODEL_BYTES) throw new IllegalStateException("File terlalu kecil untuk menjadi model GGUF yang valid.");
                if (target.exists() && !target.delete()) throw new IllegalStateException("Model lama tidak dapat diganti.");
                if (!temporary.renameTo(target)) throw new IllegalStateException("File impor tidak dapat dipindahkan.");
                if (!vision) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(ACTIVE_MODEL, id).apply();
                    getSharedPreferences(MODE_PREFS, MODE_PRIVATE).edit().putString(ACTIVE_MODE, "offline").apply();
                }
            } catch (Exception exception) {
                error = exception.getMessage();
                temporary.delete();
            }
            String finalError = error;
            runOnUiThread(() -> {
                importing = false;
                pendingModelId = "";
                pendingVision = false;
                setButtonsEnabled(true);
                refreshAll();
                Toast.makeText(
                    this,
                    finalError == null ? (vision ? "Projector berhasil diimpor." : "Model berhasil diimpor dan diaktifkan.") : "Impor gagal: " + finalError,
                    Toast.LENGTH_LONG
                ).show();
            });
        }, "FurinaModelImport").start();
    }

    private void toggleActive(String id) {
        File file = modelFile(id);
        if (!file.isFile() || file.length() < MIN_MODEL_BYTES) {
            Toast.makeText(this, "Impor file GGUF model terlebih dahulu.", Toast.LENGTH_LONG).show();
            return;
        }
        SharedPreferences preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        String active = preferences.getString(ACTIVE_MODEL, "");
        if (id.equals(active)) {
            preferences.edit().remove(ACTIVE_MODEL).apply();
            Toast.makeText(this, "Model dilepas. Furina tetap berada dalam mode offline.", Toast.LENGTH_SHORT).show();
        } else {
            preferences.edit().putString(ACTIVE_MODEL, id).apply();
            getSharedPreferences(MODE_PREFS, MODE_PRIVATE).edit().putString(ACTIVE_MODE, "offline").apply();
            Toast.makeText(this, models.get(id).optString("name") + " sekarang aktif.", Toast.LENGTH_SHORT).show();
        }
        refreshAll();
    }

    private void confirmDelete(String id) {
        JSONObject model = models.get(id);
        if (model == null) return;
        new AlertDialog.Builder(this)
            .setTitle("Hapus " + model.optString("name") + "?")
            .setMessage("File model dan projector lokal akan dihapus. Percakapan, persona, dan memori tidak ikut terhapus.")
            .setPositiveButton("Hapus", (dialog, which) -> {
                modelFile(id).delete();
                projectorFile(id).delete();
                new File(modelFile(id).getAbsolutePath() + ".importing").delete();
                new File(projectorFile(id).getAbsolutePath() + ".importing").delete();
                if (id.equals(getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, ""))) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(ACTIVE_MODEL).apply();
                }
                refreshAll();
            })
            .setNegativeButton("Batal", null)
            .show();
    }

    private void refreshAll() {
        for (String id : models.keySet()) refreshOne(id);
    }

    private void refreshOne(String id) {
        JSONObject model = models.get(id);
        if (model == null) return;
        boolean installed = modelFile(id).isFile() && modelFile(id).length() >= MIN_MODEL_BYTES;
        boolean visionInstalled = projectorFile(id).isFile() && projectorFile(id).length() >= MIN_MODEL_BYTES;
        boolean supportsImage = model.optBoolean("supportsImage", false);
        boolean active = id.equals(getSharedPreferences(PREFS, MODE_PRIVATE).getString(ACTIVE_MODEL, ""));

        TextView status = statusViews.get(id);
        if (status != null && !importing) {
            if (active) {
                status.setText(supportsImage && visionInstalled ? "Aktif • teks dan gambar lokal siap" : "Aktif • model teks lokal siap");
                status.setTextColor(ACCENT);
            } else if (installed) {
                status.setText(supportsImage && visionInstalled ? "Terpasang • projector tersedia" : "Terpasang di perangkat");
                status.setTextColor(MUTED);
            } else {
                status.setText("Belum diimpor");
                status.setTextColor(MUTED);
            }
        }

        Button activate = activateButtons.get(id);
        if (activate != null) {
            activate.setVisibility(installed ? View.VISIBLE : View.GONE);
            activate.setText(active ? "Lepas" : "Gunakan");
        }
        Button delete = deleteButtons.get(id);
        if (delete != null) delete.setVisibility(installed || visionInstalled ? View.VISIBLE : View.GONE);
        Button vision = visionButtons.get(id);
        if (vision != null && supportsImage) vision.setText(visionInstalled ? "Ganti projector" : "Impor projector");
        Button importer = importButtons.get(id);
        if (importer != null) importer.setText(installed ? "Ganti GGUF" : "Impor GGUF");
    }

    private void setButtonsEnabled(boolean enabled) {
        for (Button button : importButtons.values()) button.setEnabled(enabled);
        for (Button button : visionButtons.values()) button.setEnabled(enabled);
        for (Button button : activateButtons.values()) button.setEnabled(enabled);
        for (Button button : deleteButtons.values()) button.setEnabled(enabled);
    }

    private File modelDirectory() {
        File base = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (base == null) base = getFilesDir();
        File directory = new File(base, "models");
        if (!directory.exists()) directory.mkdirs();
        return directory;
    }

    private File modelFile(String id) {
        return new File(modelDirectory(), id + ".gguf");
    }

    private File projectorFile(String id) {
        return new File(modelDirectory(), id + "-mmproj.gguf");
    }

    private long getFreeBytes() {
        File directory = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (directory == null) directory = getFilesDir();
        return new StatFs(directory.getAbsolutePath()).getAvailableBytes();
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

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
