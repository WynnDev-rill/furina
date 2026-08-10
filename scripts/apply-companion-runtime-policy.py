#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_cpp(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "constexpr float DEFAULT_SAMPLER_TEMP    = 0.3f;",
        "constexpr float DEFAULT_SAMPLER_TEMP    = 0.7f;",
        "sampler temperature",
    )

    text = replace_once(
        text,
        '''static int                                g_active_context_size = DEFAULT_CONTEXT_SIZE;
static int                                g_active_batch_size = BATCH_SIZE;
static bool                               g_memory_saver_model = false;''',
        '''static int                                g_active_context_size = DEFAULT_CONTEXT_SIZE;
static int                                g_active_batch_size = BATCH_SIZE;
static bool                               g_large_model = false;
static bool                               g_low_memory_mode = false;''',
        "adaptive memory globals",
    )

    old_load = '''extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_load(JNIEnv *env, jobject, jstring jmodel_path) {
    llama_model_params model_params = llama_model_default_params();

    clear_native_log();

    const auto *model_path = env->GetStringUTFChars(jmodel_path, 0);
    const std::string model_path_value(model_path);
    g_memory_saver_model = model_path_value.find("9B") != std::string::npos ||
                           model_path_value.find("9b") != std::string::npos;
    g_active_batch_size = g_memory_saver_model ? 256 : BATCH_SIZE;

    // Furina is CPU-only. Keep optimized ARM/KleidiAI weight buffers enabled;
    // for 4B. The 9B profile disables additional packed weight buffers because
    // their speed benefit is not worth pushing a 12 GB phone into LMKD pressure.
    model_params.n_gpu_layers = 0;
    model_params.use_extra_bufts = !g_memory_saver_model;

    LOGd("%s: Loading model from: \\n%s\\n", __func__, model_path);
    LOGi("%s: Runtime profile: %s", __func__, g_memory_saver_model ? "9B memory-saver" : "4B performance");

    // App-specific external storage is FUSE-backed on many Android devices. Retry
    // without mmap when a valid GGUF cannot be mapped from that filesystem.
    model_params.load_mode = LLAMA_LOAD_MODE_MMAP;
    auto *model = llama_model_load_from_file(model_path, model_params);
    if (!model) {
        LOGw("%s: mmap load failed; retrying without mmap", __func__);
        model_params.load_mode = LLAMA_LOAD_MODE_NONE;
        model = llama_model_load_from_file(model_path, model_params);
    }
    env->ReleaseStringUTFChars(jmodel_path, model_path);
    if (!model) {
        return 1;
    }
    g_model = model;
    return 0;
}'''
    new_load = '''extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_load(
        JNIEnv *env, jobject, jstring jmodel_path, jboolean jlow_memory_mode) {
    llama_model_params model_params = llama_model_default_params();

    clear_native_log();

    const auto *model_path = env->GetStringUTFChars(jmodel_path, 0);
    const std::string model_path_value(model_path);
    g_large_model = model_path_value.find("9B") != std::string::npos ||
                    model_path_value.find("9b") != std::string::npos;
    g_low_memory_mode = (jlow_memory_mode == JNI_TRUE) || g_large_model;
    g_active_batch_size = g_low_memory_mode ? 256 : BATCH_SIZE;

    // Extra CPU buffer types can repack weights for faster ARM kernels, but the
    // repacked representation raises peak resident memory during model load.
    // Keep the optimization only when Android reports enough free RAM.
    model_params.n_gpu_layers = 0;
    model_params.use_extra_bufts = !g_low_memory_mode;
    model_params.no_host = false;

    const char *profile = g_large_model ? "large-model low-peak" :
                          (g_low_memory_mode ? "4B low-peak" : "4B performance");
    LOGd("%s: Loading model from: \\n%s\\n", __func__, model_path);
    LOGi("%s: Runtime profile: %s; extra_bufts=%d; batch=%d",
         __func__, profile, model_params.use_extra_bufts ? 1 : 0, g_active_batch_size);

    // Multi-GB Android models must stay mmap-backed. Retrying the same 2.7 GB
    // GGUF with LLAMA_LOAD_MODE_NONE after mmap failure can duplicate file data
    // in process memory and let LMKD kill the app before Java receives an error.
    if (!llama_supports_mmap()) {
        LOGe("%s: mmap is unavailable in this Android runtime; refusing unsafe full-buffer load", __func__);
        env->ReleaseStringUTFChars(jmodel_path, model_path);
        return 2;
    }
    model_params.load_mode = LLAMA_LOAD_MODE_MMAP;
    auto *model = llama_model_load_from_file(model_path, model_params);
    env->ReleaseStringUTFChars(jmodel_path, model_path);
    if (!model) {
        LOGe("%s: mmap model load failed; no non-mmap retry for multi-GB Android GGUF", __func__);
        return 1;
    }
    g_model = model;
    return 0;
}'''
    text = replace_once(text, old_load, new_load, "adaptive mmap model load")

    text = replace_once(
        text,
        '''    ctx_params.n_ctx = n_ctx;
    ctx_params.n_batch = g_active_batch_size;
    ctx_params.n_ubatch = g_memory_saver_model ? 128 : UBATCH_SIZE;
    if (g_memory_saver_model) {
        // Q8 KV halves cache memory relative to F16 with negligible quality
        // impact for chat, and is supported by this CPU-only backend.
        ctx_params.type_k = GGML_TYPE_Q8_0;
        ctx_params.type_v = GGML_TYPE_Q8_0;
    }''',
        '''    ctx_params.n_ctx = n_ctx;
    ctx_params.n_batch = g_active_batch_size;
    // Physical micro-batch size changes scratch memory and prompt throughput,
    // not model quality. Use the smaller shape only under RAM pressure.
    ctx_params.n_ubatch = g_low_memory_mode ? 128 : UBATCH_SIZE;
    if (g_large_model) {
        // Keep KV quantization restricted to the genuinely large-model profile.
        // The 4B low-peak profile retains F16 KV and the full 4K target context.
        ctx_params.type_k = GGML_TYPE_Q8_0;
        ctx_params.type_v = GGML_TYPE_Q8_0;
    }''',
        "adaptive context buffers",
    )

    text = replace_once(
        text,
        '''Java_com_arm_aichat_internal_InferenceEngineImpl_prepare(JNIEnv * /*env*/, jobject /*unused*/) {
    const int target_context = g_memory_saver_model ? DEFAULT_CONTEXT_SIZE / 2 : DEFAULT_CONTEXT_SIZE;
    auto *context = init_context(g_model, target_context);
    if (!context) {
        const int fallback_context = g_memory_saver_model ? DEFAULT_CONTEXT_SIZE / 4 : DEFAULT_CONTEXT_SIZE / 2;
        LOGw("%s: Context allocation failed; retrying with %d tokens", __func__, fallback_context);
        context = init_context(g_model, fallback_context);
    }
    if (!context) { return 1; }''',
        '''Java_com_arm_aichat_internal_InferenceEngineImpl_prepare(JNIEnv * /*env*/, jobject /*unused*/) {
    // Low-memory mode for the 4B model changes scratch/repack memory only. Keep
    // the same 4096-token target so response quality and continuity are intact.
    const int context_targets[] = {
        g_large_model ? DEFAULT_CONTEXT_SIZE / 2 : DEFAULT_CONTEXT_SIZE,
        g_large_model ? (DEFAULT_CONTEXT_SIZE * 3) / 8 : (DEFAULT_CONTEXT_SIZE * 3) / 4,
        g_large_model ? DEFAULT_CONTEXT_SIZE / 4 : DEFAULT_CONTEXT_SIZE / 2,
    };
    llama_context *context = nullptr;
    for (const int target_context : context_targets) {
        if (context) break;
        LOGi("%s: Trying context allocation with %d tokens", __func__, target_context);
        context = init_context(g_model, target_context);
        if (!context) {
            LOGw("%s: Context allocation failed at %d tokens", __func__, target_context);
        }
    }
    if (!context) { return 1; }''',
        "progressive context allocation",
    )

    old_sampler = '''static common_sampler *new_sampler(float temp, int reasoning_budget = 0) {
    common_params_sampling sparams;
    sparams.temp = temp;
    const llama_vocab *vocab = llama_model_get_vocab(g_model);
    sparams.reasoning_budget_tokens = std::max(0, reasoning_budget);
    sparams.reasoning_budget_start = common_tokenize(vocab, "<think>", false, true);
    auto reasoning_end = common_tokenize(vocab, "</think>", false, true);
    sparams.reasoning_budget_end = { reasoning_end };
    sparams.reasoning_budget_forced = reasoning_end;
    return common_sampler_init(g_model, sparams);
}'''
    new_sampler = '''static common_sampler *new_sampler(float temp, int reasoning_budget = 0) {
    (void) reasoning_budget;
    common_params_sampling sparams;
    // Qwen3.5 Deckard general non-thinking profile. Presence penalty reduces
    // repetitive companion openings without introducing a hard response template.
    sparams.temp = temp;
    sparams.top_p = 0.80f;
    sparams.top_k = 20;
    sparams.min_p = 0.0f;
    sparams.penalty_present = 1.5f;
    sparams.penalty_repeat = 1.0f;
    // Qwen3.5 does not use Qwen3's /think or /nothink soft switch. Thinking is
    // controlled by the chat template below instead of by prompt suffixes.
    sparams.reasoning_budget_tokens = -1;
    return common_sampler_init(g_model, sparams);
}'''
    text = replace_once(text, old_sampler, new_sampler, "sampler policy")

    old_formatter = '''static std::string chat_add_and_format(const std::string &role, const std::string &content) {
    common_chat_msg new_msg;
    new_msg.role = role;
    new_msg.content = content;
    auto formatted = common_chat_format_single(
            g_chat_templates.get(), chat_msgs, new_msg, role == ROLE_USER, /* use_jinja */ false);
    chat_msgs.push_back(new_msg);
    LOGi("%s: Formatted and added %s message: \\n%s\\n", __func__, role.c_str(), formatted.c_str());
    return formatted;
}'''
    new_formatter = '''static std::string chat_add_and_format(const std::string &role, const std::string &content) {
    common_chat_msg new_msg;
    new_msg.role = role;
    new_msg.content = content;

    // Apply the model's own Jinja template with Qwen3.5 non-thinking enabled.
    // We compute only the incremental suffix so previously decoded KV tokens are
    // not duplicated on every turn.
    common_chat_templates_inputs inputs;
    inputs.use_jinja = true;
    inputs.enable_thinking = false;
    inputs.reasoning_format = COMMON_REASONING_FORMAT_NONE;
    inputs.chat_template_kwargs["enable_thinking"] = "false";

    std::string formatted_past;
    if (!chat_msgs.empty()) {
        inputs.messages = chat_msgs;
        inputs.add_generation_prompt = false;
        formatted_past = common_chat_templates_apply(g_chat_templates.get(), inputs).prompt;
    }

    inputs.messages.push_back(new_msg);
    inputs.add_generation_prompt = role == ROLE_USER;
    const std::string formatted_full = common_chat_templates_apply(g_chat_templates.get(), inputs).prompt;

    std::string formatted;
    if (formatted_full.size() >= formatted_past.size() &&
        formatted_full.compare(0, formatted_past.size(), formatted_past) == 0) {
        formatted = formatted_full.substr(formatted_past.size());
    } else {
        // Pinned templates should be prefix-stable. Preserve correctness if a future
        // template is not by falling back to llama.cpp's incremental formatter.
        LOGw("%s: chat template was not prefix-stable; using compatibility formatter", __func__);
        formatted = common_chat_format_single(
                g_chat_templates.get(), chat_msgs, new_msg, role == ROLE_USER, /* use_jinja */ true);
    }

    chat_msgs.push_back(new_msg);
    LOGi("%s: Formatted and added %s message: \\n%s\\n", __func__, role.c_str(), formatted.c_str());
    return formatted;
}'''
    text = replace_once(text, old_formatter, new_formatter, "chat template policy")

    old_tokenize = '''common_tokenize(g_context, formatted_system_prompt,
                                               has_chat_template, has_chat_template)'''
    new_tokenize = '''common_tokenize(g_context, formatted_system_prompt,
                                               false, has_chat_template)'''
    text = replace_once(text, old_tokenize, new_tokenize, "system tokenization")

    old_user_tokenize = '''common_tokenize(g_context, formatted_user_prompt, has_chat_template, has_chat_template)'''
    new_user_tokenize = '''common_tokenize(g_context, formatted_user_prompt, false, has_chat_template)'''
    text = replace_once(text, old_user_tokenize, new_user_tokenize, "user tokenization")

    old_user_reset = '''Java_com_arm_aichat_internal_InferenceEngineImpl_processUserPrompt(
        JNIEnv *env,
        jobject /*unused*/,
        jstring juser_prompt,
        jint n_predict
) {
    // Reset short-term states
    reset_short_term_states();'''
    new_user_reset = '''Java_com_arm_aichat_internal_InferenceEngineImpl_processUserPrompt(
        JNIEnv *env,
        jobject /*unused*/,
        jstring juser_prompt,
        jint n_predict
) {
    // Reset short-term states and sampler penalties per reply. KV/chat history stays.
    reset_short_term_states();
    if (g_sampler) common_sampler_reset(g_sampler);'''
    text = replace_once(text, old_user_reset, new_user_reset, "per-turn sampler reset")

    text = replace_once(
        text,
        '''        const int skipped_tokens = user_prompt_size - max_batch_size;
        user_tokens.resize(max_batch_size);
        LOGw("%s: User prompt too long! Skipped %d tokens!", __func__, skipped_tokens);''',
        '''        const int skipped_tokens = user_prompt_size - max_batch_size;
        // Preserve the newest part of an oversized turn. The actual user message is
        // deliberately placed at the end after private retrieval/context.
        user_tokens.erase(user_tokens.begin(), user_tokens.begin() + skipped_tokens);
        LOGw("%s: User prompt too long! Dropped %d oldest context tokens", __func__, skipped_tokens);''',
        "newest-user overflow preservation",
    )

    text = replace_once(
        text,
        '''    g_active_context_size = DEFAULT_CONTEXT_SIZE;
    g_active_batch_size = BATCH_SIZE;
    g_memory_saver_model = false;''',
        '''    g_active_context_size = DEFAULT_CONTEXT_SIZE;
    g_active_batch_size = BATCH_SIZE;
    g_large_model = false;
    g_low_memory_mode = false;''',
        "adaptive memory reset",
    )

    path.write_text(text, encoding="utf-8")


