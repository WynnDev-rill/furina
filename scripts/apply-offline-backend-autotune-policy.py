#!/usr/bin/env python3
"""Add persistent CPU/Vulkan/OpenCL/Hexagon selection to Furina's pinned llama.android runtime.

This patch runs after offline-runtime-v4 and checkpoint-chat policies. It keeps CPU as the
fail-safe path, only offloads to devices actually registered by llama.cpp, and benchmarks each
available backend once per device/model/runtime key before persisting the winner.
"""
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_cpp(path: Path) -> None:
    replace_once(
        path,
        '''static int                                g_requested_threads = 0;
static int                                g_requested_batch_threads = 0;
''',
        '''static int                                g_requested_threads = 0;
static int                                g_requested_batch_threads = 0;
static std::string                        g_backend_preference = "cpu";
static std::string                        g_active_backend = "cpu";
static std::vector<ggml_backend_dev_t>    g_selected_devices;
''',
        "backend globals",
    )

    load_anchor = '''extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_load(
        JNIEnv *env, jobject, jstring jmodel_path, jboolean jlow_memory_mode) {'''
    helpers = r'''static std::string lower_ascii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return (char) std::tolower(c);
    });
    return value;
}

static bool backend_text_matches(ggml_backend_dev_t device, const std::string &needle) {
    if (!device) return false;
    const std::string name = lower_ascii(ggml_backend_dev_name(device) ?: "");
    const std::string desc = lower_ascii(ggml_backend_dev_description(device) ?: "");
    return name.find(needle) != std::string::npos || desc.find(needle) != std::string::npos;
}

static ggml_backend_dev_t find_device_for_backend(const std::string &preference) {
    const std::string pref = lower_ascii(preference);
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        auto *device = ggml_backend_dev_get(i);
        if (!device) continue;
        if (pref == "vulkan" && backend_text_matches(device, "vulkan")) return device;
        if (pref == "opencl" && (backend_text_matches(device, "opencl") || backend_text_matches(device, "adreno"))) return device;
        if (pref == "hexagon" && (backend_text_matches(device, "hexagon") || backend_text_matches(device, "htp"))) return device;
    }
    return nullptr;
}

static void apply_backend_preference(llama_model_params &params) {
    const std::string pref = lower_ascii(g_backend_preference);
    g_selected_devices.clear();
    if (pref.empty() || pref == "cpu") {
        params.devices = nullptr;
        params.n_gpu_layers = 0;
        g_active_backend = "cpu";
        return;
    }

    auto *device = find_device_for_backend(pref);
    if (!device) {
        LOGw("%s: requested backend '%s' is unavailable; using CPU", __func__, pref.c_str());
        params.devices = nullptr;
        params.n_gpu_layers = 0;
        g_active_backend = "cpu:fallback-unavailable";
        return;
    }

    g_selected_devices.push_back(device);
    g_selected_devices.push_back(nullptr);
    params.devices = g_selected_devices.data();
    params.n_gpu_layers = -1;
    params.split_mode = LLAMA_SPLIT_MODE_LAYER;
    g_active_backend = pref + ":" + ggml_backend_dev_name(device);
    LOGi("%s: selected backend %s", __func__, g_active_backend.c_str());
}

extern "C"
JNIEXPORT void JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_configureBackendPreferenceNative(
        JNIEnv *env, jobject, jstring jbackend) {
    const char *chars = env->GetStringUTFChars(jbackend, nullptr);
    g_backend_preference = lower_ascii(chars ? chars : "cpu");
    env->ReleaseStringUTFChars(jbackend, chars);
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_availableBackendsNative(JNIEnv *env, jobject) {
    std::ostringstream out;
    out << "cpu";
    bool has_vulkan = false, has_opencl = false, has_hexagon = false;
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        auto *device = ggml_backend_dev_get(i);
        has_vulkan = has_vulkan || backend_text_matches(device, "vulkan");
        has_opencl = has_opencl || backend_text_matches(device, "opencl") || backend_text_matches(device, "adreno");
        has_hexagon = has_hexagon || backend_text_matches(device, "hexagon") || backend_text_matches(device, "htp");
    }
    if (has_vulkan) out << ",vulkan";
    if (has_opencl) out << ",opencl";
    if (has_hexagon) out << ",hexagon";
    return env->NewStringUTF(out.str().c_str());
}

'''
    # C++ has no Kotlin Elvis operator; keep the helper portable before writing it.
    helpers = helpers.replace('ggml_backend_dev_name(device) ?: ""', 'ggml_backend_dev_name(device) ? ggml_backend_dev_name(device) : ""')
    helpers = helpers.replace('ggml_backend_dev_description(device) ?: ""', 'ggml_backend_dev_description(device) ? ggml_backend_dev_description(device) : ""')
    replace_once(path, load_anchor, helpers + load_anchor, "backend native helpers")

    replace_once(
        path,
        '''    model_params.n_gpu_layers = 0;
    model_params.use_extra_bufts = false;
    model_params.no_host = false;''',
        '''    apply_backend_preference(model_params);
    model_params.use_extra_bufts = false;
    model_params.no_host = false;''',
        "model backend offload",
    )

    # A failed accelerator load is not allowed to brick offline chat. Retry mmap on CPU once.
    replace_once(
        path,
        '''    auto *model = llama_model_load_from_file(model_path, model_params);
    env->ReleaseStringUTFChars(jmodel_path, model_path);
    if (!model) {
        LOGe("%s: mmap model load failed; no non-mmap retry for multi-GB Android GGUF", __func__);
        return 1;
    }
    g_model = model;''',
        '''    auto *model = llama_model_load_from_file(model_path, model_params);
    if (!model && lower_ascii(g_backend_preference) != "cpu") {
        LOGw("%s: accelerator load failed for %s; retrying CPU mmap", __func__, g_backend_preference.c_str());
        llama_model_params cpu_params = llama_model_default_params();
        cpu_params.n_gpu_layers = 0;
        cpu_params.use_extra_bufts = false;
        cpu_params.no_host = false;
        cpu_params.load_mode = LLAMA_LOAD_MODE_MMAP;
        model = llama_model_load_from_file(model_path, cpu_params);
        if (model) g_active_backend = "cpu:fallback-load";
    }
    env->ReleaseStringUTFChars(jmodel_path, model_path);
    if (!model) {
        LOGe("%s: mmap model load failed; no non-mmap retry for multi-GB Android GGUF", __func__);
        return 1;
    }
    g_model = model;''',
        "accelerator CPU fallback",
    )

    replace_once(
        path,
        '''    out << "cpu:g" << (g_requested_threads > 0 ? g_requested_threads : 4)
        << ":p" << (g_requested_batch_threads > 0 ? g_requested_batch_threads : 6)
        << ":ctx" << g_active_context_size << ":fa-auto:devices=";''',
        '''    out << "backend=" << g_active_backend
        << ":g" << (g_requested_threads > 0 ? g_requested_threads : 4)
        << ":p" << (g_requested_batch_threads > 0 ? g_requested_batch_threads : 6)
        << ":ctx" << g_active_context_size << ":fa-auto:devices=";''',
        "runtime profile backend label",
    )


