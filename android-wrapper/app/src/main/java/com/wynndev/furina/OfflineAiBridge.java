package com.wynndev.furina;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.util.LinkedHashSet;
import java.util.Set;

public final class OfflineAiBridge {
    private static final String MODEL_PREFS = "furina_model_manager";
    private static final String ACTIVE_MODEL = "active_model";
    private static final String MODE_PREFS = "furina_ai_mode";
    private static final String ACTIVE_MODE = "active_mode";
    private static final String MODE_ONLINE = "online";
    private static final String MODE_OFFLINE = "offline";
    private static final String SHARED_PREFS = "furina_shared_profile";
    private static final String SHARED_STATE = "state_json";
    private static final int MAX_SHARED_STATE_BYTES = 512 * 1024;
    private static final int MAX_MEMORIES = 80;

    private final Activity activity;
    private final WebView webView;
    private final OfflineModelEngine engine;

    public OfflineAiBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        this.engine = new OfflineModelEngine(activity);
    }

    @JavascriptInterface
    public String getStatus() {
        try {
            String modelId = engine.activeModelId();
            boolean installed = !modelId.isEmpty() && engine.isInstalled(modelId);
            boolean imageModelSelected = "qwen35-4b".equals(modelId);
            boolean multimodalReady = imageModelSelected && engine.isVisionReady(modelId);
            String mode = modePrefs().getString(ACTIVE_MODE, installed ? MODE_OFFLINE : MODE_ONLINE);
            if (MODE_OFFLINE.equals(mode) && !installed) mode = MODE_ONLINE;

            JSONObject result = new JSONObject();
            result.put("mode", mode);
            result.put("source", MODE_OFFLINE.equals(mode) ? "offline" : "lovable");
            result.put("activeModelId", modelId);
            result.put("installed", installed);
            result.put("busy", engine.isBusy());
            result.put("supportsImage", imageModelSelected);
            result.put("multimodalReady", multimodalReady);
            result.put("canUseOffline", installed);
            if (!imageModelSelected) {
                result.put("imageDisabledReason", "Model aktif hanya mendukung teks.");
            } else if (!multimodalReady) {
                result.put("imageDisabledReason", "Projector gambar Qwen3.5 belum selesai diunduh.");
            }
            return result.toString();
        } catch (Exception e) {
            return "{\"mode\":\"online\",\"source\":\"lovable\",\"installed\":false,\"busy\":false,\"supportsImage\":false,\"multimodalReady\":false,\"canUseOffline\":false}";
        }
    }

    @JavascriptInterface
    public String getSharedState() {
        String stored = activity.getSharedPreferences(SHARED_PREFS, Activity.MODE_PRIVATE)
            .getString(SHARED_STATE, "");
        if (stored != null && !stored.trim().isEmpty()) return stored;
        try {
            JSONObject defaults = new JSONObject();
            defaults.put("version", 1);
            defaults.put("name", "Furina");
            defaults.put("persona", "");
            defaults.put("language", "auto");
            defaults.put("memories", new JSONArray());
            return defaults.toString();
        } catch (Exception ignored) {
            return "{\"version\":1,\"name\":\"Furina\",\"persona\":\"\",\"language\":\"auto\",\"memories\":[]}";
        }
    }

    @JavascriptInterface
    public boolean saveSharedState(String stateJson) {
        try {
            if (stateJson == null || stateJson.length() > MAX_SHARED_STATE_BYTES) return false;
            JSONObject incoming = new JSONObject(stateJson);
            JSONObject clean = new JSONObject();
            clean.put("version", 1);
            clean.put("name", clip(incoming.optString("name", "Furina"), 40));
            clean.put("persona", clip(incoming.optString("persona", ""), 6000));
            String language = incoming.optString("language", "auto");
            if (!language.equals("auto") && !language.equals("id") && !language.equals("en") && !language.equals("ja")) {
                language = "auto";
            }
            clean.put("language", language);

            JSONArray memories = incoming.optJSONArray("memories");
            JSONArray cleanMemories = new JSONArray();
            Set<String> seen = new LinkedHashSet<>();
            if (memories != null) {
                for (int i = 0; i < memories.length() && cleanMemories.length() < MAX_MEMORIES; i++) {
                    String memory = clip(memories.optString(i, "").trim(), 240);
                    String key = memory.toLowerCase();
                    if (memory.length() >= 3 && seen.add(key)) cleanMemories.put(memory);
                }
            }
            clean.put("memories", cleanMemories);

            activity.getSharedPreferences(SHARED_PREFS, Activity.MODE_PRIVATE)
                .edit()
                .putString(SHARED_STATE, clean.toString())
                .apply();
            dispatchSharedStateChanged(clean);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private String clip(String value, int max) {
        String safe = value == null ? "" : value.trim();
        return safe.length() <= max ? safe : safe.substring(0, max);
    }

    @JavascriptInterface
    public boolean useOnlineAi() {
        if (engine.isBusy()) engine.cancel();
        modePrefs().edit().putString(ACTIVE_MODE, MODE_ONLINE).apply();
        dispatchModeChanged();
        return true;
    }

    @JavascriptInterface
    public boolean useOfflineAi() {
        String modelId = engine.activeModelId();
        if (modelId.isEmpty() || !engine.isInstalled(modelId)) return false;
        modePrefs().edit().putString(ACTIVE_MODE, MODE_OFFLINE).apply();
        dispatchModeChanged();
        return true;
    }

    @JavascriptInterface
    public boolean deactivateOfflineModel() {
        if (engine.isBusy()) engine.cancel();
        activity.getSharedPreferences(MODEL_PREFS, Activity.MODE_PRIVATE).edit().remove(ACTIVE_MODEL).apply();
        modePrefs().edit().putString(ACTIVE_MODE, MODE_ONLINE).apply();
        dispatchModeChanged();
        return true;
    }

    @JavascriptInterface
    public void openModelManager() {
        activity.runOnUiThread(() -> activity.startActivity(new Intent(activity, ModelManagerActivity.class)));
    }

    @JavascriptInterface
    public void cancelGeneration() {
        engine.cancel();
    }

    @JavascriptInterface
    public void generate(String requestJson) {
        if (!MODE_OFFLINE.equals(currentMode())) {
            dispatchError(requestId(requestJson), "Mode offline belum diaktifkan.");
            return;
        }
        runGeneration(requestJson, null);
    }

    @JavascriptInterface
    public void generateWithImage(String requestJson, String imageDataUrl) {
        File image = null;
        try {
            if (!MODE_OFFLINE.equals(currentMode())) {
                dispatchError(requestId(requestJson), "Mode offline belum diaktifkan.");
                return;
            }
            if (!"qwen35-4b".equals(engine.activeModelId())) {
                dispatchError(requestId(requestJson), "Pilih Qwen3.5-4B untuk membaca gambar.");
                return;
            }
            image = decodeImage(imageDataUrl);
            JSONObject request = new JSONObject(requestJson);
            request.put("imagePath", image.getAbsolutePath());
            runGeneration(request.toString(), image);
        } catch (Exception e) {
            if (image != null) image.delete();
            dispatchError(requestId(requestJson), "Gambar tidak dapat dipersiapkan untuk model offline.");
        }
    }

    private String currentMode() {
        return modePrefs().getString(ACTIVE_MODE, engine.activeModelId().isEmpty() ? MODE_ONLINE : MODE_OFFLINE);
    }

    private SharedPreferences modePrefs() {
        return activity.getSharedPreferences(MODE_PREFS, Activity.MODE_PRIVATE);
    }

    private void dispatchModeChanged() {
        activity.runOnUiThread(() -> {
            String script = "window.dispatchEvent(new CustomEvent('furina-ai-mode-changed',{detail:" + getStatus() + "}));";
            webView.evaluateJavascript(script, null);
        });
    }

    private void dispatchSharedStateChanged(JSONObject state) {
        activity.runOnUiThread(() -> {
            String script = "window.dispatchEvent(new CustomEvent('furina-shared-state-changed',{detail:" + state.toString() + "}));";
            webView.evaluateJavascript(script, null);
        });
    }

    private File decodeImage(String dataUrl) throws Exception {
        String encoded = dataUrl == null ? "" : dataUrl.trim();
        int comma = encoded.indexOf(',');
        if (comma >= 0) encoded = encoded.substring(comma + 1);
        byte[] bytes = Base64.decode(encoded, Base64.DEFAULT);
        if (bytes.length == 0 || bytes.length > 25 * 1024 * 1024) {
            throw new IllegalArgumentException("Ukuran gambar tidak valid");
        }
        File dir = new File(activity.getCacheDir(), "vision");
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Folder cache gambar tidak tersedia");
        File file = new File(dir, "input-" + System.currentTimeMillis() + ".img");
        try (FileOutputStream output = new FileOutputStream(file)) {
            output.write(bytes);
        }
        return file;
    }

    private void runGeneration(String requestJson, File temporaryImage) {
        final String id = requestId(requestJson);
        engine.generate(requestJson, new OfflineModelEngine.Callback() {
            private void cleanUp() {
                if (temporaryImage != null) temporaryImage.delete();
            }

            @Override public void onToken(String token) {
                dispatch("furina-native-token", id, token, null);
            }

            @Override public void onComplete() {
                cleanUp();
                dispatch("furina-native-complete", id, "", null);
            }

            @Override public void onError(String message) {
                cleanUp();
                dispatch("furina-native-error", id, "", message);
            }
        });
    }

    private String requestId(String requestJson) {
        try {
            return new JSONObject(requestJson).optString("requestId", "offline");
        } catch (Exception ignored) {
            return "offline";
        }
    }

    private void dispatchError(String requestId, String message) {
        dispatch("furina-native-error", requestId, "", message);
    }

    private void dispatch(String event, String requestId, String token, String error) {
        activity.runOnUiThread(() -> {
            try {
                JSONObject detail = new JSONObject();
                detail.put("requestId", requestId);
                if (!token.isEmpty()) detail.put("token", token);
                if (error != null) detail.put("error", error);
                String script = "window.dispatchEvent(new CustomEvent(" + JSONObject.quote(event) + "," +
                    "{detail:" + detail.toString() + "}));";
                webView.evaluateJavascript(script, null);
            } catch (Exception ignored) {}
        });
    }

    public void destroy() {
        engine.shutdown();
    }
}
