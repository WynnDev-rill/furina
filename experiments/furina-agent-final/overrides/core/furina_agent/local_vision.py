from __future__ import annotations

import atexit
import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from .config import HOME, LOG_DIR, Config
from .llm import sanitize


class LocalVisionError(RuntimeError):
    pass


class LocalVision:
    """On-demand local screenshot understanding through llama.cpp/libmtmd."""

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
        return Path(self.cfg.vision_model_path).expanduser()

    @property
    def mmproj_path(self) -> Path:
        return Path(self.cfg.vision_mmproj_path).expanduser()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{int(self.cfg.vision_port)}"

    def available(self) -> bool:
        return bool(
            self.cfg.local_vision_enabled
            and self.executable.is_file()
            and self.model_path.is_file()
            and self.mmproj_path.is_file()
        )

    def _health(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=1.3) as r:
                return 200 <= int(r.status) < 300
        except Exception:
            return False

    def _cancel_idle_stop(self) -> None:
        if self._idle_timer:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _schedule_idle_stop(self) -> None:
        with self.lock:
            self._cancel_idle_stop()
            self._idle_timer = threading.Timer(max(20, int(self.cfg.vision_idle_seconds)), self.stop)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _start(self) -> None:
        # An old idle timer must never be allowed to terminate the server while
        # a new inference is starting or already in flight.
        with self.lock:
            self._cancel_idle_stop()
            if self._health():
                return
            if not self.available():
                raise LocalVisionError("local vision model belum tersedia")
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            self._log_handle = (LOG_DIR / "vision-sidecar.log").open("ab", buffering=0)
            cmd = [
                str(self.executable),
                "-m", str(self.model_path),
                "--mmproj", str(self.mmproj_path),
                "--port", str(int(self.cfg.vision_port)),
                "-c", "2048",
                "-b", "512",
                "-ub", "512",
                "-t", str(max(1, min(int(self.cfg.vision_threads), 6))),
            ]
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=self._log_handle,
                    stderr=self._log_handle,
                    start_new_session=True,
                )
            except Exception as exc:
                raise LocalVisionError(f"gagal memulai local vision: {exc}") from exc
            deadline = time.monotonic() + 22.0
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise LocalVisionError("local vision berhenti saat startup")
                if self._health():
                    return
                time.sleep(0.3)
            self.stop()
            raise LocalVisionError("local vision timeout saat startup")

    def analyze(self, prompt: str, png_base64: str, *, max_tokens: int = 420, json_mode: bool = True) -> str:
        if not png_base64 or not self.available():
            raise LocalVisionError("local vision tidak tersedia")
        self._start()
        try:
            payload = {
                "model": "local-vision",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png_base64}},
                        ],
                    }
                ],
                "max_tokens": int(max_tokens),
                "temperature": 0.0,
                "stream": False,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(
                self.base_url + "/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=150) as r:
                    raw = json.loads(r.read().decode("utf-8", errors="replace"))
            except Exception as first:
                if json_mode:
                    payload.pop("response_format", None)
                    req = urllib.request.Request(
                        self.base_url + "/v1/chat/completions",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=150) as r:
                            raw = json.loads(r.read().decode("utf-8", errors="replace"))
                    except Exception as second:
                        raise LocalVisionError(str(second)) from second
                else:
                    raise LocalVisionError(str(first)) from first
            try:
                text = raw["choices"][0]["message"]["content"]
            except Exception as exc:
                raise LocalVisionError("format respons local vision tidak dikenali") from exc
            text = sanitize(str(text or ""))
            if not text:
                raise LocalVisionError("local vision mengembalikan respons kosong")
            return text
        finally:
            # Idle countdown starts only after the request has completely
            # finished (success or failure), never while inference is running.
            self._schedule_idle_stop()

    def stop(self) -> None:
        with self.lock:
            self._cancel_idle_stop()
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
