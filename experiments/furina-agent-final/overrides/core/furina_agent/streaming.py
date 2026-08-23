from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class StreamMetrics:
    started_at: float = 0.0
    first_chunk_at: float = 0.0
    chunks: int = 0
    chars: int = 0

    @property
    def ttft_ms(self) -> float:
        if not self.started_at or not self.first_chunk_at:
            return 0.0
        return max(0.0, (self.first_chunk_at - self.started_at) * 1000.0)


class SmoothStream:
    """Low-latency stream coalescer shared by local and online providers.

    The first visible chunk is flushed immediately. Subsequent tiny deltas are
    coalesced for a very short frame-sized window so Termux/Android do not spend
    more time repainting than generating text.
    """

    def __init__(
        self,
        emit: Callable[[str], None],
        *,
        frame_ms: int = 22,
        max_buffer_chars: int = 96,
    ):
        self.emit = emit
        self.frame = max(0.008, min(frame_ms / 1000.0, 0.060))
        self.max_buffer_chars = max(24, max_buffer_chars)
        self.metrics = StreamMetrics(started_at=time.monotonic())
        self._q: queue.Queue[str | None] = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="furina-stream")
        self._thread.start()

    def feed(self, text: str) -> None:
        if self._closed or not text:
            return
        self._q.put(str(text))

    def close(self) -> StreamMetrics:
        if not self._closed:
            self._closed = True
            self._q.put(None)
            self._thread.join(timeout=2)
        return self.metrics

    def _write(self, text: str) -> None:
        if not text:
            return
        now = time.monotonic()
        if not self.metrics.first_chunk_at:
            self.metrics.first_chunk_at = now
        self.metrics.chunks += 1
        self.metrics.chars += len(text)
        self.emit(text)

    def _run(self) -> None:
        first = True
        buffer = ""
        deadline = 0.0
        while True:
            timeout = None
            if buffer:
                timeout = max(0.0, deadline - time.monotonic())
            try:
                item = self._q.get(timeout=timeout)
            except queue.Empty:
                item = ""

            if item is None:
                if buffer:
                    self._write(buffer)
                return

            if item:
                if first:
                    # Never delay the first token/chunk. Perceived latency is
                    # dominated by time-to-first-visible-content.
                    self._write(item)
                    first = False
                    continue
                if not buffer:
                    deadline = time.monotonic() + self.frame
                buffer += item

            if buffer and (len(buffer) >= self.max_buffer_chars or time.monotonic() >= deadline):
                self._write(buffer)
                buffer = ""
