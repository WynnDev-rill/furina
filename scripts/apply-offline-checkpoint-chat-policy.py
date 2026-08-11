#!/usr/bin/env python3
"""Extend Furina v4 llama.cpp checkpoints with exact native chat framing.

KV alone is not sufficient for an incremental chat template: llama.cpp also needs the exact
role/content history used to format the next suffix. Persist both atomically so restoring a
persona/session checkpoint cannot diverge from the KV tokens already in memory.
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
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-offline-checkpoint-chat-policy.py <ai_chat.cpp>")
    path = Path(sys.argv[1])

    replace_once(
        path,
        '''constexpr uint32_t FURINA_KV_MAGIC = 0x46554B56;
constexpr uint32_t FURINA_KV_VERSION = 4;
struct furina_checkpoint_header {
    uint32_t magic;
    uint32_t version;
    int32_t system_position;
    int32_t current_position;
    uint32_t last_role;
    uint64_t state_size;
};''',
        '''constexpr uint32_t FURINA_KV_MAGIC = 0x46554B56;
constexpr uint32_t FURINA_KV_VERSION = 5;
constexpr uint32_t FURINA_CHECKPOINT_MAX_MESSAGES = 512;
constexpr uint64_t FURINA_CHECKPOINT_MAX_CHAT_BYTES = 2ULL * 1024ULL * 1024ULL;
struct furina_checkpoint_header {
    uint32_t magic;
    uint32_t version;
    int32_t system_position;
    int32_t current_position;
    uint32_t last_role;
    uint64_t state_size;
    uint32_t chat_count;
    uint64_t chat_bytes;
};''',
        "checkpoint v5 header",
    )

    old_save = '''    const char *chars = env->GetStringUTFChars(jpath, nullptr);
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
    out.flush();'''
    new_save = '''    if (chat_msgs.empty() || chat_msgs.front().role != ROLE_SYSTEM ||
        chat_msgs.size() > FURINA_CHECKPOINT_MAX_MESSAGES) return 4;
    uint64_t chat_bytes = 0;
    for (const auto &msg : chat_msgs) {
        if (msg.role.size() > UINT32_MAX || msg.content.size() > UINT32_MAX) return 4;
        chat_bytes += sizeof(uint32_t) * 2ULL + msg.role.size() + msg.content.size();
        if (chat_bytes > FURINA_CHECKPOINT_MAX_CHAT_BYTES) return 4;
    }

    const char *chars = env->GetStringUTFChars(jpath, nullptr);
    const std::string path(chars);
    env->ReleaseStringUTFChars(jpath, chars);
    const std::string tmp = path + ".tmp";
    furina_checkpoint_header header {
        FURINA_KV_MAGIC, FURINA_KV_VERSION,
        (int32_t) system_prompt_position, (int32_t) current_position,
        checkpoint_last_role(), (uint64_t) written,
        (uint32_t) chat_msgs.size(), chat_bytes,
    };

    std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
    if (!out) return 5;
    out.write(reinterpret_cast<const char *>(&header), sizeof(header));
    out.write(reinterpret_cast<const char *>(state.data()), (std::streamsize) written);
    for (const auto &msg : chat_msgs) {
        const uint32_t role_size = (uint32_t) msg.role.size();
        const uint32_t content_size = (uint32_t) msg.content.size();
        out.write(reinterpret_cast<const char *>(&role_size), sizeof(role_size));
        out.write(reinterpret_cast<const char *>(&content_size), sizeof(content_size));
        out.write(msg.role.data(), (std::streamsize) role_size);
        out.write(msg.content.data(), (std::streamsize) content_size);
    }
    out.flush();'''
    replace_once(path, old_save, new_save, "checkpoint exact chat save")

    replace_once(
        path,
        '''        std::remove(tmp.c_str());
        return 5;
    }''',
        '''        std::remove(tmp.c_str());
        return 6;
    }''',
        "checkpoint save error numbering",
    )

    old_restore = '''    furina_checkpoint_header header {};
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
    reset_short_term_states();'''
    new_restore = '''    furina_checkpoint_header header {};
    in.read(reinterpret_cast<char *>(&header), sizeof(header));
    if (!in || header.magic != FURINA_KV_MAGIC || header.version != FURINA_KV_VERSION ||
        header.system_position <= 0 || header.current_position < header.system_position ||
        header.current_position >= g_active_context_size || header.state_size == 0 ||
        header.chat_count == 0 || header.chat_count > FURINA_CHECKPOINT_MAX_MESSAGES ||
        header.chat_bytes > FURINA_CHECKPOINT_MAX_CHAT_BYTES) return 3;

    std::vector<uint8_t> state((size_t) header.state_size);
    in.read(reinterpret_cast<char *>(state.data()), (std::streamsize) state.size());
    if (!in) return 4;

    std::vector<common_chat_msg> restored_chat;
    restored_chat.reserve(header.chat_count);
    uint64_t consumed_chat_bytes = 0;
    for (uint32_t i = 0; i < header.chat_count; ++i) {
        uint32_t role_size = 0;
        uint32_t content_size = 0;
        in.read(reinterpret_cast<char *>(&role_size), sizeof(role_size));
        in.read(reinterpret_cast<char *>(&content_size), sizeof(content_size));
        consumed_chat_bytes += sizeof(uint32_t) * 2ULL + role_size + content_size;
        if (!in || role_size == 0 || role_size > 32 ||
            consumed_chat_bytes > header.chat_bytes ||
            consumed_chat_bytes > FURINA_CHECKPOINT_MAX_CHAT_BYTES) return 5;
        std::string role(role_size, '\\0');
        std::string content(content_size, '\\0');
        in.read(role.data(), (std::streamsize) role_size);
        in.read(content.data(), (std::streamsize) content_size);
        if (!in) return 5;
        if (role != ROLE_SYSTEM && role != ROLE_USER && role != ROLE_ASSISTANT) return 5;
        restored_chat.push_back(common_chat_msg{role, content});
    }
    if (consumed_chat_bytes != header.chat_bytes || restored_chat.empty() ||
        restored_chat.front().role != ROLE_SYSTEM) return 5;

    llama_memory_clear(llama_get_memory(g_context), false);
    const size_t restored = llama_state_seq_set_data(g_context, state.data(), state.size(), 0);
    if (restored == 0) {
        llama_memory_clear(llama_get_memory(g_context), false);
        return 6;
    }

    system_prompt_position = (llama_pos) header.system_position;
    current_position = (llama_pos) header.current_position;
    chat_msgs = std::move(restored_chat);
    reset_short_term_states();'''
    replace_once(path, old_restore, new_restore, "checkpoint exact chat restore")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
