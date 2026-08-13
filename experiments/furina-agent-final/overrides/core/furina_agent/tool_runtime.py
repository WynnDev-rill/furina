from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from .bridge import AndroidBridge
from .memory import MemoryStore


@dataclass
class ToolSpec:
    name: str
    handler: Callable[[dict], object]


class AgentToolRuntime:
    """Small execution boundary for agent actions.

    The planner stays independent from transport details. Android Bridge is the
    default transport today, while future tools can register action handlers
    without changing the planner loop.
    """

    def __init__(self, bridge: AndroidBridge, store: MemoryStore):
        self.bridge = bridge
        self.store = store
        self._handlers: dict[str, ToolSpec] = {}
        self._recent_failures: dict[str, tuple[int, float]] = {}

    def register(self, action_type: str, handler: Callable[[dict], object], *, name: str | None = None) -> None:
        action_type = str(action_type or "").strip()
        if not action_type:
            raise ValueError("action_type wajib diisi")
        self._handlers[action_type] = ToolSpec(name or action_type, handler)

    def unregister(self, action_type: str) -> None:
        self._handlers.pop(str(action_type or ""), None)

    def list_tools(self) -> list[str]:
        return sorted(self._handlers)

    @staticmethod
    def _fingerprint(action: dict) -> str:
        stable = {
            k: action.get(k)
            for k in (
                "type", "package", "node", "x", "y", "x1", "y1", "x2", "y2",
                "direction", "text", "duration_ms", "target",
            )
            if k in action
        }
        try:
            return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            return repr(stable)

    @staticmethod
    def _ok(result: object) -> bool:
        if isinstance(result, dict):
            return bool(result.get("ok"))
        return bool(result)

    def _handler_for(self, action_type: str) -> ToolSpec:
        spec = self._handlers.get(action_type)
        if spec is not None:
            return spec
        return ToolSpec("android_bridge", self.bridge.action)

    def execute(self, action: dict):
        if not isinstance(action, dict):
            raise TypeError("action harus dict")
        action_type = str(action.get("type") or "").strip()
        if not action_type:
            raise ValueError("action.type kosong")

        fingerprint = self._fingerprint(action)
        now = time.monotonic()
        failed = self._recent_failures.get(fingerprint)
        if failed and failed[0] >= 2 and now - failed[1] <= 2.5:
            self.store.log_event(
                "agent_tool_runtime",
                {
                    "tool": action_type,
                    "ok": False,
                    "suppressed_duplicate_failure": True,
                },
            )
            return {
                "ok": False,
                "error": "repeated_failed_action_suppressed",
                "runtime_suppressed": True,
            }

        spec = self._handler_for(action_type)
        started = time.monotonic()
        try:
            result = spec.handler(action)
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            count = (failed[0] if failed else 0) + 1
            self._recent_failures[fingerprint] = (count, time.monotonic())
            self.store.log_event(
                "agent_tool_runtime",
                {
                    "tool": spec.name,
                    "action": action_type,
                    "ok": False,
                    "ms": elapsed,
                    "error": str(exc)[:240],
                },
            )
            raise

        elapsed = int((time.monotonic() - started) * 1000)
        ok = self._ok(result)
        if ok:
            self._recent_failures.pop(fingerprint, None)
        else:
            count = (failed[0] if failed else 0) + 1
            self._recent_failures[fingerprint] = (count, time.monotonic())

        self.store.log_event(
            "agent_tool_runtime",
            {
                "tool": spec.name,
                "action": action_type,
                "ok": ok,
                "ms": elapsed,
            },
        )
        return result
