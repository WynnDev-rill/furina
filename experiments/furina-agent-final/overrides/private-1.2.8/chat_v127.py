from __future__ import annotations


def install_chat_v127(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    previous_messages = FurinaChat._messages

    def messages(self, user_text, profile):
        from .hub_settings import load_hub_settings
        from .output_v127 import leaks_reasoning, leaks_roleplay

        rows = previous_messages(self, user_text, profile)
        roleplay_off = not bool(load_hub_settings().get("roleplay_mode", False))
        safe = []
        for row in rows:
            if row.get("role") == "assistant":
                content = str(row.get("content") or "")
                if leaks_reasoning(content) or (roleplay_off and leaks_roleplay(content)):
                    continue
            safe.append(row)
        if safe and safe[0].get("role") == "system":
            safe[0] = {
                **safe[0],
                "content": str(safe[0].get("content") or "")
                + "\n\nOUTPUT BOUNDARY: reasoning/meta-commentary is never dialogue. When RolePlay is off, answer only as direct conversation without narrated actions or invented scenes.",
            }
        return safe

    FurinaChat._messages = messages
