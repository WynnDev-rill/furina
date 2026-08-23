from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

HOME = Path(os.environ.get("FURINA_HOME", Path.home() / ".furina-agent"))
CONFIG_PATH = HOME / "config.json"
DATA_DIR = HOME / "data"
LOG_DIR = HOME / "logs"
RUN_DIR = HOME / "run"
MODELS_DIR = HOME / "models"
PROVIDERS_PATH = DATA_DIR / "providers.json"
PROVIDER_STATE_PATH = DATA_DIR / "provider_state.json"
UPDATE_STATE_PATH = DATA_DIR / "update_state.json"
PERF_STATE_PATH = DATA_DIR / "performance.json"


@dataclass
class Config:
    config_revision: int = 6
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8765
    bridge_token: str = ""
    core_host: str = "127.0.0.1"
    core_port: int = 8766
    llama_host: str = "127.0.0.1"
    llama_port: int = 8080
    model_path: str = ""

    # Local Performance V2 defaults. 4K is the phone-first baseline; retrieval
    # keeps the useful companion context dense instead of blindly carrying a
    # large prompt into every turn.
    context_size: int = 4096
    threads: int = 5
    batch_size: int = 512
    ubatch_size: int = 128
    cache_reuse: int = 256
    flash_attention: str = "auto"
    accel_backend: str = "auto"
    keep_warm_seconds: int = 600
    prewarm_on_local_select: bool = True

    # Preserve the 1.0.1 response budget. Performance work targets startup,
    # prefill, caching and rendering rather than shortening Furina's answers.
    max_tokens: int = 2048
    response_continuations: int = 4

    temperature: float = 0.70
    top_p: float = 0.80
    top_k: int = 20
    min_p: float = 0.0
    local_reasoning: bool = False
    memory_limit: int = 7
    agent_max_steps: int = 28
    persona_name: str = "Furina"
    user_nickname: str = ""

    routing_mode: str = "local"
    provider_order: list[str] = field(default_factory=lambda: ["groq", "openrouter", "nvidia", "gemini"])
    provider_prefer_free: bool = True
    provider_max_models: int = 5

    performance_tuned: bool = False
    server_priority: int = 1
    cpu_mask: str = ""
    cpu_strict: bool = False

    auto_start: bool = True
    onboarding_complete: bool = False
    agent_task_approval: bool = True


def ensure_dirs() -> None:
    for p in (HOME, DATA_DIR, LOG_DIR, RUN_DIR, MODELS_DIR):
        p.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    defaults = asdict(Config())
    defaults.update({k: v for k, v in raw.items() if k in defaults})

    if not isinstance(defaults.get("provider_order"), list):
        defaults["provider_order"] = list(Config().provider_order)
    if defaults.get("routing_mode") not in {"local", "online"}:
        defaults["routing_mode"] = "local"

    try:
        revision = int(raw.get("config_revision", 0) or 0)
    except Exception:
        revision = 0

    # V2 migration only adjusts legacy performance defaults. Deliberate user
    # overrides and the response-quality budget are retained.
    if revision < 6:
        try:
            old_ctx = int(raw.get("context_size", 0) or 0)
        except Exception:
            old_ctx = 0
        if old_ctx in {0, 6144}:
            defaults["context_size"] = 4096
        try:
            old_threads = int(raw.get("threads", 0) or 0)
        except Exception:
            old_threads = 0
        if old_threads in {0, 6}:
            defaults["threads"] = 5

    defaults["max_tokens"] = max(128, min(int(defaults["max_tokens"]), 8192))
    defaults["response_continuations"] = max(0, min(int(defaults["response_continuations"]), 6))
    defaults["agent_max_steps"] = max(8, min(int(defaults["agent_max_steps"]), 48))
    defaults["memory_limit"] = max(3, min(int(defaults["memory_limit"]), 16))
    defaults["threads"] = max(1, min(int(defaults["threads"]), 12))
    defaults["context_size"] = max(2048, min(int(defaults["context_size"]), 16384))
    defaults["batch_size"] = max(64, min(int(defaults["batch_size"]), 2048))
    defaults["ubatch_size"] = max(32, min(int(defaults["ubatch_size"]), defaults["batch_size"]))
    defaults["cache_reuse"] = max(0, min(int(defaults["cache_reuse"]), 4096))
    defaults["keep_warm_seconds"] = max(0, min(int(defaults["keep_warm_seconds"]), 3600))
    defaults["flash_attention"] = str(defaults.get("flash_attention") or "auto").lower()
    if defaults["flash_attention"] not in {"auto", "on", "off"}:
        defaults["flash_attention"] = "auto"
    defaults["accel_backend"] = str(defaults.get("accel_backend") or "auto").lower()
    if defaults["accel_backend"] not in {"auto", "cpu", "opencl", "vulkan"}:
        defaults["accel_backend"] = "auto"
    defaults["top_k"] = max(0, min(int(defaults["top_k"]), 100))
    defaults["min_p"] = max(0.0, min(float(defaults["min_p"]), 1.0))
    mask = str(defaults.get("cpu_mask") or "").strip().lower().removeprefix("0x")
    defaults["cpu_mask"] = mask if all(c in "0123456789abcdef" for c in mask) else ""

    defaults["local_reasoning"] = False
    defaults["config_revision"] = Config().config_revision
    return Config(**defaults)


def save_config(cfg: Config) -> None:
    ensure_dirs()
    cfg.user_nickname = cfg.user_nickname.strip()[:48]
    cfg.local_reasoning = False
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)
