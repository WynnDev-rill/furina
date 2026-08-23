from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config, PERF_STATE_PATH, RUN_DIR, save_config


@dataclass
class RuntimeStatus:
    state: str = "stopped"
    detail: str = ""
    started_at: float = 0.0
    ready_at: float = 0.0
    backend: str = "cpu"
    threads: int = 0


_HELP_CACHE: dict[str, str] = {}
_RUNTIME_LOCK = threading.RLock()
_RUNTIME_SINGLETON: "LocalRuntime | None" = None


def _binary_for_backend(backend: str) -> str | None:
    env_name = {
        "cpu": "FURINA_LLAMA_SERVER",
        "opencl": "FURINA_LLAMA_SERVER_OPENCL",
        "vulkan": "FURINA_LLAMA_SERVER_VULKAN",
    }.get(backend, "FURINA_LLAMA_SERVER")
    explicit = os.environ.get(env_name)
    if explicit and Path(explicit).exists():
        return explicit
    if backend == "cpu":
        return shutil.which("llama-server")
    # Do not pretend one generic Android binary exposes a particular GPU
    # backend. Accelerators are considered only when a backend-specific build
    # is actually installed/provided.
    return None


def _help(binary: str) -> str:
    cached = _HELP_CACHE.get(binary)
    if cached is not None:
        return cached
    try:
        p = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=4, check=False)
        value = (p.stdout or "") + "\n" + (p.stderr or "")
    except Exception:
        value = ""
    _HELP_CACHE[binary] = value
    return value


def _flag_supported(help_text: str, flag: str) -> bool:
    return flag in help_text


