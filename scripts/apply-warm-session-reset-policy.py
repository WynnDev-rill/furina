#!/usr/bin/env python3
"""Patch the pinned llama.android binding with a real conversation reset primitive.

The primitive keeps the already-prefilled SYSTEM KV prefix, removes only chat tokens after
that boundary, resets sampler/generation state, and exposes the operation through
InferenceEngine. Exact replacements intentionally fail closed if the pinned upstream layout
changes.
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
        "    suspend fun resetConversationKeepingSystemPrompt()\n\n",
        "InferenceEngine reset API",
    )

    replace_once(
        impl,
        "    private external fun processSystemPrompt(systemPrompt: String): Int\n\n",
        "    private external fun processSystemPrompt(systemPrompt: String): Int\n\n"
        "    @FastNative\n"
        "    private external fun resetConversationKeepingSystemPromptNative(): Int\n\n",
        "InferenceEngineImpl native reset declaration",
    )

    user_prompt_marker = "    /**\n     * Send plain text user prompt to LLM, which starts generating tokens in a [Flow]\n     */\n"
    reset_impl = """    /**
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

"""
    replace_once(impl, user_prompt_marker, reset_impl + user_prompt_marker, "InferenceEngineImpl reset implementation")

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
