from __future__ import annotations

from dataclasses import dataclass
import re
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
from .vision import OnlineVision, VisionError
from .local_vision import LocalVision, LocalVisionError


@dataclass
class RouteResult:
    backend: str = ""
    model: str = ""
    role: str = "conversation"


class RoutingLLM:
    """Role-aware LLM facade.

    Provider success memory is isolated per task role so JSON planning/memory
    work cannot silently redefine the preferred conversation model.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.local = LocalLLM(cfg)
        self.secrets = ProviderSecrets()
        self.vision_router = OnlineVision(cfg, self.secrets)
        self.local_vision = LocalVision(cfg)
        self.last = RouteResult()
        self.last_by_role: dict[str, RouteResult] = {}
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

    @staticmethod
    def _infer_role(messages: list[dict], json_mode: bool) -> str:
        system = " ".join(
            str(m.get("content") or "") for m in messages[:3]
            if isinstance(m, dict) and str(m.get("role") or "") == "system"
        ).casefold()
        if any(token in system for token in ("memory consolidator", "reflection engine", "experience integrator")):
            return "memory"
        if any(token in system for token in ("verifier", "verification", "goal status")):
            return "verifier"
        if any(token in system for token in ("planner", "android agent", "semantic parser", "task contract")):
            return "agent_planner"
        if json_mode and any(token in system for token in ("json", "agent", "android", "tool")):
            return "agent_planner"
        return "conversation"

    @staticmethod
    def _normalize_role(role: str | None, messages: list[dict], json_mode: bool) -> str:
        if role:
            clean = re.sub(r"[^a-z0-9_-]+", "_", str(role).strip().lower())[:32]
            return clean or "conversation"
        return RoutingLLM._infer_role(messages, json_mode)

    def _record(self, backend: str, model: str, role: str) -> None:
        result = RouteResult(backend, model, role)
        self.last = result
        self.last_by_role[role] = result

    def _online_chat(
        self,
        messages,
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
        role: str = "conversation",
    ) -> str:
        self.last_failures = []
        configured = self.configured_online()
        if not configured:
            raise LLMError("Belum ada API key online yang dikonfigurasi.")

        for name in configured:
            key = self.secrets.get(name)
            if not key:
                continue
            provider = OpenAICompatibleProvider(name, key, self.cfg, role=role)
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
                    self._record(name, candidate.id, role)
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

    def vision(self, prompt: str, image_base64: str, *, mime: str = "image/png", max_tokens: int = 420, json_mode: bool = True) -> str:
        failures: list[str] = []
        if self.cfg.routing_mode != "online":
            try:
                return self.local_vision.analyze(prompt, image_base64, mime=mime, max_tokens=max_tokens, json_mode=json_mode)
            except LocalVisionError as exc:
                failures.append(str(exc))
        if self.cfg.routing_mode != "local" and self.secrets.configured():
            try:
                return self.vision_router.analyze(prompt, image_base64, mime=mime, max_tokens=max_tokens, json_mode=json_mode)
            except VisionError as exc:
                failures.append(str(exc))
        detail = "; ".join(failures[-3:])
        raise LLMError("Vision tidak tersedia" + (f": {detail}" if detail else ". Atur model vision lokal atau provider online."))

    def _ensure_local(self) -> bool:
        if self.local.health():
            return True
        if not self.cfg.model_path or not Path(self.cfg.model_path).exists():
            return False
        launcher = HOME / "bin" / "furina"
        if not launcher.exists():
            return False
        try:
            subprocess.run(
                [str(launcher), "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=135,
                check=False,
            )
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
        role: str | None = None,
    ) -> str:
        max_tokens = self.cfg.max_tokens if max_tokens is None else max_tokens
        temperature = self.cfg.temperature if temperature is None else temperature
        role = self._normalize_role(role, messages, json_mode)

        if self.cfg.routing_mode == "local":
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
                json_mode=json_mode,
            )
            self._record("local", "GGUF", role)
            return answer

        if self.cfg.routing_mode in {"auto", "online"}:
            try:
                answer = self._online_chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                    role=role,
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
            self._record("local", "GGUF", role)
            return answer
        failures = "; ".join(self.last_failures[-5:])
        raise LLMError(
            "Provider online tidak tersedia dan model lokal belum aktif"
            + (f": {failures}" if failures else "")
        )