def patch_kotlin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''import android.content.Context
import android.util.Log''',
        '''import android.app.ActivityManager
import android.content.Context
import android.util.Log''',
        "ActivityManager import",
    )

    text = replace_once(
        text,
        '''internal class InferenceEngineImpl private constructor(
    private val nativeLibDir: String
) : InferenceEngine {''',
        '''internal class InferenceEngineImpl private constructor(
    private val appContext: Context,
    private val nativeLibDir: String
) : InferenceEngine {''',
        "application context ownership",
    )

    text = replace_once(
        text,
        '''                    InferenceEngineImpl(nativeLibDir).also { instance = it }''',
        '''                    InferenceEngineImpl(context.applicationContext, nativeLibDir).also { instance = it }''',
        "inference engine construction",
    )

    text = replace_once(
        text,
        '''    private external fun load(modelPath: String): Int''',
        '''    private external fun load(modelPath: String, lowMemoryMode: Boolean): Int''',
        "adaptive native load signature",
    )

    marker = '''    /**
     * Load the LLM
     */
    override suspend fun loadModel(pathToModel: String) ='''
    helper = '''    /**
     * Repacked CPU weights can materially improve throughput but also raise peak RSS.
     * Keep that optimization only when Android reports enough free memory for roughly
     * two model-sized resident representations plus a 2 GiB UI/context/system margin.
     * This changes memory layout and batch scratch only; model weights/context quality stay.
     */
    private fun shouldUseLowMemoryMode(modelBytes: Long): Boolean {
        val manager = appContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = ActivityManager.MemoryInfo().also(manager::getMemoryInfo)
        val gib = 1024L * 1024L * 1024L
        val performanceFloor = (modelBytes * 2L) + (2L * gib)
        val lowPeak = info.lowMemory || info.availMem < performanceFloor
        Log.i(
            TAG,
            "RAM load profile: ${if (lowPeak) "low-peak" else "performance"}; " +
                "model=${modelBytes / (1024 * 1024)}MiB, " +
                "avail=${info.availMem / (1024 * 1024)}MiB, " +
                "total=${info.totalMem / (1024 * 1024)}MiB, threshold=${performanceFloor / (1024 * 1024)}MiB"
        )
        return lowPeak
    }

    /**
     * Load the LLM
     */
    override suspend fun loadModel(pathToModel: String) ='''
    text = replace_once(text, marker, helper, "adaptive RAM profile helper")

    text = replace_once(
        text,
        '''                Log.i(TAG, "Checking access to model file... \\n$pathToModel")
                File(pathToModel).let {''',
        '''                Log.i(TAG, "Checking access to model file... \\n$pathToModel")
                val modelFile = File(pathToModel)
                modelFile.let {''',
        "retain validated model file",
    )

    text = replace_once(
        text,
        '''                _readyForSystemPrompt = false
                _state.value = InferenceEngine.State.LoadingModel
                load(pathToModel).let {''',
        '''                _readyForSystemPrompt = false
                _state.value = InferenceEngine.State.LoadingModel
                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                load(pathToModel, lowMemoryMode).let {''',
        "adaptive model load call",
    )

    old = '''            val reasoningBudget = reasoningBudgetFor(message)
            configureReasoningBudget(reasoningBudget)
            val controlledMessage = when {
                message.contains("/think", ignoreCase = true) ||
                    message.contains("/no_think", ignoreCase = true) -> message
                reasoningBudget > 0 -> "$message\\n/think"
                else -> "$message\\n/no_think"
            }

            processUserPrompt(controlledMessage, predictLength).let { result ->'''
    new = '''            // Qwen3.5 thinking mode is controlled by the GGUF chat template in the
            // native runtime. Never mutate the user's message with /think or /no_think.
            processUserPrompt(message, predictLength).let { result ->'''
    text = replace_once(text, old, new, "Qwen3.5 prompt mutation")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply-companion-runtime-policy.py <ai_chat.cpp> <InferenceEngineImpl.kt>")
    cpp = Path(sys.argv[1])
    kotlin = Path(sys.argv[2])
    patch_cpp(cpp)
    patch_kotlin(kotlin)
    print("Applied Furina companion runtime policy: adaptive low-peak mmap + layered Qwen3.5 chat")


if __name__ == "__main__":
    main()
