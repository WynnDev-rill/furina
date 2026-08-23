from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class GenerationState:
    request_id: str
    started_at: float
    cancelled: threading.Event


class GenerationController:
    """Track one foreground generation and provide instant cooperative stop."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._current: GenerationState | None = None

    def begin(self, request_id: str) -> GenerationState:
        state = GenerationState(request_id=request_id, started_at=time.monotonic(), cancelled=threading.Event())
        with self._lock:
            old = self._current
            self._current = state
        if old:
            old.cancelled.set()
        return state

    def stop(self) -> bool:
        with self._lock:
            state = self._current
        if not state:
            return False
        state.cancelled.set()
        return True

    def finish(self, state: GenerationState) -> None:
        with self._lock:
            if self._current is state:
                self._current = None

    @staticmethod
    def guarded_emit(state: GenerationState, emit: Callable[[str], None]) -> Callable[[str], None]:
        def _emit(text: str) -> None:
            if state.cancelled.is_set():
                raise InterruptedError("generation cancelled")
            emit(text)
        return _emit