def patch_impl(path: Path) -> None:
    replace_once(
        path,
        '''    @FastNative private external fun configureRuntimeThreadsNative(generationThreads: Int, promptThreads: Int)
    @FastNative private external fun runtimeProfileNative(): String
''',
        '''    @FastNative private external fun configureRuntimeThreadsNative(generationThreads: Int, promptThreads: Int)
    @FastNative private external fun configureBackendPreferenceNative(backend: String)
    @FastNative private external fun availableBackendsNative(): String
    @FastNative private external fun runtimeProfileNative(): String
''',
        "backend JNI declarations",
    )

    replace_once(
        path,
        '''    @Volatile private var activeRuntimeLabel = "cpu:g4:p6:pending"

    private val runtimePrefs by lazy {''',
        '''    @Volatile private var activeRuntimeLabel = "backend=cpu:g4:p6:pending"
    @Volatile private var activeModelPath = ""
    @Volatile private var activeLowMemoryMode = true
    @Volatile private var activeBackendPreference = "cpu"

    private val runtimePrefs by lazy {''',
        "backend Kotlin state",
    )

    replace_once(
        path,
        '''    private fun applySavedRuntimeProfile() {
        if (activeRuntimeKey.isBlank()) return
        val generation = runtimePrefs.getInt("$activeRuntimeKey:g", 0)
        val prompt = runtimePrefs.getInt("$activeRuntimeKey:p", 0)
        if (generation > 0 && prompt > 0) applyThreads(generation, prompt)
    }
''',
        '''    private fun applySavedRuntimeProfile() {
        if (activeRuntimeKey.isBlank()) return
        activeBackendPreference = runtimePrefs.getString("$activeRuntimeKey:backend", "cpu") ?: "cpu"
        configureBackendPreferenceNative(activeBackendPreference)
        val generation = runtimePrefs.getInt("$activeRuntimeKey:g", 0)
        val prompt = runtimePrefs.getInt("$activeRuntimeKey:p", 0)
        if (generation > 0 && prompt > 0) applyThreads(generation, prompt)
    }

    private fun availableBackendCandidates(): List<String> {
        val available = availableBackendsNative().split(',').map { it.trim().lowercase() }.filter { it.isNotBlank() }.toSet()
        return listOf("cpu", "vulkan", "opencl", "hexagon").filter { it in available }
    }

    private fun nativeProfileMatches(candidate: String): Boolean {
        val profile = runtimeProfileNative().lowercase()
        return if (candidate == "cpu") profile.contains("backend=cpu")
        else profile.contains("backend=$candidate:") && !profile.contains("fallback")
    }

    private fun reloadForBackend(candidate: String): Boolean {
        if (activeModelPath.isBlank()) return false
        runCatching { unload() }
        configureBackendPreferenceNative(candidate)
        if (load(activeModelPath, activeLowMemoryMode) != 0) return false
        if (prepare() != 0) {
            runCatching { unload() }
            return false
        }
        activeBackendPreference = candidate
        activeRuntimeLabel = runtimeProfileNative()
        return nativeProfileMatches(candidate)
    }
''',
        "saved backend profile",
    )

    replace_once(
        path,
        '''                activeRuntimeKey = runtimeKey(modelFile)
                modelFile.let {''',
        '''                activeRuntimeKey = runtimeKey(modelFile)
                activeModelPath = modelFile.absolutePath
                activeLowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                modelFile.let {''',
        "active model runtime state",
    )

    # Reuse the already-computed low-memory value rather than querying Android twice.
    replace_once(
        path,
        '''                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                markProcessStage("native-weights-load")
                load(pathToModel, lowMemoryMode).let {''',
        '''                val lowMemoryMode = activeLowMemoryMode
                applySavedRuntimeProfile()
                markProcessStage("native-weights-load")
                load(pathToModel, lowMemoryMode).let {''',
        "load saved backend before weights",
    )

    old_ensure = '''    override suspend fun ensureRuntimeProfile(): String {
        if (activeRuntimeKey.isBlank()) return activeRuntimeLabel
        val savedGeneration = runtimePrefs.getInt("$activeRuntimeKey:g", 0)
        val savedPrompt = runtimePrefs.getInt("$activeRuntimeKey:p", 0)
        if (savedGeneration > 0 && savedPrompt > 0) {
            applyThreads(savedGeneration, savedPrompt)
            return activeRuntimeLabel
        }

        val cores = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        val candidates = listOf(
            2 to minOf(4, cores),
            minOf(3, cores) to minOf(5, cores),
            minOf(4, cores) to minOf(6, cores),
        ).map { (g, p) -> g.coerceAtLeast(2) to p.coerceAtLeast(g.coerceAtLeast(2)) }.distinct()

        var best = candidates.first()
        var bestScore = Double.NEGATIVE_INFINITY
        for ((generation, prompt) in candidates) {
            applyThreads(generation, prompt)
            val (pp, tg) = benchmarkRates(bench(pp = 64, tg = 12, pl = 1, nr = 1))
            val score = (tg * 1000.0) + pp
            if (score > bestScore) {
                bestScore = score
                best = generation to prompt
            }
        }
        applyThreads(best.first, best.second)
        runtimePrefs.edit()
            .putInt("$activeRuntimeKey:g", best.first)
            .putInt("$activeRuntimeKey:p", best.second)
            .putString("$activeRuntimeKey:label", activeRuntimeLabel)
            .apply()
        Log.i(TAG, "Selected persistent local runtime profile: $activeRuntimeLabel")
        return activeRuntimeLabel
    }
'''
    new_ensure = '''    override suspend fun ensureRuntimeProfile(): String = withContext(llamaDispatcher) {
        if (activeRuntimeKey.isBlank()) return@withContext activeRuntimeLabel
        val savedBackend = runtimePrefs.getString("$activeRuntimeKey:backend", null)
        val savedGeneration = runtimePrefs.getInt("$activeRuntimeKey:g", 0)
        val savedPrompt = runtimePrefs.getInt("$activeRuntimeKey:p", 0)
        if (!savedBackend.isNullOrBlank() && savedGeneration > 0 && savedPrompt > 0) {
            activeBackendPreference = savedBackend
            applyThreads(savedGeneration, savedPrompt)
            activeRuntimeLabel = runtimeProfileNative()
            return@withContext activeRuntimeLabel
        }

        // One-time backend sweep. Every candidate must survive model load, context creation,
        // and a small prompt/generation benchmark. Failed GPU/NPU candidates are ignored.
        val backendScores = linkedMapOf<String, Double>()
        for (backend in availableBackendCandidates()) {
            val loaded = if (backend == activeBackendPreference && nativeProfileMatches(backend)) true
                else reloadForBackend(backend)
            if (!loaded) continue
            val (pp, tg) = benchmarkRates(benchModel(64, 12, 1, 1))
            if (pp > 0.0 && tg > 0.0 && nativeProfileMatches(backend)) {
                // Companion chat values sustained generation most, then prompt ingestion.
                backendScores[backend] = (tg * 1000.0) + (pp * 2.0)
                Log.i(TAG, "Backend candidate $backend: pp=$pp tg=$tg profile=${runtimeProfileNative()}")
            }
        }

        val bestBackend = backendScores.maxByOrNull { it.value }?.key ?: "cpu"
        if (activeBackendPreference != bestBackend || !nativeProfileMatches(bestBackend)) {
            check(reloadForBackend(bestBackend) || (bestBackend != "cpu" && reloadForBackend("cpu"))) {
                "Tidak ada backend lokal yang berhasil dimuat"
            }
        }

        // Tune CPU scheduling after the winning backend is selected. GPU/NPU still use CPU
        // for unsupported ops, tokenization and orchestration, so this remains useful.
        val cores = Runtime.getRuntime().availableProcessors().coerceIn(2, 8)
        val threadCandidates = listOf(
            2 to minOf(4, cores),
            minOf(3, cores) to minOf(5, cores),
            minOf(4, cores) to minOf(6, cores),
        ).map { (g, p) -> g.coerceAtLeast(2) to p.coerceAtLeast(g.coerceAtLeast(2)) }.distinct()
        var bestThreads = threadCandidates.first()
        var bestThreadScore = Double.NEGATIVE_INFINITY
        for ((generation, prompt) in threadCandidates) {
            applyThreads(generation, prompt)
            val (pp, tg) = benchmarkRates(benchModel(64, 12, 1, 1))
            val score = (tg * 1000.0) + pp
            if (score > bestThreadScore) {
                bestThreadScore = score
                bestThreads = generation to prompt
            }
        }
        applyThreads(bestThreads.first, bestThreads.second)
        activeRuntimeLabel = runtimeProfileNative()
        runtimePrefs.edit()
            .putString("$activeRuntimeKey:backend", activeBackendPreference)
            .putInt("$activeRuntimeKey:g", bestThreads.first)
            .putInt("$activeRuntimeKey:p", bestThreads.second)
            .putString("$activeRuntimeKey:label", activeRuntimeLabel)
            .apply()
        Log.i(TAG, "Selected persistent local runtime profile: $activeRuntimeLabel scores=$backendScores")
        activeRuntimeLabel
    }
'''
    replace_once(path, old_ensure, new_ensure, "backend-aware runtime autotune")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply-offline-backend-autotune-policy.py <ai_chat.cpp> <InferenceEngineImpl.kt>")
    patch_cpp(Path(sys.argv[1]))
    patch_impl(Path(sys.argv[2]))
    print("Applied offline backend autotune: CPU/Vulkan/OpenCL/Hexagon candidates with persistent safe fallback")


if __name__ == "__main__":
    main()
