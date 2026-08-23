from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable

from .config import Config
from .streaming import SmoothStream


class LLMError(RuntimeError):
    pass


_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F\u200D\u20E3"
    "]",
    flags=re.UNICODE,
)
_REASON_TAGS = {"<think>": "</think>", "<analysis>": "</analysis>"}


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def sanitize(text: str) -> str:
    """Remove internal reasoning markup and pictographs from user-visible text."""
    text = str(text or "")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    text = re.sub(r"<analysis>.*?</analysis>", "", text, flags=re.I | re.S)
    text = re.sub(r"<think>.*$", "", text, flags=re.I | re.S)
    text = re.sub(r"<analysis>.*$", "", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:think|analysis)>", "", text, flags=re.I)
    text = _strip_emoji(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


class _VisibleStreamFilter:
    """Incrementally suppress hidden reasoning before any chunk reaches the UI."""

    def __init__(self, emit: Callable[[str], None]):
        self.emit = emit
        self.pending = ""
        self.hidden_close: str | None = None

    @staticmethod
    def _partial_open_suffix(text: str) -> int:
        low = text.lower()
        best = 0
        for opening in _REASON_TAGS:
            for n in range(1, min(len(opening) - 1, len(low)) + 1):
                if low.endswith(opening[:n]):
                    best = max(best, n)
        return best

    def feed(self, piece: str) -> None:
        self.pending += str(piece)
        while self.pending:
            low = self.pending.lower()
            if self.hidden_close:
                pos = low.find(self.hidden_close)
                if pos < 0:
                    keep = max(0, len(self.hidden_close) - 1)
                    self.pending = self.pending[-keep:] if keep else ""
                    return
                self.pending = self.pending[pos + len(self.hidden_close) :]
                self.hidden_close = None
                continue

            found: tuple[int, str, str] | None = None
            for opening, closing in _REASON_TAGS.items():
                pos = low.find(opening)
                if pos >= 0 and (found is None or pos < found[0]):
                    found = (pos, opening, closing)
            if found:
                pos, opening, closing = found
                visible = self.pending[:pos]
                if visible:
                    cleaned = _strip_emoji(visible)
                    if cleaned:
                        self.emit(cleaned)
                self.pending = self.pending[pos + len(opening) :]
                self.hidden_close = closing
                continue

            hold = self._partial_open_suffix(self.pending)
            visible = self.pending[:-hold] if hold else self.pending
            self.pending = self.pending[-hold:] if hold else ""
            if visible:
                cleaned = _strip_emoji(visible)
                if cleaned:
                    self.emit(cleaned)
            return

    def finish(self) -> None:
        if self.hidden_close:
            self.pending = ""
            return
        if self.pending:
            cleaned = sanitize(self.pending)
            if cleaned:
                self.emit(cleaned)
            self.pending = ""


class LocalLLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.llama_host}:{self.cfg.llama_port}"

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=1) as r:
                return 200 <= r.status < 300
        except Exception:
            return False

    def _request_once(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        on_token: Callable[[str], None] | None,
        json_mode: bool = False,
    ) -> tuple[str, str]:
        payload = {
            "model": "local",
            "messages": normalize_messages(messages),
            "temperature": temperature,
            "top_p": self.cfg.top_p,
            "top_k": self.cfg.top_k,
            "min_p": self.cfg.min_p,
            "max_tokens": max_tokens,
            "stream": bool(on_token) and not json_mode,
            "chat_template_kwargs": {"enable_thinking": bool(self.cfg.local_reasoning)},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # Only serialize requests; do not hold a lifecycle lock while the
            # UI consumes chunks. llama-server does continuous batching itself.
            with self.lock, urllib.request.urlopen(req, timeout=180) as r:
                if not payload["stream"]:
                    raw = json.loads(r.read().decode("utf-8"))
                    choice = raw["choices"][0]
                    content = choice.get("message", {}).get("content") or ""
                    finish = str(choice.get("finish_reason") or "")
                    return sanitize(content), finish

                raw_chunks: list[str] = []
                finish = ""
                smoother = SmoothStream(on_token, frame_ms=22, max_buffer_chars=96) if on_token else None
                stream_filter = _VisibleStreamFilter(smoother.feed) if smoother else None
                for raw_line in r:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        choice = obj.get("choices", [{}])[0]
                    except Exception:
                        continue
                    finish = str(choice.get("finish_reason") or finish or "")
                    delta = choice.get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        piece = str(piece)
                        raw_chunks.append(piece)
                        if stream_filter:
                            stream_filter.feed(piece)
                if stream_filter:
                    stream_filter.finish()
                if smoother:
                    smoother.close()
                return sanitize("".join(raw_chunks)), finish
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"llama-server HTTP {e.code}: {body[:700]}") from e
        except Exception as e:
            raise LLMError(f"Tidak dapat menghubungi llama-server: {e}") from e

    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        on_token: Callable[[str], None] | None = None,
        json_mode: bool = False,
    ) -> str:
        messages = normalize_messages(messages)
        limit = self.cfg.max_tokens if max_tokens is None else max_tokens
        temp = self.cfg.temperature if temperature is None else temperature
        answer, finish = self._request_once(
            messages,
            max_tokens=limit,
            temperature=temp,
            on_token=on_token,
            json_mode=json_mode,
        )
        if json_mode:
            return sanitize(answer)

        for _ in range(self.cfg.response_continuations):
            if finish not in {"length", "max_tokens"}:
                break
            continuation_messages = list(messages) + [
                {"role": "assistant", "content": answer[-6000:]},
                {"role": "user", "content": "Lanjutkan tepat dari bagian terakhir tanpa mengulang pembukaan. Berhenti sendiri setelah jawaban benar-benar selesai."},
            ]
            more, finish = self._request_once(
                continuation_messages,
                max_tokens=max(384, min(limit, 1536)),
                temperature=temp,
                on_token=on_token,
                json_mode=False,
            )
            if not more:
                break
            answer = (answer.rstrip() + " " + more.lstrip()).strip()
        return sanitize(answer)


def normalize_messages(messages: list[dict]) -> list[dict]:
    system_parts: list[str] = []
    turns: list[dict] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", ""))
        if role == "system":
            if content.strip():
                system_parts.append(content.strip())
            continue
        if role in {"user", "assistant", "tool"}:
            turns.append({"role": role, "content": content})
    if system_parts:
        return [{"role": "system", "content": "\n\n".join(system_parts)}] + turns
    return turns
