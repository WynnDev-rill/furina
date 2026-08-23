from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STREAM_PROTOCOL = "furina-stream/2"


@dataclass(frozen=True)
class StreamEvent:
    kind: str
    text: str = ""
    request_id: str = ""
    meta: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"protocol": STREAM_PROTOCOL, "kind": self.kind}
        if self.text:
            payload["text"] = self.text
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.meta:
            payload["meta"] = self.meta
        return payload


def status(text: str, request_id: str = "") -> dict[str, Any]:
    return StreamEvent("status", text=text, request_id=request_id).as_dict()


def delta(text: str, request_id: str = "") -> dict[str, Any]:
    return StreamEvent("delta", text=text, request_id=request_id).as_dict()


def done(request_id: str = "", **meta: Any) -> dict[str, Any]:
    return StreamEvent("done", request_id=request_id, meta=meta or None).as_dict()


def error(text: str, request_id: str = "") -> dict[str, Any]:
    return StreamEvent("error", text=text, request_id=request_id).as_dict()
