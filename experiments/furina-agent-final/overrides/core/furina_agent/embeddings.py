from __future__ import annotations

import atexit
import json
import math
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import HOME, LOG_DIR, RUN_DIR, Config


class EmbeddingError(RuntimeError):
    pass


class LocalEmbeddingEngine:
    """Lazy local embedding sidecar backed by llama.cpp.

    It is started only when semantic recall is needed and is stopped after a
    short idle period. This keeps hybrid memory local without keeping another
    model hot all day.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._idle_timer: threading.Timer | None = None
        self._log_handle = None
        atexit.register(self.stop)

    @property
    def executable(self) -> Path:
        return HOME / "llama.cpp" / "build" / "bin" / "llama-server"

    @property
    def model_path(self) -> Path:
        return Path(self.cfg.embedding_model_path).expanduser()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{int(self.cfg.embedding_port)}"

    def available(self) -> bool:
        return bool(self.cfg.embedding_enabled and self.executable.is_file() and self.model_path.is_file())

    def _health(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=1.3) as r:
                return 200 <= int(r.status) < 300
        except Exception:
            return False

    def _schedule_idle_stop(self) -> None:
        if self._idle_timer:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(max(20, int(self.cfg.embedding_idle_seconds)), self.stop)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _start(self) -> None:
        if self._health():
            self._schedule_idle_stop()
            return
        if not self.available():
            raise EmbeddingError("local embedding model belum tersedia")
        with self.lock:
            if self._health():
                self._schedule_idle_stop()
                return
            RUN_DIR.mkdir(parents=True, exist_ok=True)
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log = LOG_DIR / "embedding-sidecar.log"
            self._log_handle = log.open("ab", buffering=0)
            cmd = [
                str(self.executable),
                "-m", str(self.model_path),
                "--embedding",
                "--pooling", "mean",
                "--port", str(int(self.cfg.embedding_port)),
                "-c", "512",
                "-b", "512",
                "-ub", "512",
                "-t", str(max(1, min(int(self.cfg.embedding_threads), 4))),
            ]
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=self._log_handle,
                    stderr=self._log_handle,
                    start_new_session=True,
                )
            except Exception as exc:
                raise EmbeddingError(f"gagal memulai embedding sidecar: {exc}") from exc
            deadline = time.monotonic() + 18.0
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise EmbeddingError("embedding sidecar berhenti saat startup")
                if self._health():
                    self._schedule_idle_stop()
                    return
                time.sleep(0.25)
            self.stop()
            raise EmbeddingError("embedding sidecar timeout saat startup")

    @staticmethod
    def _extract_vector(raw) -> list[float] | None:
        candidate = None
        if isinstance(raw, dict):
            if isinstance(raw.get("embedding"), list):
                candidate = raw.get("embedding")
            data = raw.get("data")
            if candidate is None and isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                    candidate = first.get("embedding")
                elif isinstance(first, list):
                    candidate = first
        elif isinstance(raw, list) and raw:
            first = raw[0]
            if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                candidate = first.get("embedding")
            elif isinstance(first, list):
                candidate = first
            elif all(isinstance(x, (int, float)) for x in raw):
                candidate = raw
        if not isinstance(candidate, list) or len(candidate) < 16:
            return None
        try:
            vec = [float(x) for x in candidate]
        except Exception:
            return None
        norm = math.sqrt(sum(x * x for x in vec))
        if norm <= 1e-12:
            return None
        return [x / norm for x in vec]

    def embed(self, text: str) -> list[float] | None:
        text = " ".join(str(text or "").split())[:1800]
        if len(text) < 2 or not self.available():
            return None
        try:
            self._start()
            payload = json.dumps({"input": text, "embd_normalize": 2}).encode("utf-8")
            req = urllib.request.Request(
                self.base_url + "/embedding",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = json.loads(r.read().decode("utf-8", errors="replace"))
            self._schedule_idle_stop()
            return self._extract_vector(raw)
        except (EmbeddingError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return None
        except Exception:
            return None

    def stop(self) -> None:
        with self.lock:
            if self._idle_timer:
                self._idle_timer.cancel()
                self._idle_timer = None
            proc = self._process
            self._process = None
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2.5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if self._log_handle:
                try:
                    self._log_handle.close()
                except Exception:
                    pass
                self._log_handle = None
