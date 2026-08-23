from __future__ import annotations

from collections.abc import Callable

from .streaming import SmoothStream


def smooth_online_callback(on_token: Callable[[str], None] | None):
    """Return (emit, close) for provider SSE streams.

    Providers can keep their native network parser; this wrapper guarantees the
    same first-chunk-fast / frame-coalesced rendering policy as the local path.
    """
    if on_token is None:
        return None, lambda: None
    stream = SmoothStream(on_token, frame_ms=22, max_buffer_chars=96)
    return stream.feed, stream.close
