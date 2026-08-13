from __future__ import annotations

import math
import time


def _estimate_tokens(messages: list[dict], max_tokens: int) -> tuple[int, int]:
    chars = sum(
        len(str(m.get("content") or ""))
        for m in messages
        if isinstance(m, dict)
    )
    prompt = max(1, math.ceil(chars / 4))
    return prompt, max(1, int(max_tokens))


def enqueue_event(store, event: dict) -> None:
    """Cheap event batching only. Never invokes an LLM."""
    if not isinstance(event, dict):
        return
    typ = str(event.get("type") or "")
    text = str(event.get("text") or "").strip()
    package = str(event.get("package") or "")
    if not (typ or text or package):
        return

    raw = store.get_state("cognition_event_batch", [])
    rows = raw if isinstance(raw, list) else []
    compact = {
        "type": typ[:48],
        "package": package[:120],
        "text": text[:180],
        "at": float(event.get("at", time.time()) or time.time()),
    }

    if rows:
        prev = rows[-1]
        if (
            isinstance(prev, dict)
            and prev.get("type") == compact["type"]
            and prev.get("package") == compact["package"]
            and prev.get("text") == compact["text"]
        ):
            prev["at"] = compact["at"]
            prev["repeat"] = min(
                999, int(prev.get("repeat", 1) or 1) + 1
            )
            store.set_state("cognition_event_batch", rows[-48:])
            return

    compact["repeat"] = 1
    rows.append(compact)
    store.set_state("cognition_event_batch", rows[-48:])


class CognitionBudget:
    def __init__(self, cfg, store):
        self.cfg = cfg
        self.store = store

    def _state(self) -> dict:
        day = time.strftime("%Y-%m-%d", time.localtime())
        raw = self.store.get_state("cognition_budget", {})
        state = raw if isinstance(raw, dict) else {}
        if state.get("day") != day:
            state = {
                "day": day,
                "online_calls": 0,
                "estimated_input_tokens": 0,
                "reserved_output_tokens": 0,
                "by_purpose": {},
            }
        return state

    def allow(
        self,
        messages: list[dict],
        max_tokens: int,
        purpose: str,
    ) -> bool:
        state = self._state()
        prompt, output = _estimate_tokens(messages, max_tokens)

        max_calls = max(
            0,
            int(getattr(self.cfg, "cognition_daily_online_calls", 12)),
        )
        max_tokens_day = max(
            1000,
            int(
                getattr(
                    self.cfg,
                    "cognition_daily_estimated_tokens",
                    24000,
                )
            ),
        )
        remaining_calls = max_calls - int(
            state.get("online_calls", 0) or 0
        )

        # Preserve a small reserve for self-reflection, which is the
        # highest-value background cognition in this companion-first design.
        if purpose == "memory_consolidation" and remaining_calls <= 2:
            return False

        estimated = int(
            state.get("estimated_input_tokens", 0) or 0
        ) + int(state.get("reserved_output_tokens", 0) or 0)
        return (
            remaining_calls > 0
            and estimated + prompt + output <= max_tokens_day
        )

    def record(
        self,
        messages: list[dict],
        max_tokens: int,
        purpose: str,
    ) -> None:
        state = self._state()
        prompt, output = _estimate_tokens(messages, max_tokens)

        state["online_calls"] = int(
            state.get("online_calls", 0) or 0
        ) + 1
        state["estimated_input_tokens"] = int(
            state.get("estimated_input_tokens", 0) or 0
        ) + prompt
        state["reserved_output_tokens"] = int(
            state.get("reserved_output_tokens", 0) or 0
        ) + output

        by = (
            state.get("by_purpose")
            if isinstance(state.get("by_purpose"), dict)
            else {}
        )
        by[purpose] = int(by.get(purpose, 0) or 0) + 1
        state["by_purpose"] = by
        self.store.set_state("cognition_budget", state)


class CognitionRouter:
    """Online-first internal cognition with local fallback only when appropriate.

    No timer lives here. Calls occur only while Furina Core is already active,
    so closing Termux leaves no model heartbeat burning CPU or battery.
    """

    def __init__(self, cfg, store, llm):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.budget = CognitionBudget(cfg, store)

    def run(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        purpose: str,
        json_mode: bool = True,
    ) -> str:
        configured = []
        if hasattr(self.llm, "configured_online"):
            try:
                configured = list(self.llm.configured_online())
            except Exception:
                configured = []

        prefer_online = bool(
            getattr(self.cfg, "cognition_online_preferred", True)
        )

        if configured and prefer_online:
            if not self.budget.allow(messages, max_tokens, purpose):
                # An API exists, so do not silently heat the phone just
                # because the background quota is exhausted. Defer cognition.
                self.store.log_event(
                    "cognition_deferred",
                    {"purpose": purpose, "reason": "daily_budget"},
                )
                return ""

            try:
                if hasattr(self.llm, "cognitive_chat"):
                    answer = self.llm.cognitive_chat(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=json_mode,
                        prefer_online=True,
                    )
                else:
                    answer = self.llm.chat(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=json_mode,
                    )
                if answer:
                    self.budget.record(
                        messages, max_tokens, purpose
                    )
                return answer or ""
            except Exception as exc:
                self.store.log_event(
                    "cognition_online_error",
                    {
                        "purpose": purpose,
                        "error": str(exc)[:220],
                    },
                )
                return ""

        # No online provider configured: use Qwen/local as the functional
        # fallback. This path only runs while the Core is active.
        try:
            if hasattr(self.llm, "cognitive_chat"):
                return self.llm.cognitive_chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                    prefer_online=False,
                )
            return self.llm.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
            )
        except Exception as exc:
            self.store.log_event(
                "cognition_local_error",
                {
                    "purpose": purpose,
                    "error": str(exc)[:220],
                },
            )
            return ""
