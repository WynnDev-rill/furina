#!/usr/bin/env python3
"""Patch the pinned llama.android binding with warm-session SYSTEM-prefix primitives.

The primitives keep the already-prefilled identity SYSTEM KV prefix, can remove mutable chat
state after that boundary, and can append session continuity as a second SYSTEM/background
message without advancing the preserved boundary. Exact replacements fail closed if pinned
upstream layout changes.
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


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: apply-warm-session-reset-policy.py <ai_chat.cpp> <InferenceEngine.kt> <InferenceEngineImpl.kt>")

    cpp = Path(sys.argv[1])
    interface = Path(sys.argv[2])
    impl = Path(sys.argv[3])

    replace_once(
        interface,
        "    suspend fun setSystemPrompt(systemPrompt: String)\n\n",
        "    suspend fun setSystemPrompt(systemPrompt: String)\n\n"
        "    /** Clear USER/ASSISTANT conversation state while retaining the prefetched SYSTEM prefix. */\n"
        "    suspend fun resetConversationKeepingSystemPrompt()\n\n"
        "    /** Append mutable session continuity as SYSTEM/background after the preserved prefix. */\n"
        "    suspend fun appendSystemContext(systemContext: String)\n\n",
        "InferenceEngine warm-session APIs",
    )

    replace_once(
        impl,
        "    private external fun processSystemPrompt(systemPrompt: String): Int\n\n",
        "    private external fun processSystemPrompt(systemPrompt: String): Int\n\n"
        "    @FastNative\n"
        "    private external fun resetConversationKeepingSystemPromptNative(): Int\n\n"
        "    @FastNative\n"
        "    private external fun appendSystemContextNative(systemContext: String): Int\n\n",
        "InferenceEngineImpl warm-session native declarations",
    )

    user_prompt_marker = "    /**\n     * Send plain text user prompt to LLM, which starts generating tokens in a [Flow]\n     */\n"
    warm_impl = """    /**
     * Drop mutable USER/ASSISTANT state without paying the stable SYSTEM prefill cost again.
     * Native code fails closed unless a valid prefetched system boundary exists.
     */
    override suspend fun resetConversationKeepingSystemPrompt() =
        withContext(llamaDispatcher) {
            check(_state.value is InferenceEngine.State.ModelReady) {
                "Cannot reset conversation in ${_state.value.javaClass.simpleName}!"
            }
            _cancelGeneration = false
            resetConversationKeepingSystemPromptNative().let { result ->
                if (result != 0) {
                    throw IOException("Failed to preserve system prefix while resetting conversation: $result")
                }
            }
            _state.value = InferenceEngine.State.ModelReady
        }

    /** Append session-scoped continuity as a SYSTEM message without moving the stable boundary. */
    override suspend fun appendSystemContext(systemContext: String) =
        withContext(llamaDispatcher) {
            require(systemContext.isNotBlank()) { "Cannot append empty system context!" }
            check(_state.value is InferenceEngine.State.ModelReady) {
                "Cannot append system context in ${_state.value.javaClass.simpleName}!"
            }
            _state.value = InferenceEngine.State.ProcessingSystemPrompt
            appendSystemContextNative(systemContext).let { result ->
                _state.value = InferenceEngine.State.ModelReady
                if (result != 0) {
                    throw IOException("Failed to append session system context: $result")
                }
            }
        }

"""
    replace_once(impl, user_prompt_marker, warm_impl + user_prompt_marker, "InferenceEngineImpl warm-session implementation")

    short_reset = """static void reset_short_term_states() {
    generated_tokens_remaining = 0;
    cached_token_chars.clear();
    assistant_ss.str("");
}
"""
    native_reset = short_reset + """

extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_resetConversationKeepingSystemPromptNative(
        JNIEnv * /*env*/, jobject /*unused*/) {
    if (!g_context || system_prompt_position <= 0 || current_position < system_prompt_position) {
        LOGw("%s: no valid prefetched system prefix", __func__);
        return 1;
    }

    if (!chat_msgs.empty()) {
        const common_chat_msg system_msg = chat_msgs.front();
        chat_msgs.clear();
        if (system_msg.role == ROLE_SYSTEM) {
            chat_msgs.push_back(system_msg);
        }
    }

    if (current_position > system_prompt_position) {
        llama_memory_seq_rm(
                llama_get_memory(g_context), 0, system_prompt_position, current_position);
    }
    current_position = system_prompt_position;
    reset_short_term_states();
    if (g_sampler) common_sampler_reset(g_sampler);
    LOGi("%s: conversation reset to preserved system prefix at position %d", __func__, system_prompt_position);
    return 0;
}
"""
    replace_once(cpp, short_reset, native_reset, "native system-prefix reset")

    user_native_marker = """extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_processUserPrompt(
"""
    append_native = """extern "C"
JNIEXPORT jint JNICALL
Java_com_arm_aichat_internal_InferenceEngineImpl_appendSystemContextNative(
        JNIEnv *env, jobject /*unused*/, jstring jsystem_context) {
    if (!g_context || system_prompt_position <= 0 || current_position < system_prompt_position) {
        LOGw("%s: no valid identity-only system prefix", __func__);
        return 1;
    }

    const auto *system_context = env->GetStringUTFChars(jsystem_context, nullptr);
    std::string formatted_system_context(system_context);
    const bool has_chat_template = common_chat_templates_was_explicit(g_chat_templates.get());
    if (has_chat_template) {
        formatted_system_context = chat_add_and_format(ROLE_SYSTEM, system_context);
    }
    env->ReleaseStringUTFChars(jsystem_context, system_context);

    const auto context_tokens = common_tokenize(
            g_context, formatted_system_context, has_chat_template, has_chat_template);
    const int hard_limit = g_active_context_size - OVERFLOW_HEADROOM;
    if (context_tokens.empty() || current_position + (int) context_tokens.size() >= hard_limit) {
        if (has_chat_template && !chat_msgs.empty()) chat_msgs.pop_back();
        LOGw("%s: session SYSTEM context cannot fit without shifting stable prefix", __func__);
        return 2;
    }

    const llama_pos preserved_boundary = system_prompt_position;
    if (decode_tokens_in_batches(g_context, g_batch, context_tokens, current_position)) {
        if (has_chat_template && !chat_msgs.empty()) chat_msgs.pop_back();
        llama_memory_seq_rm(llama_get_memory(g_context), 0, preserved_boundary, current_position);
        current_position = preserved_boundary;
        LOGe("%s: failed to decode session SYSTEM context", __func__);
        return 3;
    }
    if (system_prompt_position != preserved_boundary) {
        LOGe("%s: stable system boundary moved unexpectedly", __func__);
        return 4;
    }
    reset_short_term_states();
    if (g_sampler) common_sampler_reset(g_sampler);
    return 0;
}

"""
    replace_once(cpp, user_native_marker, append_native + user_native_marker, "native SYSTEM background append")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
