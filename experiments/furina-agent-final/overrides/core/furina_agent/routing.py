from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path

from .config import HOME, Config
from .llm import LocalLLM, LLMError
from .providers import (
    OpenAICompatibleProvider,
    ProviderError,
    ProviderSecrets,
    provider_error_summary,
)


@dataclass
class RouteResult:
    backend: str = ""
    model: str = ""


class RoutingLLM:
    """LLM facade with provider/model failover and local fallback."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.local = LocalLLM(cfg)
        self.secrets = ProviderSecrets()
        self.last = RouteResult()
        self.last_failures: list[str] = []

    def health(self) -> bool:
        if self.cfg.routing_mode == "local":
            return self.local.health()
        if self.secrets.configured():
            return True
        return self.local.health() if self.cfg.routing_mode == "auto" else False

    def configured_online(self) -> list[str]:
        configured = set(self.secrets.configured())
        return [p for p in self.cfg.provider_order if p in configured]

    def _online_chat(self, messages, *, max_tokens: int, temperature: float, json_mode: bool = False) -> str:
        self.last_failures = []
        configured = self.configured_online()
        if not configured:
            raise LLMError("Belum ada API key online yang dikonfigurasi.")

        for name in configured:
            key = self.secrets.get(name)
            if not key:
                continue
            provider = OpenAICompatibleProvider(name, key, self.cfg)
            try:
                candidates = provider.candidate_models()
            except ProviderError as e:
                self.last_failures.append(f"{name}: {provider_error_summary(e)}")
                continue
            for candidate in candidates:
                try:
                    answer = provider.chat_model(
                        candidate.id,
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=json_mode,
                    )
                    self.last = RouteResult(name, candidate.id)
                    return answer
                except ProviderError as e:
                    self.last_failures.append(f"{name}/{candidate.id}: {provider_error_summary(e)}")
                    if e.invalid_key:
                        break
                    if e.status is None:
                        break
                    continue
        detail = "; ".join(self.last_failures[-5:])
        raise LLMError("Semua provider online gagal" + (f": {detail}" if detail else ""))

    def _ensure_local(self) -> bool:
        if self.local.health():
            return True
        if not self.cfg.model_path or not Path(self.cfg.model_path).exists():
            return False
        launcher = HOME / "bin" / "furina"
        if not launcher.exists():
            return False
        try:
            subprocess.run([str(launcher), "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=135, check=False)
        except Exception:
            return False
        return self.local.health()

    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        on_token=None,
        json_mode: bool = False,
    ) -> str:
        max_tokens = self.cfg.max_tokens if max_tokens is None else max_tokens
        temperature = self.cfg.temperature if temperature is None else temperature

        if self.cfg.routing_mode == "local":
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
                json_mode=json_mode,
            )
            self.last = RouteResult("local", "GGUF")
            return answer

        if self.cfg.routing_mode in {"auto", "online"}:
            try:
                answer = self._online_chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                )
                if on_token and answer and not json_mode:
                    on_token(answer)
                return answer
            except LLMError:
                if self.cfg.routing_mode == "online":
                    raise

        if self._ensure_local():
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
                json_mode=json_mode,
            )
            self.last = RouteResult("local", "GGUF")
            return answer
        failures = "; ".join(self.last_failures[-5:])
        raise LLMError("Provider online tidak tersedia dan model lokal belum aktif" + (f": {failures}" if failures else ""))
