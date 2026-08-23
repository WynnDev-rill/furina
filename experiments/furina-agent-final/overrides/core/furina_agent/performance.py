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


def _find_server() -> str | None:
    return os.environ.get("FURINA_LLAMA_SERVER") or shutil.which("llama-server")


def _candidate_backends() -> list[str]:
    # CPU is mandatory. Accelerators are best-effort and only considered when
    # a matching llama.cpp build/backend appears to exist on-device.
    result = ["cpu"]
    if os.environ.get("FURINA_ENABLE_OPENCL") == "1":
        result.append("opencl")
    if os.environ.get("FURINA_ENABLE_VULKAN") == "1":
        result.append("vulkan")
    return result


def tune_local_runtime(cfg: Config, model: Path) -> dict:
    """Benchmark a tiny prompt and persist the fastest healthy profile.

    This is intentionally opt-in: it should run after a model download or from
    Settings, never on every `furina` launch. If a backend fails, it is skipped
    and CPU remains available.
    """
    server = _find_server()
    if not server or not model.exists():
        return {"ok": False, "reason": "llama-server/model tidak tersedia"}

    candidates: list[dict] = []
    base_port = 18080
    prompt = {
        "model": "local",
        "messages": [{"role": "user", "content": "Jawab hanya: siap"}],
        "max_tokens": 8,
        "stream": True,
        "temperature": 0.1,
    }

    for backend_index, backend in enumerate(_candidate_backends()):
        for threads in (4, 5, 6):
            port = base_port + backend_index * 10 + threads
            cmd = [
                server,
                "--host", "127.0.0.1",
                "--port", str(port),
                "--model", str(model),
                "--ctx-size", "2048",
                "--threads", str(threads),
                "--threads-batch", str(threads),
                "--batch-size", "512",
                "--ubatch-size", "128",
                "--parallel", "1",
                "--cont-batching",
                "--cache-reuse", "256",
                "--flash-attn", "auto",
                "--n-gpu-layers", "0" if backend == "cpu" else "999",
            ]
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
                chars = 0
                try:
                    with urllib.request.urlopen(req, timeout=25) as r:
                        for raw in r:
                            if raw.startswith(b"data:"):
                                if not first:
                                    first = time.monotonic()
                                chars += len(raw)
                                if b"[DONE]" in raw:
                                    break
                except Exception:
                    first = 0.0
                elapsed = max(0.001, time.monotonic() - start)
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
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
                        "throughput_proxy": chars / elapsed,
                    })

    if not candidates:
        return {"ok": False, "reason": "tidak ada profil benchmark yang sehat"}

    # TTFT dominates companion UX; use the throughput proxy only as a tie break.
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
