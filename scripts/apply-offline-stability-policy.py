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

    # For a multi-GB mobile model, predictable peak RSS is more valuable than the
    # optional CPU weight-repacking speedup. None of these settings alter weights,
    # sampler, KV precision for 4B, or the 4096-token target context.
    text = replace_once(
        text,
        "g_active_batch_size = g_low_memory_mode ? 256 : BATCH_SIZE;",
        "g_active_batch_size = g_low_memory_mode ? 128 : 256;",
        "low-peak batch",
    )
    text = replace_once(
        text,
        "model_params.use_extra_bufts = !g_low_memory_mode;",
        "model_params.use_extra_bufts = false;",
        "disable extra packed-weight buffers",
    )
    text = replace_once(
        text,
        "ctx_params.n_ubatch = g_low_memory_mode ? 128 : UBATCH_SIZE;",
        "ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;",
        "low-peak micro-batch",
    )

    # The Qwen3.5 template intentionally raises "No user query found in messages"
    # when rendered with a system-only history. Furina prewarms by decoding its
    # identity before the first user turn, so calling the full Jinja renderer here
    # crosses JNI with an uncaught C++ exception and Android reports SIGABRT (6).
    # Furina's offline path is text-only, therefore use the exact text markers from
    # Qwen3.5's template directly. This preserves enable_thinking=false semantics
    # while removing the unsafe system-only Jinja state and its parser overhead.
    risky_formatter = '''static std::string chat_add_and_format(const std::string &role, const std::string &content) {
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
    safe_formatter = '''static std::string chat_add_and_format(const std::string &role, const std::string &content) {
    common_chat_msg new_msg;
    new_msg.role = role;
    new_msg.content = content;

    std::string formatted;
    if (role == ROLE_SYSTEM) {
        // Exact text-only Qwen3.5 system branch.
        formatted = std::string("<|im_start|>system\\n") + content + "<|im_end|>\\n";
    } else if (role == ROLE_USER) {
        // A sampled EOG already closes the previous assistant turn; its template
        // has a trailing newline that is not part of the EOG token, so add it here.
        const bool follows_assistant = !chat_msgs.empty() && chat_msgs.back().role == ROLE_ASSISTANT;
        if (follows_assistant) formatted += "\\n";
        formatted += std::string("<|im_start|>user\\n") + content +
                     "<|im_end|>\\n<|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n";
    } else if (role != ROLE_ASSISTANT) {
        LOGe("%s: Unsupported local chat role: %s", __func__, role.c_str());
    }

    // Assistant text is already present in KV because it was generated token by
    // token. We only retain its semantic message here for turn bookkeeping.
    chat_msgs.push_back(new_msg);
    LOGi("%s: Added %s message using deterministic Qwen3.5 text template", __func__, role.c_str());
    return formatted;
}'''
    text = replace_once(text, risky_formatter, safe_formatter, "system-safe Qwen3.5 formatter")

    old_system_format = '''    // Format system prompt if applicable
    const bool has_chat_template = common_chat_templates_was_explicit(g_chat_templates.get());
    if (has_chat_template) {
        formatted_system_prompt = chat_add_and_format(ROLE_SYSTEM, system_prompt);
    }'''
    new_system_format = '''    // Furina currently has one local model: Qwen3.5 Deckard. Always apply its
    // deterministic text markers; never invoke the full Jinja template system-only.
    formatted_system_prompt = chat_add_and_format(ROLE_SYSTEM, system_prompt);'''
    text = replace_once(text, old_system_format, new_system_format, "system prompt formatter")

    old_user_format = '''    // Format user prompt if applicable
    const bool has_chat_template = common_chat_templates_was_explicit(g_chat_templates.get());
    if (has_chat_template) {
        formatted_user_prompt = chat_add_and_format(ROLE_USER, user_prompt);
    }'''
    new_user_format = '''    // Use the exact Qwen3.5 text-only user + non-thinking generation markers.
    formatted_user_prompt = chat_add_and_format(ROLE_USER, user_prompt);'''
    text = replace_once(text, old_user_format, new_user_format, "user prompt formatter")

    text = replace_once(
        text,
        '''common_tokenize(g_context, formatted_system_prompt,
                                               false, has_chat_template)''',
        '''common_tokenize(g_context, formatted_system_prompt,
                                               false, true)''',
        "system special-token parsing",
    )
    text = replace_once(
        text,
        '''common_tokenize(g_context, formatted_user_prompt, false, has_chat_template)''',
        '''common_tokenize(g_context, formatted_user_prompt, false, true)''',
        "user special-token parsing",
    )

    path.write_text(text, encoding="utf-8")


def patch_kotlin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''import android.app.ActivityManager
import android.content.Context
import android.util.Log''',
        '''import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.util.Log''',
        "Build import",
    )

    marker = '''    /**
     * Repacked CPU weights can materially improve throughput but also raise peak RSS.
     * Keep that optimization only when Android reports enough free memory for roughly
     * two model-sized resident representations plus a 2 GiB UI/context/system margin.
     * This changes memory layout and batch scratch only; model weights/context quality stay.
     */
    private fun shouldUseLowMemoryMode(modelBytes: Long): Boolean {'''
    replacement = '''    /** Persist the exact native-load stage so Android can report it after a hard process death. */
    private fun markProcessStage(stage: String) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return
        runCatching {
            val manager = appContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            manager.setProcessStateSummary(("furina:" + stage).take(120).toByteArray(Charsets.UTF_8))
        }
    }

    /**
     * Repacked CPU weights can materially improve throughput but also raise peak RSS.
     * Furina's local GGUF is multi-gigabyte, so always use the deterministic low-peak
     * profile for it. This changes scratch/repack layout only, not model/context quality.
     */
    private fun shouldUseLowMemoryMode(modelBytes: Long): Boolean {'''
    text = replace_once(text, marker, replacement, "native stage marker helper")

    text = replace_once(
        text,
        '''        val performanceFloor = (modelBytes * 2L) + (2L * gib)
        val lowPeak = info.lowMemory || info.availMem < performanceFloor''',
        '''        val performanceFloor = (modelBytes * 2L) + (2L * gib)
        val multiGigabyteModel = modelBytes >= 2L * gib
        val lowPeak = multiGigabyteModel || info.lowMemory || info.availMem < performanceFloor''',
        "force multi-gigabyte low-peak profile",
    )

    text = replace_once(
        text,
        '''                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                load(pathToModel, lowMemoryMode).let {
                    if (it != 0) {''',
        '''                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                markProcessStage("native-weights-load")
                load(pathToModel, lowMemoryMode).let {
                    if (it != 0) {''',
        "weights-load stage marker",
    )

    text = replace_once(
        text,
        '''                }
                prepare().let {
                    if (it != 0) throw IOException("Failed to prepare resources")
                }
                Log.i(TAG, "Model loaded!")''',
        '''                }
                markProcessStage("native-context-prepare")
                prepare().let {
                    if (it != 0) throw IOException("Failed to prepare resources")
                }
                markProcessStage("native-model-ready")
                Log.i(TAG, "Model loaded!")''',
        "context stage marker",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply-offline-stability-policy.py <ai_chat.cpp> <InferenceEngineImpl.kt>")
    cpp = Path(sys.argv[1])
    kotlin = Path(sys.argv[2])
    patch_cpp(cpp)
    patch_kotlin(kotlin)
    print("Applied Furina Android offline stability policy: private mmap + low-peak load + system-safe Qwen3.5 prompt")


if __name__ == "__main__":
    main()
