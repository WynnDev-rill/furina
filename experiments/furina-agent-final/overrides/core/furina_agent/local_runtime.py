from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.error
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


class LocalRuntime:
    """Own the local llama-server lifecycle without blocking the chat surface.

    Product rule: loading is allowed to be expensive, waiting in silence is not.
    The runtime can be prepared in the background as soon as Local is selected,
    remains warm for a bounded idle window and is restarted only when its model
    or performance profile changes.
    """

    def __init__(self, cfg: Config, model_path: Callable[[], Path | None]):
        self.cfg = cfg
        self._model_path = model_path
        self._proc: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._last_use = 0.0
        self._model_loaded = ""
        self._generation = 0
        self.status = RuntimeStatus()
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        self._watchdog = threading.Thread(target=self._idle_watchdog, daemon=True, name="furina-local-idle")
        self._watchdog.start()

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.llama_host}:{self.cfg.llama_port}"

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
                self.touch()
                return
            generation = self._generation = self._generation + 1
            threading.Thread(
                target=self._start_worker,
                args=(generation,),
                daemon=True,
                name="furina-local-prewarm",
            ).start()

    def ensure_ready(self, *, timeout: float = 45.0, status_cb: Callable[[str], None] | None = None) -> bool:
        if self.health():
            self.status.state = "ready"
            self.touch()
            return True
        self.prewarm()
        started = time.monotonic()
        last_note = 0.0
        while time.monotonic() - started < timeout:
            if self._ready.wait(0.15):
                self.touch()
                return self.health(timeout=0.7)
            now = time.monotonic()
            if status_cb and now - last_note > 0.7:
                status_cb("Menyiapkan model lokal…")
                last_note = now
            with self._lock:
                if self._proc and self._proc.poll() is not None and self.status.state == "error":
                    return False
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
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _start_worker(self, generation: int) -> None:
        model = self._model_path()
        if not model or not model.exists():
            with self._lock:
                if generation == self._generation:
                    self.status = RuntimeStatus(state="error", detail="Model lokal belum diunduh")
            return

        with self._lock:
            if generation != self._generation:
                return
            if self._proc and self._proc.poll() is None:
                return
            self._ready.clear()
            self.status = RuntimeStatus(
                state="loading",
                detail="Menyiapkan model lokal…",
                started_at=time.time(),
                backend=self._choose_backend(),
                threads=self.cfg.threads,
            )

        cmd = self._server_command(model, self.status.backend)
        log_path = RUN_DIR / "llama-server.log"
        log = log_path.open("ab", buffering=0)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, "OMP_NUM_THREADS": str(self.cfg.threads)},
            )
        except Exception as exc:
            log.close()
            with self._lock:
                if generation == self._generation:
                    self.status = RuntimeStatus(state="error", detail=f"llama-server gagal dimulai: {exc}")
            return

        with self._lock:
            if generation != self._generation:
                try:
                    proc.terminate()
                except Exception:
                    pass
                log.close()
                return
            self._proc = proc
            self._model_loaded = str(model)

        # llama.cpp model load should normally finish well below this on a 1.7B
        # model. Fail quickly enough that the UI can present a useful error,
        # rather than reproducing the old multi-minute silent wait.
        deadline = time.monotonic() + 42.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if self.health(timeout=0.6):
                with self._lock:
                    if generation == self._generation:
                        self.status.state = "ready"
                        self.status.detail = "Siap"
                        self.status.ready_at = time.time()
                        self._ready.set()
                        self.touch()
                return
            time.sleep(0.18)

        with self._lock:
            if generation == self._generation:
                self.status.state = "error"
                self.status.detail = "Model lokal terlalu lama disiapkan"
        try:
            proc.terminate()
        except Exception:
            pass

    def _server_command(self, model: Path, backend: str) -> list[str]:
        binary = os.environ.get("FURINA_LLAMA_SERVER") or shutil.which("llama-server") or "llama-server"
        cmd = [
            binary,
            "--host", self.cfg.llama_host,
            "--port", str(self.cfg.llama_port),
            "--model", str(model),
            "--ctx-size", str(self.cfg.context_size),
            "--threads", str(self.cfg.threads),
            "--threads-batch", str(self.cfg.threads),
            "--batch-size", str(self.cfg.batch_size),
            "--ubatch-size", str(self.cfg.ubatch_size),
            "--parallel", "1",
            "--cont-batching",
            "--cache-reuse", str(self.cfg.cache_reuse),
            "--prio", str(self.cfg.server_priority),
        ]
        if self.cfg.cpu_mask:
            cmd += ["--cpu-mask", self.cfg.cpu_mask]
            if self.cfg.cpu_strict:
                cmd += ["--cpu-strict", "1"]
        if self.cfg.flash_attention == "on":
            cmd += ["--flash-attn", "on"]
        elif self.cfg.flash_attention == "off":
            cmd += ["--flash-attn", "off"]
        else:
            cmd += ["--flash-attn", "auto"]

        # Backend selection is intentionally conservative. Furina only opts in
        # after a local benchmark has marked a backend as faster and healthy.
        # CPU therefore remains a dependable fallback on every phone.
        if backend == "cpu":
            cmd += ["--n-gpu-layers", "0"]
        else:
            cmd += ["--n-gpu-layers", "999"]
        return cmd

    def _choose_backend(self) -> str:
        requested = self.cfg.accel_backend
        if requested in {"cpu", "opencl", "vulkan"}:
            return requested
        try:
            raw = json.loads(PERF_STATE_PATH.read_text(encoding="utf-8"))
            backend = str(raw.get("best_backend") or "cpu")
            if backend in {"cpu", "opencl", "vulkan"}:
                return backend
        except Exception:
            pass
        return "cpu"

    def _idle_watchdog(self) -> None:
        while not self._stop.wait(5.0):
            if self.cfg.keep_warm_seconds <= 0:
                continue
            with self._lock:
                alive = bool(self._proc and self._proc.poll() is None)
                last = self._last_use
            if alive and last and time.monotonic() - last > self.cfg.keep_warm_seconds:
                self.stop()


class LocalPerformanceTuner:
    """Cheap, device-local tuner for thread count and optional accelerators.

    The benchmark intentionally measures time-to-first-byte against the exact
    installed model. It runs only on explicit setup/benchmark paths and stores
    the winner so normal chat never pays this cost.
    """

    def __init__(self, cfg: Config, runtime: LocalRuntime):
        self.cfg = cfg
        self.runtime = runtime

    def record_profile(self, *, threads: int, backend: str, ttft_ms: float, tokens_per_second: float = 0.0) -> None:
        PERF_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 2,
            "best_threads": int(threads),
            "best_backend": str(backend),
            "ttft_ms": round(float(ttft_ms), 2),
            "tokens_per_second": round(float(tokens_per_second), 3),
            "updated_at": int(time.time()),
        }
        tmp = PERF_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, PERF_STATE_PATH)
        self.cfg.threads = int(threads)
        self.cfg.accel_backend = str(backend)
        self.cfg.performance_tuned = True
        save_config(self.cfg)
