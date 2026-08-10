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

    # The Jinja-rendered prompt already contains its special tokens. Parse them, but
    # do not ask tokenization to add another BOS/EOS layer.
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

    path.write_text(text, encoding="utf-8")


def patch_kotlin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
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
    print("Applied Furina companion runtime policy: layered chat template + Qwen3.5 non-thinking sampler")


if __name__ == "__main__":
    main()
