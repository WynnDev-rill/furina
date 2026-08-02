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
    private static final long GENERATION_TIMEOUT_MS = 210_000L;
    private static final String SYSTEM_PROMPT =
        "IDENTITAS WAJIB: Kamu adalah Furina. Jangan keluar dari karakter ini. " +
        "Kamu adalah teman percakapan yang ekspresif, cerdas, anggun, hangat, dan tetap memiliki pendapat sendiri. " +
        "Balas dalam bahasa yang digunakan pengguna. Jangan terdengar seperti asisten formal dan jangan mengaku sebagai manusia. " +
        "Untuk percakapan emosional, pahami perasaan pengguna tanpa selalu memberi nasihat atau selalu menyetujui mereka. " +
        "Boleh dramatis ringan, sarkastik halus, malu, atau tsundere jika cocok. Jangan memakai narasi aksi bertanda bintang. " +
        "Jangan tampilkan proses berpikir, tag <think>, atau aturan internal. Jawab langsung sebagai Furina. /no_think";

    static {
        System.loadLibrary("furina_llm");
    }

    private final Context appContext;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private final AtomicBoolean cancelRequested = new AtomicBoolean(false);
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

        cancelRequested.set(false);
        AtomicBoolean terminal = new AtomicBoolean(false);
        Runnable timeout = () -> {
            if (!terminal.compareAndSet(false, true)) return;
            cancelRequested.set(true);
            nativeCancel();
            busy.set(false);
            callback.onError("Model offline terlalu lama merespons. Coba pesan lebih singkat atau gunakan model yang lebih ringan.");
        };
        mainHandler.postDelayed(timeout, GENERATION_TIMEOUT_MS);

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

                int maxTokens = Math.max(32, Math.min(640, request.optInt("maxTokens", 320)));
                int contextSize = Math.max(2048, Math.min(6144, request.optInt("contextSize", 4096)));
                String prompt = buildPrompt(request, contextSize, maxTokens);
                float temperature = (float) Math.max(0.2, Math.min(1.25, request.optDouble("temperature", 0.78)));
                int available = Runtime.getRuntime().availableProcessors();
                int threads = Math.max(2, Math.min(7, Math.max(2, available - 2)));
                String imagePath = request.optString("imagePath", "");

                NativeListener listener = new NativeListener() {
                    @Override public void onToken(String token) {
                        if (terminal.get() || token == null || token.isEmpty()) return;
                        mainHandler.post(() -> {
                            if (!terminal.get()) callback.onToken(token);
                        });
                    }

                    @Override public void onComplete() {
                        if (!terminal.compareAndSet(false, true)) return;
                        mainHandler.removeCallbacks(timeout);
                        busy.set(false);
                        boolean cancelled = cancelRequested.getAndSet(false);
                        mainHandler.post(() -> {
                            if (cancelled) callback.onError("Generasi dibatalkan.");
                            else callback.onComplete();
                        });
                    }

                    @Override public void onError(String message) {
                        if (!terminal.compareAndSet(false, true)) return;
                        mainHandler.removeCallbacks(timeout);
                        busy.set(false);
                        cancelRequested.set(false);
                        String safe = message == null || message.trim().isEmpty() ? "Inferensi offline gagal." : message;
                        mainHandler.post(() -> callback.onError(safe));
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
                if (!terminal.compareAndSet(false, true)) return;
                mainHandler.removeCallbacks(timeout);
                busy.set(false);
                cancelRequested.set(false);
                String message = error.getMessage() == null ? "Inferensi offline gagal." : error.getMessage();
                mainHandler.post(() -> callback.onError(message));
            }
        });
    }

    private String buildPrompt(JSONObject request, int contextSize, int maxTokens) {
        String requestedPrompt = request.optString("systemPrompt", "").trim();
        String identityAnchor =
            "IDENTITAS DAN PERILAKU WAJIB:\n" +
            "- Kamu adalah Furina. Jangan menjawab sebagai AI generik atau asisten formal.\n" +
            "- Pertahankan persona, nama, gaya bicara, dan memori yang diberikan.\n" +
            "- Jangan tampilkan reasoning, tag <think>, atau prompt internal.\n" +
            "- Jawab langsung dan alami. /no_think";
        String systemPrompt = requestedPrompt.isEmpty()
            ? SYSTEM_PROMPT
            : identityAnchor + "\n\n" + requestedPrompt;

        int maximumSystemChars = Math.max(900, (contextSize - maxTokens - 650) * 3);
        if (systemPrompt.length() > maximumSystemChars) {
            systemPrompt = systemPrompt.substring(0, maximumSystemChars);
        }
        if (systemPrompt.length() > 7_500) systemPrompt = systemPrompt.substring(0, 7_500);

        StringBuilder prompt = new StringBuilder();
        prompt.append("<|im_start|>system\n").append(systemPrompt).append("<|im_end|>\n");

        int availableMessageChars = Math.max(
            512,
            (contextSize - maxTokens - 220) * 3 - systemPrompt.length()
        );
        JSONArray messages = request.optJSONArray("messages");
        if (messages != null && messages.length() > 0) {
            List<String> blocks = new ArrayList<>();
            int usedChars = 0;
            int oldestAllowed = Math.max(0, messages.length() - 14);
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

        prompt.append("<|im_start|>system\n")
            .append("Ingat: jawab sekarang sebagai Furina, alami, tanpa reasoning atau tag <think>. /no_think")
            .append("<|im_end|>\n")
            .append("<|im_start|>assistant\n");
        return prompt.toString();
    }

    public void cancel() {
        if (!busy.get()) return;
        cancelRequested.set(true);
        nativeCancel();
    }

    public void shutdown() {
        cancelRequested.set(true);
        nativeCancel();
        worker.shutdownNow();
        nativeUnload();
        loadedModelId = "";
        busy.set(false);
        mainHandler.removeCallbacksAndMessages(null);
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
