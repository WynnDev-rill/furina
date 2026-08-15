from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config
from .llm import sanitize
from .providers import PROVIDER_BASE_URLS, PROVIDER_LABELS, ProviderSecrets


class VisionError(RuntimeError):
    pass


_VISION_HINTS = (
    "vision", "-vl", "/vl", "vl-", "llava", "pixtral", "llama-4",
    "gemma-3", "minicpm-v", "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "ocr",
)
_BLOCKED = ("embed", "rerank", "moderation", "guard", "tts", "whisper")


class OnlineVision:
    """Best-effort screenshot understanding using an already configured provider.

    Accessibility remains the primary control path. This is intentionally a
    fallback for WebViews/custom views/canvas-heavy apps that expose too little
    semantic UI. No new API key is required.
    """

    def __init__(self, cfg: Config, secrets: ProviderSecrets | None = None):
        self.cfg = cfg
        self.secrets = secrets or ProviderSecrets()

    @staticmethod
    def _headers(name: str, key: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Furina-Agent/1.0 By-Wynn",
        }
        if name == "openrouter":
            headers["X-Title"] = "Furina Agent by Wynn"
        return headers

    def _json(self, name: str, key: str, method: str, path: str, payload: dict | None = None, timeout: int = 90):
        url = PROVIDER_BASE_URLS[name].rstrip("/") + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(name, key), method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise VisionError(f"{PROVIDER_LABELS.get(name, name)} vision HTTP {e.code}: {body[:300]}") from e
        except Exception as e:
            raise VisionError(f"{PROVIDER_LABELS.get(name, name)} vision gagal: {e}") from e

    def _models(self, name: str, key: str) -> list[str]:
        raw = self._json(name, key, "GET", "/models", timeout=20)
        out: list[str] = []
        for item in raw.get("data", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            model = str(item.get("id") or item.get("name") or "").strip()
            if model.startswith("models/"):
                model = model.split("/", 1)[1]
            low = model.lower()
            if model and any(h in low for h in _VISION_HINTS) and not any(b in low for b in _BLOCKED):
                out.append(model)
        # Prefer smaller/faster vision models for UI grounding.
        def score(model: str) -> int:
            low = model.lower()
            value = 0
            for token, pts in (
                ("flash", 60), ("scout", 55), ("4b", 50), ("3b", 48), ("2b", 45),
                ("mini", 38), ("nano", 35), ("qwen3-vl", 32), ("qwen2.5-vl", 28),
                ("llama-4", 25), ("gemma-3", 20), ("72b", -25), ("90b", -30), ("405b", -50),
            ):
                if token in low:
                    value += pts
            return value
        return sorted(dict.fromkeys(out), key=score, reverse=True)

    def analyze(self, prompt: str, image_base64: str, *, mime: str = "image/png", max_tokens: int = 420, json_mode: bool = True) -> str:
        mime = mime if mime in {"image/jpeg", "image/png", "image/webp"} else "image/png"
        configured = set(self.secrets.configured())
        failures: list[str] = []
        for name in self.cfg.provider_order:
            if name not in configured or name not in PROVIDER_BASE_URLS:
                continue
            key = self.secrets.get(name)
            if not key:
                continue
            try:
                models = self._models(name, key)
            except Exception as exc:
                failures.append(str(exc))
                continue
            for model in models[:4]:
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + image_base64, "detail": "high"}},
                            ],
                        }
                    ],
                    "max_tokens": max_tokens,
                    "stream": False,
                    "temperature": 0.0,
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                try:
                    try:
                        raw = self._json(name, key, "POST", "/chat/completions", payload, timeout=120)
                    except VisionError as first:
                        # Some compatible providers support image input but not
                        # response_format. Retry without the optional hint.
                        if json_mode and "response_format" in payload:
                            payload.pop("response_format", None)
                            raw = self._json(name, key, "POST", "/chat/completions", payload, timeout=120)
                        else:
                            raise first
                    choice = raw.get("choices", [{}])[0]
                    message = choice.get("message") or {}
                    text = sanitize(str(message.get("content") or ""))
                    if text:
                        return text
                except Exception as exc:
                    failures.append(f"{name}/{model}: {exc}")
                    continue
        raise VisionError("Tidak ada model vision online yang berhasil" + (": " + "; ".join(failures[-4:]) if failures else ""))