class LocalRuntime:
    """Own a selected local model without making the chat surface block silently."""

    def __init__(self, cfg: Config, model_path: Callable[[], Path | None]):
        self.cfg = cfg
        self._model_path = model_path
        self._proc: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._stop_event = threading.Event()
        self._last_use = 0.0
        self._model_loaded = ""
        self._generation = 0
        self.status = RuntimeStatus()
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        self._watchdog = threading.Thread(target=self._idle_watchdog, daemon=True, name="furina-local-idle")
        self._watchdog.start()
        atexit.register(self.stop)

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.llama_host}:{self.cfg.llama_port}"

    def update_config(self, cfg: Config, model_path: Callable[[], Path | None]) -> None:
        """Refresh mutable settings while retaining one runtime per process."""
        with self._lock:
            old_model = str(self._model_path() or "")
            self.cfg = cfg
            self._model_path = model_path
            new_model = str(self._model_path() or "")
        if self._proc and old_model != new_model:
            self.stop()

    def health(self, timeout: float = 0.45) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=timeout) as r:
                return 200 <= r.status < 300
        except Exception:
            return False

    def touch(self) -> None:
        self._last_use = time.monotonic()

    def prewarm(self) -> None:
        if not self.cfg.prewarm_on_local_select:
            return
        with self._lock:
            if self.health() or (self._proc and self._proc.poll() is None):
                self.touch(); return
            generation = self._generation = self._generation + 1
            threading.Thread(target=self._start_worker, args=(generation,), daemon=True, name="furina-local-prewarm").start()

    def ensure_ready(self, *, timeout: float = 45.0, status_cb: Callable[[str], None] | None = None) -> bool:
        if self.health():
            self.status.state = "ready"; self.touch(); return True
        self.prewarm()
        started = time.monotonic(); last_note = 0.0
        while time.monotonic() - started < min(timeout, 45.0):
            if self._ready.wait(0.15):
                self.touch(); return self.health(timeout=0.7)
            now = time.monotonic()
            if status_cb and now - last_note > 0.7:
                status_cb("Menyiapkan model lokal…"); last_note = now
            with self._lock:
                if self.status.state == "error": return False
        return False

    def stop(self) -> None:
        with self._lock:
            self._generation += 1
            proc = self._proc
            self._proc = None
            self._ready.clear()
            self.status.state = "stopped"
        if proc and proc.poll() is None:
            try:
                proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try: proc.kill()
                except Exception: pass

    def _start_worker(self, generation: int) -> None:
        model = self._model_path()
        if not model or not model.exists():
            with self._lock:
                if generation == self._generation: self.status = RuntimeStatus(state="error", detail="Model lokal belum diunduh")
            return
        backend = self._choose_backend()
        binary = _binary_for_backend(backend)
        if not binary:
            backend = "cpu"; binary = _binary_for_backend("cpu")
        if not binary:
            with self._lock:
                if generation == self._generation: self.status = RuntimeStatus(state="error", detail="llama-server belum tersedia")
            return
        with self._lock:
            if generation != self._generation: return
            if self._proc and self._proc.poll() is None: return
            self._ready.clear()
            self.status = RuntimeStatus(state="loading", detail="Menyiapkan model lokal…", started_at=time.time(), backend=backend, threads=self.cfg.threads)
        cmd = self._server_command(model, backend, binary)
        log = (RUN_DIR / "llama-server.log").open("ab", buffering=0)
        try:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, env={**os.environ, "OMP_NUM_THREADS": str(self.cfg.threads)})
        except Exception as exc:
            log.close()
            with self._lock:
                if generation == self._generation: self.status = RuntimeStatus(state="error", detail=f"llama-server gagal dimulai: {exc}")
            return
        with self._lock:
            if generation != self._generation:
                try: proc.terminate()
                except Exception: pass
                return
            self._proc = proc; self._model_loaded = str(model)
        deadline = time.monotonic() + 42.0
        while time.monotonic() < deadline:
            if proc.poll() is not None: break
            if self.health(timeout=0.6):
                with self._lock:
                    if generation == self._generation:
                        self.status.state = "ready"; self.status.detail = "Siap"; self.status.ready_at = time.time(); self._ready.set(); self.touch()
                return
            time.sleep(0.18)
        with self._lock:
            if generation == self._generation:
                self.status.state = "error"; self.status.detail = "Model lokal terlalu lama disiapkan"
        try: proc.terminate()
        except Exception: pass

    def _server_command(self, model: Path, backend: str, binary: str) -> list[str]:
        help_text = _help(binary)
        cmd = [binary, "--host", self.cfg.llama_host, "--port", str(self.cfg.llama_port), "--model", str(model), "--ctx-size", str(self.cfg.context_size), "--threads", str(self.cfg.threads)]
        optional: list[tuple[str, list[str]]] = [
            ("--threads-batch", ["--threads-batch", str(self.cfg.threads)]),
            ("--batch-size", ["--batch-size", str(self.cfg.batch_size)]),
            ("--ubatch-size", ["--ubatch-size", str(self.cfg.ubatch_size)]),
            ("--parallel", ["--parallel", "1"]),
            ("--cache-reuse", ["--cache-reuse", str(self.cfg.cache_reuse)]),
            ("--prio", ["--prio", str(self.cfg.server_priority)]),
        ]
        for flag, args in optional:
            if _flag_supported(help_text, flag): cmd += args
        if _flag_supported(help_text, "--cont-batching"): cmd.append("--cont-batching")
        if self.cfg.cpu_mask and _flag_supported(help_text, "--cpu-mask"):
            cmd += ["--cpu-mask", self.cfg.cpu_mask]
            if self.cfg.cpu_strict and _flag_supported(help_text, "--cpu-strict"): cmd += ["--cpu-strict", "1"]
        if _flag_supported(help_text, "--flash-attn"):
            cmd += ["--flash-attn", self.cfg.flash_attention]
        if _flag_supported(help_text, "--n-gpu-layers"):
            cmd += ["--n-gpu-layers", "0" if backend == "cpu" else "999"]
        return cmd

    def _choose_backend(self) -> str:
        requested = self.cfg.accel_backend
        if requested in {"opencl", "vulkan"} and _binary_for_backend(requested): return requested
        if requested == "cpu": return "cpu"
        try:
            raw = json.loads(PERF_STATE_PATH.read_text(encoding="utf-8")); backend = str(raw.get("best_backend") or "cpu")
            if backend in {"opencl", "vulkan"} and _binary_for_backend(backend): return backend
        except Exception: pass
        return "cpu"

    def _idle_watchdog(self) -> None:
        while not self._stop_event.wait(5.0):
            if self.cfg.keep_warm_seconds <= 0: continue
            with self._lock:
                alive = bool(self._proc and self._proc.poll() is None); last = self._last_use
            if alive and last and time.monotonic() - last > self.cfg.keep_warm_seconds: self.stop()


class LocalPerformanceTuner:
    def __init__(self, cfg: Config, runtime: LocalRuntime):
        self.cfg = cfg; self.runtime = runtime

    def record_profile(self, *, threads: int, backend: str, ttft_ms: float, tokens_per_second: float = 0.0) -> None:
        PERF_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": 2, "best_threads": int(threads), "best_backend": str(backend), "ttft_ms": round(float(ttft_ms), 2), "tokens_per_second": round(float(tokens_per_second), 3), "updated_at": int(time.time())}
        tmp = PERF_STATE_PATH.with_suffix(".tmp"); tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8"); os.replace(tmp, PERF_STATE_PATH)
        self.cfg.threads = int(threads); self.cfg.accel_backend = str(backend); self.cfg.performance_tuned = True; save_config(self.cfg)


def get_local_runtime(cfg: Config, model_path: Callable[[], Path | None]) -> LocalRuntime:
    global _RUNTIME_SINGLETON
    with _RUNTIME_LOCK:
        if _RUNTIME_SINGLETON is None:
            _RUNTIME_SINGLETON = LocalRuntime(cfg, model_path)
        else:
            _RUNTIME_SINGLETON.update_config(cfg, model_path)
        return _RUNTIME_SINGLETON
