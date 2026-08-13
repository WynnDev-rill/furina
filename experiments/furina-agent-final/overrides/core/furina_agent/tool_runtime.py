from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from .bridge import AndroidBridge
from .memory import MemoryStore
from .mind_v2 import FurinaMind


@dataclass
class ToolSpec:
    name: str
    handler: Callable[[dict], object]
    description: str = ""
    risk: str = "navigate"
    cost: str = "local"
    direct: bool = True
    verifier: str = "android_state"


class AgentToolRuntime:
    """Capability registry + execution boundary.

    Direct integrations can register beside Android primitives without changing
    the planner loop. Learned skills remain a higher-level composition layer;
    the UI agent remains the universal fallback.
    """

    def __init__(self, bridge: AndroidBridge, store: MemoryStore):
        self.bridge = bridge
        self.store = store
        self.mind = FurinaMind(store)
        self._handlers: dict[str, ToolSpec] = {}
        self._recent_failures: dict[str, tuple[int, float]] = {}

    def register(
        self,
        action_type: str,
        handler: Callable[[dict], object],
        *,
        name: str | None = None,
        description: str = "",
        risk: str = "navigate",
        cost: str = "local",
        direct: bool = True,
        verifier: str = "android_state",
    ) -> None:
        action_type = str(action_type or "").strip()
        if not action_type:
            raise ValueError("action_type wajib diisi")
        self._handlers[action_type] = ToolSpec(
            name or action_type,
            handler,
            str(description)[:240],
            str(risk)[:32],
            str(cost)[:32],
            bool(direct),
            str(verifier)[:64],
        )

    def unregister(self, action_type: str) -> None:
        self._handlers.pop(str(action_type or ""), None)

    def list_tools(self) -> list[str]:
        return sorted(self._handlers)

    def capabilities(self) -> list[dict]:
        stats = self.store.get_state("furina_agent_capabilities", {})
        stats = stats if isinstance(stats, dict) else {}
        rows = []
        for action_type, spec in sorted(self._handlers.items()):
            row = stats.get(spec.name) if isinstance(stats.get(spec.name), dict) else {}
            rows.append(
                {
                    "action_type": action_type,
                    "name": spec.name,
                    "description": spec.description,
                    "risk": spec.risk,
                    "cost": spec.cost,
                    "direct": spec.direct,
                    "verifier": spec.verifier,
                    "reliability": float(row.get("reliability", 0.5) or 0.5),
                    "uses": int(row.get("uses", 0) or 0),
                }
            )
        return rows

    @staticmethod
    def _fingerprint(action: dict) -> str:
        stable = {
            k: action.get(k)
            for k in (
                "type",
                "package",
                "node",
                "x",
                "y",
                "x1",
                "y1",
                "x2",
                "y2",
                "direction",
                "text",
                "duration_ms",
                "target",
            )
            if k in action
        }
        try:
            return json.dumps(
                stable,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
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
        return ToolSpec(
            "android_bridge",
            self.bridge.action,
            "Universal Android Accessibility/gesture transport",
            "navigate",
            "local",
            False,
            "android_state",
        )

    def _record(self, spec: ToolSpec, ok: bool, elapsed: int) -> None:
        try:
            self.mind.record_agent_outcome(spec.name, ok, ms=elapsed)
        except Exception:
            pass

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
            self._recent_failures[fingerprint] = (
                count,
                time.monotonic(),
            )
            self._record(spec, False, elapsed)
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
            self._recent_failures[fingerprint] = (
                count,
                time.monotonic(),
            )

        self._record(spec, ok, elapsed)
        self.store.log_event(
            "agent_tool_runtime",
            {
                "tool": spec.name,
                "action": action_type,
                "ok": ok,
                "ms": elapsed,
                "risk": spec.risk,
                "cost": spec.cost,
                "direct": spec.direct,
                "verifier": spec.verifier,
            },
        )
        return result
