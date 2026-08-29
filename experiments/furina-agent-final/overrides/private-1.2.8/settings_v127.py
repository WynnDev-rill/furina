from __future__ import annotations


def install_settings_v127(ns: dict) -> None:
    previous_defaults = ns["defaults"]
    previous_normalize = ns["normalize"]

    def defaults() -> dict:
        state = previous_defaults()
        state.pop("custom_personality_traits", None)
        state["schema_version"] = 6
        state["roleplay_mode"] = bool(state.get("roleplay_mode", False))
        return state

    def normalize(raw: dict | None) -> dict:
        source = raw if isinstance(raw, dict) else {}
        state = previous_normalize(source)
        # Core 1.1.26 briefly exposed custom traits. They were not part of the
        # intended 20-trait product and must not survive as hidden behavior.
        state.pop("custom_personality_traits", None)
        state["schema_version"] = 6
        state["roleplay_mode"] = bool(source.get("roleplay_mode", False))
        return state

    def personalization_prompt(settings: dict | None = None, user_text: str = "", context: dict | None = None) -> str:
        from .personality import compile_contextual_personality

        state = normalize(settings) if settings is not None else ns["load_hub_settings"]()
        merged = dict(context or {})
        merged["partner_mode"] = bool(state.get("partner_mode"))
        merged["roleplay_mode"] = bool(state.get("roleplay_mode"))
        return (
            "[PERSONAL EXPRESSION — 20 built-in traits, contextual expression]\n"
            + compile_contextual_personality(state.get("personality_traits"), user_text, context=merged)
            + "\nNama companion hanyalah identitas yang dapat diganti dan tidak membawa lore atau latar tokoh lain."
        )

    ns["SCHEMA_VERSION"] = 6
    ns["defaults"] = defaults
    ns["normalize"] = normalize
    ns["personalization_prompt"] = personalization_prompt
