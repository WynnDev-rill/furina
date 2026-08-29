from __future__ import annotations


def install_settings_v128(ns: dict) -> None:
    previous_defaults = ns["defaults"]
    previous_normalize = ns["normalize"]

    def defaults() -> dict:
        state = previous_defaults()
        state["schema_version"] = 7
        state["inner_thoughts"] = False
        return state

    def normalize(raw: dict | None) -> dict:
        source = raw if isinstance(raw, dict) else {}
        state = previous_normalize(source)
        state["schema_version"] = 7
        state["inner_thoughts"] = bool(source.get("inner_thoughts", False))
        return state

    ns["SCHEMA_VERSION"] = 7
    ns["defaults"] = defaults
    ns["normalize"] = normalize
