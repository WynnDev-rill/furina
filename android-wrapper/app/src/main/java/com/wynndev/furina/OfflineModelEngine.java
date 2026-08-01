package com.wynndev.furina;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class OfflineModelEngine {
    public interface Callback {
        void onToken(String token);
        void onComplete();
        void onError(String message);
    }

    public interface NativeListener {
        void onToken(String token);
        void onComplete();
        void onError(String message);
    }

    private static final String PREFS = "furina_model_manager";
    private static final String ACTIVE_MODEL = "active_model";
    private static final String SYSTEM_PROMPT =
        "Kamu adalah Furina, teman percakapan yang ekspresif, cerdas, hangat, dan tetap memiliki pendapat sendiri. " +
        "Balas dalam bahasa yang digunakan pengguna. Jangan terdengar seperti asisten formal. Jangan mengaku sebagai manusia. " +
        "Untuk percakapan emosional, pahami perasaan pengguna tanpa selalu memberi nasihat atau selalu menyetujui mereka. " +
        "Jaga jawaban tetap alami dan sesuai panjang pesan pengguna.";

    static {
        System.loadLibrary("furina_llm");
    }

    private final Context appContext;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private String loadedModelId = "";

    public OfflineModelEngine(Context context) {
        appContext = context.getApplicationContext();
    }

    public String activeModelId() {
        SharedPreferences prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return prefs.getString(ACTIVE_MODEL, "");
    }

    private File modelDirectory() {
        File external = appContext.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        File root = new File(external != null ? external : appContext.getFilesDir(), "models");
        if (!root.exists()) root.mkdirs();
        return root;
    }

    public File modelFile(String modelId) {
        return new File(modelDirectory(), modelId + ".gguf");
    }

    public File projectorFile(String modelId) {
        return new File(modelDirectory(), modelId + "-mmproj.gguf");
    }

    public boolean isInstalled(String modelId) {
        File file = modelFile(modelId);
        return file.isFile() && file.length() > 100_000_000L;
    }

    public boolean isVisionReady(String modelId) {
        File file = projectorFile(modelId);
        return "qwen35-4b".equals(modelId) && isInstalled(modelId) && file.isFile() && file.length() > 100_000_000L;
    }

    public boolean isBusy() {
        return busy.get();
    }

    public void generate(String requestJson, Callback callback) {
        if (!busy.compareAndSet(false, true)) {
            callback.onError("Model sedang menghasilkan jawaban lain.");
            return;
        }

        worker.execute(() -> {
            try {
                JSONObject request = new JSONObject(requestJson);
                String modelId = request.optString("modelId", activeModelId());
                if (modelId.isEmpty()) throw new IllegalStateException("Pilih model offline terlebih dahulu.");
                if (!isInstalled(modelId)) throw new IllegalStateException("Model belum diunduh atau file model tidak lengkap.");

                File file = modelFile(modelId);
                if (!modelId.equals(loadedModelId) || !nativeIsLoaded()) {
                    nativeUnload();
                    if (!nativeLoad(file.getAbsolutePath())) {
                        throw new IllegalStateException("Model gagal dimuat. RAM mungkin tidak cukup atau file model rusak.");
                    }
                    loadedModelId = modelId;
                }

                int maxTokens = Math.max(32, Math.min(768, request.optInt("maxTokens", 320)));
                int contextSize = Math.max(2048, Math.min(8192, request.optInt("contextSize", 4096)));
                String prompt = buildPrompt(request, contextSize, maxTokens);
                float temperature = (float) Math.max(0.2, Math.min(1.4, request.optDouble("temperature", 0.82)));
                int available = Runtime.getRuntime().availableProcessors();
                int threads = Math.max(2, Math.min(8, Math.max(2, available - 1)));
                String imagePath = request.optString("imagePath", "");

                NativeListener listener = new NativeListener() {
                    @Override public void onToken(String token) {
                        mainHandler.post(() -> callback.onToken(token));
                    }

                    @Override public void onComplete() {
                        busy.set(false);
                        mainHandler.post(callback::onComplete);
                    }

                    @Override public void onError(String message) {
                        busy.set(false);
                        mainHandler.post(() -> callback.onError(message));
                    }
                };

                if (!imagePath.isEmpty()) {
                    if (!"qwen35-4b".equals(modelId)) {
                        throw new IllegalStateException("Model aktif tidak mendukung gambar. Pilih Qwen3.5-4B.");
                    }
                    if (!isVisionReady(modelId)) {
                        throw new IllegalStateException("Projector gambar Qwen3.5 belum selesai diunduh.");
                    }
                    nativeGenerateVision(
                        prompt,
                        imagePath,
                        projectorFile(modelId).getAbsolutePath(),
                        maxTokens,
                        temperature,
                        Math.max(4096, contextSize),
                        threads,
                        listener
                    );
                } else {
                    nativeGenerate(prompt, maxTokens, temperature, contextSize, threads, listener);
                }
            } catch (Exception error) {
                busy.set(false);
                String message = error.getMessage() == null ? "Inferensi offline gagal." : error.getMessage();
                mainHandler.post(() -> callback.onError(message));
            }
        });
    }

    private String buildPrompt(JSONObject request, int contextSize, int maxTokens) {
        String requestedPrompt = request.optString("systemPrompt", "").trim();
        String systemPrompt = requestedPrompt.isEmpty() ? SYSTEM_PROMPT : requestedPrompt;
        int maximumSystemChars = Math.max(600, (contextSize - maxTokens - 500) * 3);
        if (systemPrompt.length() > maximumSystemChars) {
            systemPrompt = systemPrompt.substring(0, maximumSystemChars);
        }
        if (systemPrompt.length() > 6_000) systemPrompt = systemPrompt.substring(0, 6_000);

        StringBuilder prompt = new StringBuilder();
        prompt.append("<|im_start|>system\n").append(systemPrompt).append("<|im_end|>\n");

        int availableMessageChars = Math.max(
            384,
            (contextSize - maxTokens - 160) * 3 - systemPrompt.length()
        );
        JSONArray messages = request.optJSONArray("messages");
        if (messages != null && messages.length() > 0) {
            List<String> blocks = new ArrayList<>();
            int usedChars = 0;
            int oldestAllowed = Math.max(0, messages.length() - 20);
            for (int i = messages.length() - 1; i >= oldestAllowed; i--) {
                JSONObject message = messages.optJSONObject(i);
                if (message == null) continue;
                String role = message.optString("role", "user");
                if (!role.equals("assistant") && !role.equals("user")) continue;
                String content = message.optString("content", "").trim();
                if (content.isEmpty()) continue;

                String prefix = "<|im_start|>" + role + "\n";
                String suffix = "<|im_end|>\n";
                int remaining = availableMessageChars - usedChars;
                int contentLimit = remaining - prefix.length() - suffix.length();
                if (contentLimit < 96) break;

                if (content.length() > contentLimit) {
                    if (!blocks.isEmpty()) continue;
                    int side = Math.max(32, (contentLimit - 7) / 2);
                    if (side * 2 + 7 > content.length()) {
                        content = content.substring(0, Math.min(content.length(), contentLimit));
                    } else {
                        content = content.substring(0, side) + "\n…\n" + content.substring(content.length() - side);
                    }
                }

                String block = prefix + content + suffix;
                if (block.length() > remaining) continue;
                blocks.add(block);
                usedChars += block.length();
            }
            Collections.reverse(blocks);
            for (String block : blocks) prompt.append(block);
        } else {
            String text = request.optString("text", "").trim();
            if (text.isEmpty()) text = "Jelaskan isi gambar ini secara jelas.";
            int textLimit = Math.max(96, availableMessageChars - 40);
            if (text.length() > textLimit) text = text.substring(0, textLimit);
            prompt.append("<|im_start|>user\n").append(text).append("<|im_end|>\n");
        }

        prompt.append("<|im_start|>assistant\n");
        return prompt.toString();
    }

    public void cancel() {
        nativeCancel();
    }

    public void shutdown() {
        nativeCancel();
        worker.shutdownNow();
        nativeUnload();
        loadedModelId = "";
        busy.set(false);
    }

    private static native boolean nativeLoad(String path);
    private static native void nativeUnload();
    private static native void nativeCancel();
    private static native boolean nativeIsLoaded();
    private static native void nativeGenerate(
        String prompt,
        int maxTokens,
        float temperature,
        int contextSize,
        int threadCount,
        NativeListener listener
    );
    private static native void nativeGenerateVision(
        String prompt,
        String imagePath,
        String mmprojPath,
        int maxTokens,
        float temperature,
        int contextSize,
        int threadCount,
        NativeListener listener
    );
}
