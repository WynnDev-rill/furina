from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable

from .config import Config


class LLMError(RuntimeError):
    pass


class LocalLLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.llama_host}:{self.cfg.llama_port}"

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=2) as r:
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
    ) -> tuple[str, str]:
        payload = {
            "model": "local",
            "messages": normalize_messages(messages),
            "temperature": temperature,
            "top_p": self.cfg.top_p,
            "top_k": self.cfg.top_k,
            "min_p": self.cfg.min_p,
            "max_tokens": max_tokens,
            "stream": bool(on_token),
            "chat_template_kwargs": {"enable_thinking": bool(self.cfg.local_reasoning)},
        }
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.lock, urllib.request.urlopen(req, timeout=360) as r:
                if not on_token:
                    raw = json.loads(r.read().decode("utf-8"))
                    choice = raw["choices"][0]
                    content = choice.get("message", {}).get("content") or ""
                    finish = str(choice.get("finish_reason") or "")
                    return sanitize(content), finish

                chunks: list[str] = []
                finish = ""
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
                        chunks.append(piece)
                        on_token(piece)
                return sanitize("".join(chunks)), finish
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
    ) -> str:
        messages = normalize_messages(messages)
        limit = self.cfg.max_tokens if max_tokens is None else max_tokens
        temp = self.cfg.temperature if temperature is None else temperature
        answer, finish = self._request_once(messages, max_tokens=limit, temperature=temp, on_token=on_token)

        # If llama.cpp explicitly says the generation hit the output cap, resume
        # once (configurable) rather than silently cutting a sentence in half.
        for _ in range(self.cfg.response_continuations):
            if finish != "length" or not answer:
                break
            continuation_messages = list(messages) + [
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": "Lanjutkan tepat dari bagian terakhir tanpa mengulang pembukaan. Selesaikan jawaban secara natural dan ringkas.",
                },
            ]
            more, finish = self._request_once(
                continuation_messages,
                max_tokens=max(256, min(limit, 768)),
                temperature=temp,
                on_token=on_token,
            )
            if not more:
                break
            answer = (answer.rstrip() + " " + more.lstrip()).strip()
        return sanitize(answer)


def sanitize(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    text = re.sub(r"<analysis>.*?</analysis>", "", text, flags=re.I | re.S)
    return text.strip()


def normalize_messages(messages: list[dict]) -> list[dict]:
    """Normalize messages for strict llama.cpp/Qwen chat templates."""
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
