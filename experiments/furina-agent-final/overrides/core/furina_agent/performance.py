from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from .config import Config, PERF_STATE_PATH, save_config


def _binary(backend: str) -> str | None:
    key = {"cpu": "FURINA_LLAMA_SERVER", "opencl": "FURINA_LLAMA_SERVER_OPENCL", "vulkan": "FURINA_LLAMA_SERVER_VULKAN"}[backend]
    explicit = os.environ.get(key)
    if explicit and Path(explicit).exists():
        return explicit
    return shutil.which("llama-server") if backend == "cpu" else None


def _help(binary: str) -> str:
    try:
        p = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=4, check=False)
        return (p.stdout or "") + "\n" + (p.stderr or "")
    except Exception:
        return ""


def tune_local_runtime(cfg: Config, model: Path) -> dict:
    """Benchmark 4/5/6 CPU threads and any explicitly installed GPU builds.

    The exact selected GGUF is used. Accelerator candidates are never guessed:
    an OpenCL/Vulkan-specific llama-server binary must actually exist. CPU is
    therefore always the safe fallback.
    """
    if not model.exists():
        return {"ok": False, "reason": "model tidak tersedia"}
    backend_bins = [(b, _binary(b)) for b in ("cpu", "opencl", "vulkan")]
    backend_bins = [(b, p) for b, p in backend_bins if p]
    if not backend_bins:
        return {"ok": False, "reason": "llama-server tidak tersedia"}

    candidates: list[dict] = []
    prompt = {
        "model": "local",
        "messages": [{"role": "user", "content": "Jawab hanya: siap"}],
        "max_tokens": 12,
        "stream": True,
        "temperature": 0.1,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    for backend_index, (backend, server) in enumerate(backend_bins):
        help_text = _help(server)
        for threads in (4, 5, 6):
            port = 18080 + backend_index * 10 + threads
            cmd = [server, "--host", "127.0.0.1", "--port", str(port), "--model", str(model), "--ctx-size", "2048", "--threads", str(threads)]
            for flag, args in (
                ("--threads-batch", ["--threads-batch", str(threads)]),
                ("--batch-size", ["--batch-size", "512"]),
                ("--ubatch-size", ["--ubatch-size", "128"]),
                ("--parallel", ["--parallel", "1"]),
                ("--cache-reuse", ["--cache-reuse", "256"]),
            ):
                if flag in help_text:
                    cmd += args
            if "--cont-batching" in help_text:
                cmd.append("--cont-batching")
            if "--flash-attn" in help_text:
                cmd += ["--flash-attn", "auto"]
            if "--n-gpu-layers" in help_text:
                cmd += ["--n-gpu-layers", "0" if backend == "cpu" else "999"]
            with tempfile.TemporaryFile() as log:
                try:
                    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                except Exception:
                    continue
                ready = False
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.3) as r:
                            ready = 200 <= r.status < 300
                    except Exception:
                        ready = False
                    if ready:
                        break
                    time.sleep(0.15)
                if not ready:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    continue
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/v1/chat/completions",
                    data=json.dumps(prompt).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                start = time.monotonic()
                first = 0.0
                payload_bytes = 0
                try:
                    with urllib.request.urlopen(req, timeout=25) as r:
                        for raw in r:
                            if raw.startswith(b"data:"):
                                if not first:
                                    first = time.monotonic()
                                payload_bytes += len(raw)
                                if b"[DONE]" in raw:
                                    break
                except Exception:
                    first = 0.0
                elapsed = max(0.001, time.monotonic() - start)
                try:
                    proc.terminate(); proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                if first:
                    candidates.append({
                        "backend": backend,
                        "threads": threads,
                        "ttft_ms": (first - start) * 1000.0,
                        "throughput_proxy": payload_bytes / elapsed,
                    })
    if not candidates:
        return {"ok": False, "reason": "tidak ada profil benchmark yang sehat"}
    winner = min(candidates, key=lambda x: (x["ttft_ms"], -x["throughput_proxy"]))
    cfg.threads = int(winner["threads"])
    cfg.accel_backend = str(winner["backend"])
    cfg.performance_tuned = True
    save_config(cfg)
    PERF_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERF_STATE_PATH.write_text(json.dumps({
        "schema": 2,
        "best_backend": cfg.accel_backend,
        "best_threads": cfg.threads,
        "ttft_ms": round(winner["ttft_ms"], 2),
        "throughput_proxy": round(winner["throughput_proxy"], 2),
        "candidates": candidates,
        "updated_at": int(time.time()),
    }, indent=2), encoding="utf-8")
    return {"ok": True, "winner": winner, "candidates": candidates}
