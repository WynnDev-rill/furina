#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/llm.py"


def replace_method(class_name: str, name: str, source: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        raise SystemExit(f"{class_name} missing")
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    PATH.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


replace_method("LocalLLM", "_request_once", r'''    def _request_once(
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
            "chat_template_kwargs": {"enable_thinking": False},
            # llama.cpp-native conservative anti-loop sampling. A modest value
            # avoids the exact phrase/sentence loops seen on 1.7B models without
            # flattening vocabulary or changing the model/quantization.
            "repeat_penalty": 1.10 if not json_mode else 1.0,
            "repeat_last_n": 192 if not json_mode else 64,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = None
        smoother = None
        try:
            response = urllib.request.urlopen(req, timeout=180)
            with self.lock:
                self._active_response = response
            with response as r:
                if not payload["stream"]:
                    raw = json.loads(r.read().decode("utf-8"))
                    choice = raw["choices"][0]
                    content = choice.get("message", {}).get("content") or ""
                    return sanitize(content), str(choice.get("finish_reason") or "")
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
                        obj = json.loads(data); choice = obj.get("choices", [{}])[0]
                    except Exception:
                        continue
                    finish = str(choice.get("finish_reason") or finish or "")
                    piece = str((choice.get("delta") or {}).get("content") or "")
                    if piece:
                        raw_chunks.append(piece)
                        if stream_filter:
                            stream_filter.feed(piece)
                if stream_filter:
                    stream_filter.finish()
                return sanitize("".join(raw_chunks)), finish
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"llama-server HTTP {e.code}: {body[:700]}") from e
        except Exception as e:
            raise LLMError(f"Tidak dapat menghubungi llama-server: {e}") from e
        finally:
            if smoother:
                smoother.close()
            with self.lock:
                if self._active_response is response:
                    self._active_response = None''')

text = PATH.read_text(encoding="utf-8")
compile(text, str(PATH), "exec")
print("FURINA_PRIVATE_1_0_5_SAMPLING_OK")
