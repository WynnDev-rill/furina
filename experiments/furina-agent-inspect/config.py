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
    config_revision: int = 3
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8765
    bridge_token: str = ""
    core_host: str = "127.0.0.1"
    core_port: int = 8766
    llama_host: str = "127.0.0.1"
    llama_port: int = 8080
    model_path: str = ""
    context_size: int = 4096
    threads: int = 6
    max_tokens: int = 1024
    response_continuations: int = 1
    temperature: float = 0.70
    top_p: float = 0.80
    top_k: int = 20
    min_p: float = 0.0
    local_reasoning: bool = False
    memory_limit: int = 6
    agent_max_steps: int = 14
    persona_name: str = "Furina"
    user_nickname: str = ""

    # LLM routing. AUTO tries configured online providers first and only wakes
    # the 2.7 GB local runtime when online inference is unavailable.
    routing_mode: str = "local"
    provider_order: list[str] = field(default_factory=lambda: ["groq", "openrouter", "nvidia", "gemini"])
    provider_prefer_free: bool = True
    provider_max_models: int = 5

    # Runtime tuning. Values are conservative defaults; `furina optimize`
    # benchmarks the actual phone/model and persists a better thread count.
    performance_tuned: bool = False
    cache_reuse: int = 256
    server_priority: int = 1
    cpu_mask: str = ""
    cpu_strict: bool = False

    # UX / permissions
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
    if defaults.get("routing_mode") not in {"local", "auto", "online"}:
        defaults["routing_mode"] = "local"

    # v0.2 shipped with a 320-token cap. That looked like a model failure when
    # a normal answer hit the cap, so migrate that exact legacy default.
    if int(raw.get("max_tokens", 0) or 0) <= 320:
        defaults["max_tokens"] = 1024
    defaults["max_tokens"] = max(128, min(int(defaults["max_tokens"]), 4096))
    defaults["response_continuations"] = max(0, min(int(defaults["response_continuations"]), 2))
    defaults["threads"] = max(1, min(int(defaults["threads"]), 12))
    defaults["context_size"] = max(2048, min(int(defaults["context_size"]), 16384))
    defaults["top_k"] = max(0, min(int(defaults["top_k"]), 100))
    defaults["min_p"] = max(0.0, min(float(defaults["min_p"]), 1.0))
    mask = str(defaults.get("cpu_mask") or "").strip().lower().removeprefix("0x")
    defaults["cpu_mask"] = mask if all(c in "0123456789abcdef" for c in mask) else ""
    defaults["config_revision"] = Config().config_revision
    return Config(**defaults)


def save_config(cfg: Config) -> None:
    ensure_dirs()
    cfg.user_nickname = cfg.user_nickname.strip()[:48]
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)
