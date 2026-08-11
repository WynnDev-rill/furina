#!/usr/bin/env python3
"""Post-patch Furina's pinned llama.android runtime with persistent KV and mobile tuning.

Order: companion policy -> stability policy -> warm reset -> this policy.
All replacements fail closed against the pinned llama.cpp source.
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


def patch_interface(path: Path) -> None:
    replace_once(
        path,
        "    suspend fun resetConversationKeepingSystemPrompt()\n\n",
        "    suspend fun resetConversationKeepingSystemPrompt()\n\n"
        "    suspend fun saveCheckpoint(path: String): Boolean\n"
        "    suspend fun restoreCheckpoint(path: String): Boolean\n"
        "    suspend fun ensureRuntimeProfile(): String\n"
        "    fun runtimeProfile(): String\n\n",
        "adaptive interface API",
    )


def patch_cpp(path: Path) -> None:
    replace_once(
        path,
        "#include <iomanip>\n#include <cmath>\n#include <mutex>\n#include <string>\n#include <unistd.h>",
        "#include <iomanip>\n#include <cmath>\n#include <cstdint>\n#include <cstdio>\n#include <fstream>\n#include <mutex>\n#include <string>\n#include <vector>\n#include <unistd.h>",
        "checkpoint includes",
    )
    replace_once(
        path,
        '#include "common.h"\n#include "llama.h"',
        '#include "common.h"\n#include "ggml-backend.h"\n#include "llama.h"',
        "backend include",
    )
    replace_once(
        path,
        "static common_sampler                   * g_sampler;\n",
        "static common_sampler                   * g_sampler;\n"
        "static int                                g_requested_threads = 0;\n"
        "static int                                g_requested_batch_threads = 0;\n",
        "runtime globals",
    )

    old_threads = '''    const int n_threads_batch = std::max(N_THREADS_MIN, std::min(N_THREADS_MAX,
                                                     (int) sysconf(_SC_NPROCESSORS_ONLN) -
                                                     N_THREADS_HEADROOM));
    // Token generation is memory-bandwidth bound and tends to slow down when
    // Snapdragon efficiency cores join it. Prompt ingestion still uses six.
    const int n_threads = std::min(4, n_threads_batch);
    LOGi("%s: Using %d generation / %d prompt threads", __func__, n_threads, n_threads_batch);'''
    new_threads = '''    const int auto_batch_threads = std::max(N_THREADS_MIN, std::min(N_THREADS_MAX,
                                                     (int) sysconf(_SC_NPROCESSORS_ONLN) -
                                                     N_THREADS_HEADROOM));
    const int n_threads_batch = g_requested_batch_threads > 0
            ? std::max(N_THREADS_MIN, std::min(N_THREADS_MAX, g_requested_batch_threads))
            : auto_batch_threads;
    const int n_threads = g_requested_threads > 0
            ? std::max(N_THREADS_MIN, std::min(n_threads_batch, g_requested_threads))
            : std::min(4, n_threads_batch);
    LOGi("%s: Using %d generation / %d prompt threads", __func__, n_threads, n_threads_batch);'''
    replace_once(path, old_threads, new_threads, "thread selection")

    replace_once(
        path,
        '''    ctx_params.n_batch = g_active_batch_size;
    // Physical micro-batch size changes scratch memory and prompt throughput,
    // not model quality. Use the smaller shape only under RAM pressure.
    ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;
    if (g_large_model) {''',
        '''    ctx_params.n_batch = g_active_batch_size;
    // Physical micro-batch size changes scratch memory and prompt throughput,
    // not model quality. Use the smaller shape only under RAM pressure.
    ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;
    // AUTO is fail-safe: llama.cpp uses fused attention only when the current
    // model/backend supports it, otherwise the ordinary attention path remains.
    ctx_params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_AUTO;
    if (g_large_model) {''',
        "flash attention auto",
    )

    replace_once(
        path,
        '''    if (context == nullptr) {
        LOGe("%s: llama_new_context_with_model() returned null", __func__);
    } else {
        g_active_context_size = (int) llama_n_ctx(context);
    }
    return context;''',
        '''    if (context == nullptr) {
        LOGe("%s: llama_new_context_with_model() returned null", __func__);
    }
    return context;''',
        "temporary context isolation",
    )
    replace_once(
        path,
        '''    g_context = context;
    g_batch = llama_batch_init(g_active_batch_size, 0, 1);''',
        '''    g_context = context;
    g_active_context_size = (int) llama_n_ctx(g_context);
    g_batch = llama_batch_init(g_active_batch_size, 0, 1);''',
        "main context size",
    )

    old_shift = '''/**
 * TODO-hyin: implement sliding-window version as a better alternative
 *
 * Context shifting by discarding the older half of the tokens appended after system prompt:
 * - take the [system_prompt_position] first tokens from the original prompt
 * - take half of the last (system_prompt_position - system_prompt_position) tokens
 * - recompute the logits in batches
 */
static void shift_context() {
    const int n_discard = (current_position - system_prompt_position) / 2;
    LOGi("%s: Discarding %d tokens", __func__, n_discard);
    llama_memory_seq_rm(llama_get_memory(g_context), 0, system_prompt_position, system_prompt_position + n_discard);
    llama_memory_seq_add(llama_get_memory(g_context), 0, system_prompt_position + n_discard, current_position, -n_discard);
    current_position -= n_discard;
    LOGi("%s: Context shifting done! Current position: %d", __func__, current_position);
}'''
    new_shift = '''/** Preserve immutable SYSTEM KV and slide only the oldest mutable suffix. */
static bool shift_context_for(const int required_tokens) {
    if (!g_context || system_prompt_position <= 0) return false;
    const int limit = g_active_context_size - OVERFLOW_HEADROOM;
    if (current_position + required_tokens < limit) return true;

    const int mutable_tokens = current_position - system_prompt_position;
    if (mutable_tokens <= 0) return false;
    const int shortage = std::max(1, current_position + required_tokens - limit + 1);
    const int reserve = std::max(32, g_active_context_size / 10);
    const int n_discard = std::min(mutable_tokens, std::max(shortage, reserve));

    LOGi("%s: Sliding %d oldest mutable tokens; SYSTEM prefix=%d",
         __func__, n_discard, system_prompt_position);
    llama_memory_seq_rm(
            llama_get_memory(g_context), 0, system_prompt_position, system_prompt_position + n_discard);
    llama_memory_seq_add(
            llama_get_memory(g_context), 0, system_prompt_position + n_discard, current_position, -n_discard);
    current_position -= n_discard;
    return current_position + required_tokens < limit;
}'''
    replace_once(path, old_shift, new_shift, "sliding context")
    replace_once(
        path,
        '''        if (current_position + cur_batch_size >= g_active_context_size - OVERFLOW_HEADROOM) {
            LOGw("%s: Current batch won't fit into context! Shifting...", __func__);
            shift_context();
        }''',
        '''        if (current_position + cur_batch_size >= g_active_context_size - OVERFLOW_HEADROOM) {
            LOGw("%s: Current batch won't fit; sliding oldest mutable KV", __func__);
            if (!shift_context_for(cur_batch_size)) return 1;
        }''',
        "batch sliding",
    )
    replace_once(
        path,
        '''    if (current_position >= g_active_context_size - OVERFLOW_HEADROOM) {
        LOGw("%s: Context full! Shifting...", __func__);
        shift_context();
    }''',
        '''    if (current_position >= g_active_context_size - OVERFLOW_HEADROOM) {
        LOGw("%s: Context full; sliding oldest mutable KV", __func__);
        if (!shift_context_for(1)) return nullptr;
    }''',
        "generation sliding",
    )

    reset_tail = '''    LOGi("%s: conversation reset to preserved system prefix at position %d", __func__, system_prompt_position);
    return 0;
}
'''
    checkpoint_code = reset_tail + r'''

constexpr uint32_t FURINA_KV_MAGIC = 0x46554B56;
constexpr uint32_t FURINA_KV_VERSION = 4;
struct furina_checkpoint_header {
    uint32_t magic;
    uint32_t version;
    int32_t system_position;
    int32_t current_position;
    uint32_t last_role;
    uint64_t state_size;
};

static uint32_t checkpoint_last_role() {
    if (chat_msgs.empty()) return 0;
    if (chat_msgs.back().role == ROLE_ASSISTANT) return 2;
    if (chat_msgs.back().role == ROLE_USER) return 1;
    return 0;
}

extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_saveCheckpointNative(
        JNIEnv *env, jobject /*unused*/, jstring jpath) {
    if (!g_context || system_prompt_position <= 0 || current_position < system_prompt_position) return 1;
    const size_t state_size = llama_state_seq_get_size(g_context, 0);
    if (state_size == 0) return 2;
    std::vector<uint8_t> state(state_size);
    const size_t written = llama_state_seq_get_data(g_context, state.data(), state.size(), 0);
    if (written == 0 || written > state.size()) return 3;

    const char *chars = env->GetStringUTFChars(jpath, nullptr);
    const std::string path(chars);
    env->ReleaseStringUTFChars(jpath, chars);
    const std::string tmp = path + ".tmp";
    furina_checkpoint_header header {
        FURINA_KV_MAGIC, FURINA_KV_VERSION,
        (int32_t) system_prompt_position, (int32_t) current_position,
        checkpoint_last_role(), (uint64_t) written,
    };

    std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
    if (!out) return 4;
    out.write(reinterpret_cast<const char *>(&header), sizeof(header));
    out.write(reinterpret_cast<const char *>(state.data()), (std::streamsize) written);
    out.flush();
    const bool ok = out.good();
    out.close();
    if (!ok || std::rename(tmp.c_str(), path.c_str()) != 0) {
        std::remove(tmp.c_str());
        return 5;
    }
    LOGi("%s: saved %zu bytes; system=%d current=%d", __func__, written,
         system_prompt_position, current_position);
    return 0;
}

extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_restoreCheckpointNative(
        JNIEnv *env, jobject /*unused*/, jstring jpath) {
    if (!g_context) return 1;
    const char *chars = env->GetStringUTFChars(jpath, nullptr);
    const std::string path(chars);
    env->ReleaseStringUTFChars(jpath, chars);

    std::ifstream in(path, std::ios::binary);
    if (!in) return 2;
    furina_checkpoint_header header {};
    in.read(reinterpret_cast<char *>(&header), sizeof(header));
    if (!in || header.magic != FURINA_KV_MAGIC || header.version != FURINA_KV_VERSION ||
        header.system_position <= 0 || header.current_position < header.system_position ||
        header.current_position >= g_active_context_size || header.state_size == 0) return 3;

    std::vector<uint8_t> state((size_t) header.state_size);
    in.read(reinterpret_cast<char *>(state.data()), (std::streamsize) state.size());
    if (!in) return 4;
    llama_memory_clear(llama_get_memory(g_context), false);
    const size_t restored = llama_state_seq_set_data(g_context, state.data(), state.size(), 0);
    if (restored == 0) {
        llama_memory_clear(llama_get_memory(g_context), false);
        return 5;
    }

    system_prompt_position = (llama_pos) header.system_position;
    current_position = (llama_pos) header.current_position;
    chat_msgs.clear();
    chat_msgs.push_back(common_chat_msg{ROLE_SYSTEM, "[restored system prefix]"});
    if (header.last_role == 2) chat_msgs.push_back(common_chat_msg{ROLE_ASSISTANT, "[restored assistant]"});
    else if (header.last_role == 1) chat_msgs.push_back(common_chat_msg{ROLE_USER, "[restored user]"});
    reset_short_term_states();
    if (g_sampler) common_sampler_reset(g_sampler);
    LOGi("%s: restored %zu bytes; system=%d current=%d", __func__, restored,
         system_prompt_position, current_position);
    return 0;
}

extern "C"
JNIEXPORT void JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_configureRuntimeThreadsNative(
        JNIEnv *, jobject, jint generation_threads, jint prompt_threads) {
    g_requested_threads = std::max(N_THREADS_MIN, std::min(N_THREADS_MAX, (int) generation_threads));
    g_requested_batch_threads = std::max(g_requested_threads,
            std::max(N_THREADS_MIN, std::min(N_THREADS_MAX, (int) prompt_threads)));
    if (g_context) llama_set_n_threads(g_context, g_requested_threads, g_requested_batch_threads);
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_runtimeProfileNative(JNIEnv *env, jobject) {
    std::ostringstream out;
    out << "cpu:g" << (g_requested_threads > 0 ? g_requested_threads : 4)
        << ":p" << (g_requested_batch_threads > 0 ? g_requested_batch_threads : 6)
        << ":ctx" << g_active_context_size << ":fa-auto:devices=";
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        if (i) out << ",";
        out << ggml_backend_dev_name(ggml_backend_dev_get(i));
    }
    return env->NewStringUTF(out.str().c_str());
}
'''
    replace_once(path, reset_tail, checkpoint_code, "checkpoint API")

    replace_once(
        path,
        '''    g_large_model = false;
    g_low_memory_mode = false;
}''',
        '''    g_large_model = false;
    g_low_memory_mode = false;
    g_requested_threads = 0;
    g_requested_batch_threads = 0;
}''',
        "runtime reset",
    )


def patch_impl(path: Path) -> None:
    replace_once(
        path,
        '''import android.os.Build
import android.util.Log''',
        '''import android.os.Build
import android.os.PowerManager
import android.util.Log''',
        "PowerManager import",
    )
    replace_once(
        path,
        '''    @FastNative
    private external fun resetConversationKeepingSystemPromptNative(): Int
''',
        '''    @FastNative
    private external fun resetConversationKeepingSystemPromptNative(): Int
    private external fun saveCheckpointNative(path: String): Int
    private external fun restoreCheckpointNative(path: String): Int
    @FastNative private external fun configureRuntimeThreadsNative(generationThreads: Int, promptThreads: Int)
    @FastNative private external fun runtimeProfileNative(): String
''',
        "native declarations",
    )
    replace_once(
        path,
        '''    @Volatile
    private var _cancelGeneration = false
''',
        '''    @Volatile
    private var _cancelGeneration = false
    @Volatile private var activeRuntimeKey = ""
    @Volatile private var activeGenerationThreads = 4
    @Volatile private var activePromptThreads = 6
    @Volatile private var activeRuntimeLabel = "cpu:g4:p6:pending"

    private val runtimePrefs by lazy {
        appContext.getSharedPreferences("furina_llama_runtime_v4", Context.MODE_PRIVATE)
    }

    private fun runtimeKey(modelFile: File): String = buildString {
        append(Build.SOC_MANUFACTURER).append(':')
        append(Build.SOC_MODEL).append(':')
        append(Build.VERSION.SDK_INT).append(':')
        append(modelFile.length()).append(':')
        append(modelFile.name.hashCode())
    }

    private fun applyThreads(generation: Int, prompt: Int) {
        activeGenerationThreads = generation.coerceIn(2, 6)
        activePromptThreads = prompt.coerceIn(activeGenerationThreads, 6)
        configureRuntimeThreadsNative(activeGenerationThreads, activePromptThreads)
        activeRuntimeLabel = runtimeProfileNative()
    }

    private fun applySavedRuntimeProfile() {
        if (activeRuntimeKey.isBlank()) return
        val generation = runtimePrefs.getInt("$activeRuntimeKey:g", 0)
        val prompt = runtimePrefs.getInt("$activeRuntimeKey:p", 0)
        if (generation > 0 && prompt > 0) applyThreads(generation, prompt)
    }

    private fun applyThermalThreadCap() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return
        val pm = appContext.getSystemService(Context.POWER_SERVICE) as PowerManager
        when {
            pm.currentThermalStatus >= PowerManager.THERMAL_STATUS_SEVERE ->
                configureRuntimeThreadsNative(2, 3)
            pm.currentThermalStatus >= PowerManager.THERMAL_STATUS_MODERATE ->
                configureRuntimeThreadsNative(
                    (activeGenerationThreads - 1).coerceAtLeast(2),
                    (activePromptThreads - 1).coerceAtLeast(3),
                )
            else -> configureRuntimeThreadsNative(activeGenerationThreads, activePromptThreads)
        }
    }
''',
        "runtime Kotlin state",
    )
    replace_once(
        path,
        '''                val modelFile = File(pathToModel)
                modelFile.let {''',
        '''                val modelFile = File(pathToModel)
                activeRuntimeKey = runtimeKey(modelFile)
                modelFile.let {''',
        "runtime key",
    )
    replace_once(
        path,
        '''                markProcessStage("native-context-prepare")
                prepare().let {''',
        '''                applySavedRuntimeProfile()
                markProcessStage("native-context-prepare")
                prepare().let {''',
        "saved profile restore",
    )

    marker = '''    /**
     * Send plain text user prompt to LLM, which starts generating tokens in a [Flow]
     */
'''
    methods = '''    override suspend fun saveCheckpoint(path: String): Boolean =
        withContext(llamaDispatcher) {
            check(_state.value is InferenceEngine.State.ModelReady) {
                "Cannot save checkpoint in ${_state.value.javaClass.simpleName}!"
            }
            saveCheckpointNative(path) == 0
        }

    override suspend fun restoreCheckpoint(path: String): Boolean =
        withContext(llamaDispatcher) {
            check(_state.value is InferenceEngine.State.ModelReady) {
                "Cannot restore checkpoint in ${_state.value.javaClass.simpleName}!"
            }
            restoreCheckpointNative(path) == 0
        }

    private fun benchmarkRates(raw: String): Pair<Double, Double> {
        var pp = 0.0
        var tg = 0.0
        Regex("\\|\\s+(pp|tg)\\s+\\d+\\s+\\|\\s+([0-9.]+)").findAll(raw).forEach { match ->
            val value = match.groupValues[2].toDoubleOrNull() ?: 0.0
            if (match.groupValues[1] == "pp") pp = value else tg = value
        }
        return pp to tg
    }

    override suspend fun ensureRuntimeProfile(): String {
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

    override fun runtimeProfile(): String = activeRuntimeLabel

'''
    replace_once(path, marker, methods + marker, "adaptive methods")
    replace_once(
        path,
        '''        try {
            Log.i(TAG, "Sending user prompt...")''',
        '''        try {
            applyThermalThreadCap()
            Log.i(TAG, "Sending user prompt...")''',
        "thermal cap",
    )


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: apply-offline-runtime-v4-policy.py <ai_chat.cpp> <InferenceEngine.kt> <InferenceEngineImpl.kt>")
    patch_cpp(Path(sys.argv[1]))
    patch_interface(Path(sys.argv[2]))
    patch_impl(Path(sys.argv[3]))
    print("Applied offline runtime v4: persistent KV, sliding context, FA auto, CPU autotune, thermal governor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
