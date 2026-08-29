from __future__ import annotations

import re


def _custom_traits(raw) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(raw if isinstance(raw, list) else ()):
        if not isinstance(item, dict):
            continue
        label = re.sub(r"\s+", " ", str(item.get("label") or "").strip())[:48]
        description = re.sub(r"[\r\n\[\]{}]+", " ", str(item.get("description") or "").strip())
        description = re.sub(r"\s+", " ", description)[:240]
        if len(label) < 2 or len(description) < 3:
            continue
        key = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or f"custom-{index + 1}"
        key = (str(item.get("id") or key).strip().casefold()[:64] or key)
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": key, "label": label, "description": description, "active": bool(item.get("active", True))})
    return out


def install_settings_v126(ns: dict) -> None:
    old_defaults = ns["defaults"]
    old_normalize = ns["normalize"]

    def defaults() -> dict:
        state = old_defaults()
        state["schema_version"] = 5
        state["roleplay_mode"] = False
        state["custom_personality_traits"] = []
        return state

    def normalize(raw: dict | None) -> dict:
        source = raw if isinstance(raw, dict) else {}
        state = old_normalize(source)
        state["schema_version"] = 5
        state["roleplay_mode"] = bool(source.get("roleplay_mode", False))
        state["custom_personality_traits"] = _custom_traits(source.get("custom_personality_traits"))
        return state

    def personalization_prompt(settings: dict | None = None, user_text: str = "", context: dict | None = None) -> str:
        from .personality import compile_contextual_personality
        state = normalize(settings) if settings is not None else ns["load_hub_settings"]()
        merged = dict(context or {})
        merged["partner_mode"] = bool(state.get("partner_mode"))
        merged["roleplay_mode"] = bool(state.get("roleplay_mode"))
        merged["custom_traits"] = state.get("custom_personality_traits") or []
        return (
            "[PERSONAL EXPRESSION — stable traits, contextual expression]\n"
            + compile_contextual_personality(state.get("personality_traits"), user_text, context=merged)
            + "\nNama companion hanyalah identitas yang dapat diganti dan tidak membawa lore atau latar tokoh lain."
        )

    ns["SCHEMA_VERSION"] = 5
    ns["defaults"] = defaults
    ns["normalize"] = normalize
    ns["personalization_prompt"] = personalization_prompt
