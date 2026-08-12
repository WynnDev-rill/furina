from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PROVIDERS_PATH, PROVIDER_STATE_PATH, Config, ensure_dirs
from .llm import normalize_messages, sanitize


PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "groq": "Groq",
    "nvidia": "NVIDIA",
    "gemini": "Gemini",
}

PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.body = body

    @property
    def invalid_key(self) -> bool:
        return self.status in {401, 403}

    @property
    def quota_like(self) -> bool:
        return self.status in {402, 408, 409, 429} or (self.status is not None and self.status >= 500)


class ProviderSecrets:
    """Store user API keys locally, outside config.json, mode 0600."""

    def __init__(self, path: Path = PROVIDERS_PATH):
        self.path = path
        ensure_dirs()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in raw.items() if k in PROVIDER_LABELS and str(v).strip()}
        except Exception:
            return {}

    def _save(self, data: dict[str, str]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def set(self, provider: str, key: str) -> None:
        if provider not in PROVIDER_LABELS:
            raise ValueError(f"Provider tidak dikenal: {provider}")
        key = key.strip()
        if not key:
            raise ValueError("API key kosong")
        data = self._load()
        data[provider] = key
        self._save(data)

    def remove(self, provider: str) -> None:
        data = self._load()
        data.pop(provider, None)
        self._save(data)

    def get(self, provider: str) -> str | None:
        return self._load().get(provider)

    def configured(self) -> list[str]:
        data = self._load()
        return [p for p in PROVIDER_LABELS if data.get(p)]

    def masked(self, provider: str) -> str:
        key = self.get(provider)
        if not key:
            return "belum diatur"
        if len(key) <= 8:
            return "••••••••"
        return key[:4] + "…" + key[-4:]


@dataclass
class ModelInfo:
    id: str
    raw: dict[str, Any]
    score: float = 0.0
    free: bool = False


class ProviderState:
    def __init__(self, path: Path = PROVIDER_STATE_PATH):
        self.path = path
        ensure_dirs()

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except Exception:
            return {}

    def last_good(self, provider: str) -> str | None:
        value = self._load().get(provider, {}).get("last_good_model")
        return str(value) if value else None

    def mark_success(self, provider: str, model: str) -> None:
        data = self._load()
        data[provider] = {"last_good_model": model, "updated_at": time.time()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)


_MODEL_CACHE: dict[str, tuple[float, list[ModelInfo]]] = {}


class OpenAICompatibleProvider:
    def __init__(self, name: str, api_key: str, cfg: Config):
        if name not in PROVIDER_LABELS:
            raise ValueError(name)
        self.name = name
        self.api_key = api_key
        self.cfg = cfg
        self.base_url = PROVIDER_BASE_URLS[name].rstrip("/")
        self.state = ProviderState()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Furina-Agent/1.0 By-Wynn",
        }
        if self.name == "openrouter":
            headers["X-Title"] = "Furina Agent by Wynn"
        return headers

    def _json(self, method: str, url: str, payload: dict | None = None, timeout: int = 30) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                self.name,
                f"{PROVIDER_LABELS[self.name]} HTTP {e.code}",
                status=e.code,
                body=body[:1200],
            ) from e
        except Exception as e:
            raise ProviderError(self.name, f"{PROVIDER_LABELS[self.name]} tidak dapat dihubungi: {e}") from e

    @staticmethod
    def _zero(v: Any) -> bool:
        try:
            return float(v) == 0.0
        except Exception:
            return False

    def _model_info(self, raw: dict) -> ModelInfo | None:
        model_id = str(raw.get("id") or raw.get("name") or "").strip()
        if model_id.startswith("models/"):
            model_id = model_id.split("/", 1)[1]
        if not model_id:
            return None
        low = model_id.lower()
        blocked = ("embedding", "embed-", "whisper", "tts", "moderation", "rerank", "safety", "image", "vision-guard")
        if any(x in low for x in blocked):
            return None
        pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
        free = low.endswith(":free") or bool(
            pricing and self._zero(pricing.get("prompt")) and self._zero(pricing.get("completion"))
        )
        return ModelInfo(model_id, raw, free=free)

    def list_models(self, *, force: bool = False) -> list[ModelInfo]:
        cache_key = self.name + ":" + str(hash(self.api_key))
        cached = _MODEL_CACHE.get(cache_key)
        if cached and not force and time.time() - cached[0] < 1800:
            return list(cached[1])
        raw = self._json("GET", self.base_url + "/models", timeout=20)
        models: list[ModelInfo] = []
        for item in raw.get("data", []) if isinstance(raw, dict) else []:
            if isinstance(item, dict):
                info = self._model_info(item)
                if info:
                    models.append(info)
        if not models:
            raise ProviderError(self.name, f"{PROVIDER_LABELS[self.name]} tidak mengembalikan model chat yang dapat dipakai")
        models = self._rank_models(models)
        _MODEL_CACHE[cache_key] = (time.time(), list(models))
        return models

    def _rank_models(self, models: list[ModelInfo]) -> list[ModelInfo]:
        last = self.state.last_good(self.name)
        for m in models:
            low = m.id.lower()
            score = 0.0
            if m.id == last:
                score += 1000
            if self.name == "openrouter" and m.free:
                score += 300
            hints = {
                "gpt-oss-20b": 90,
                "gemini-3.6-flash": 90,
                "flash-lite": 86,
                "flash": 75,
                "qwen3.6": 82,
                "qwen3": 70,
                "nemotron": 70,
                "mistral": 65,
                "minimax": 62,
                "glm": 60,
                "llama": 55,
                "kimi": 55,
                "20b": 25,
                "8b": 22,
                "nano": 20,
                "instant": 20,
                "120b": 5,
                "ultra": -5,
            }
            for token, value in hints.items():
                if token in low:
                    score += value
            if "preview" in low or "experimental" in low or "exp-" in low:
                score -= 12
            if "thinking" in low or "reasoning" in low:
                score -= 35
            if self.name == "groq" and low.startswith("groq/compound"):
                score -= 10
            m.score = score
        models.sort(key=lambda x: (float(x.score), bool(x.free)), reverse=True)
        if self.name == "openrouter" and self.cfg.provider_prefer_free:
            free = [m for m in models if bool(m.free)]
            if free:
                return free
            return []
        return models

    def candidate_models(self) -> list[ModelInfo]:
        models = self.list_models()
        if not models and self.name == "openrouter" and self.cfg.provider_prefer_free:
            raise ProviderError(self.name, "OpenRouter: tidak ada model gratis yang ditemukan. Nonaktifkan mode free-only jika ingin memakai kredit.")
        return models[: max(1, int(self.cfg.provider_max_models))]

    def _apply_hidden_reasoning(self, payload: dict, model: str) -> None:
        """Keep model reasoning internal across providers that expose controls."""
        low = model.lower()
        if self.name == "openrouter":
            # OpenRouter documents `exclude` as provider-normalized and safe for
            # all models, including those with mandatory internal reasoning.
            payload["reasoning"] = {"exclude": True}
            return
        if self.name == "groq":
            if "qwen3" in low or "gpt-oss" in low:
                payload["reasoning_format"] = "hidden"
            if "qwen3.6" in low or "qwen3-32b" in low:
                payload["reasoning_effort"] = "none"

    def _chat_once(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> tuple[str, str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": normalize_messages(messages),
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.name != "gemini":
            payload["temperature"] = temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        self._apply_hidden_reasoning(payload, model)

        try:
            raw = self._json("POST", self.base_url + "/chat/completions", payload, timeout=120)
        except ProviderError as e:
            # A few OpenAI-compatible endpoints/models do not support
            # response_format. Retry JSON planning without that hint, while
            # preserving hidden-reasoning controls and strict prompt rules.
            if json_mode and e.status in {400, 422} and "response_format" in payload:
                payload.pop("response_format", None)
                raw = self._json("POST", self.base_url + "/chat/completions", payload, timeout=120)
            else:
                raise
        try:
            choice = raw["choices"][0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            finish = str(choice.get("finish_reason") or "")
        except Exception as e:
            raise ProviderError(self.name, f"Format respons {PROVIDER_LABELS[self.name]} tidak dikenali: {str(raw)[:500]}") from e
        return sanitize(str(content)), finish

    def chat_model(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
    ) -> str:
        normalized = normalize_messages(messages)
        answer, finish = self._chat_once(
            model,
            normalized,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )

        if not json_mode:
            for _ in range(self.cfg.response_continuations):
                if finish not in {"length", "max_tokens"}:
                    break
                continuation_messages = list(normalized) + [
                    {"role": "assistant", "content": answer[-6000:]},
                    {
                        "role": "user",
                        "content": "Lanjutkan tepat dari bagian terakhir tanpa mengulang pembukaan. Berhenti sendiri setelah jawaban benar-benar selesai.",
                    },
                ]
                more, finish = self._chat_once(
                    model,
                    continuation_messages,
                    max_tokens=max(512, min(max_tokens, 2048)),
                    temperature=temperature,
                    json_mode=False,
                )
                if not more:
                    break
                answer = (answer.rstrip() + " " + more.lstrip()).strip()

        answer = sanitize(answer)
        if not answer:
            raise ProviderError(self.name, f"{PROVIDER_LABELS[self.name]} tidak mengembalikan jawaban final yang dapat ditampilkan")
        self.state.mark_success(self.name, model)
        return answer

    def test(self) -> tuple[bool, str]:
        models = self.candidate_models()
        if not models:
            return False, "Tidak ada model kandidat"
        last_error = ""
        for model in models[:3]:
            try:
                reply = self.chat_model(
                    model.id,
                    [{"role": "user", "content": "Balas hanya: OK"}],
                    max_tokens=8,
                    temperature=0.0,
                )
                return True, f"{model.id} • {reply[:40] or 'OK'}"
            except ProviderError as e:
                last_error = provider_error_summary(e)
                if e.invalid_key:
                    break
        return False, last_error or "Tes gagal"


def provider_error_summary(error: ProviderError) -> str:
    body = error.body
    detail = ""
    if body:
        try:
            raw = json.loads(body)
            e = raw.get("error") if isinstance(raw, dict) else None
            if isinstance(e, dict):
                detail = str(e.get("message") or e.get("status") or "")
            elif e:
                detail = str(e)
        except Exception:
            detail = re.sub(r"\s+", " ", body)[:180]
    if error.status == 400:
        return "Provider menolak parameter/model (400)" + (f": {detail[:160]}" if detail else "")
    if error.status == 401:
        return "API key ditolak (401)"
    if error.status == 403:
        return "Akses provider ditolak (403)"
    if error.status == 402:
        return "Kredit/quota provider tidak tersedia (402)"
    if error.status == 429:
        return "Rate limit/quota tercapai (429)"
    suffix = f": {detail[:180]}" if detail else ""
    return f"{str(error)}{suffix}"
