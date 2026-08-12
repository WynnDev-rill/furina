from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _battery() -> dict:
    # Prefer direct sysfs reads: they are effectively free and cannot block on
    # a missing Termux:API companion app.
    base = "/sys/class/power_supply/battery"
    capacity = _read(base + "/capacity")
    status = _read(base + "/status")
    temp = _read(base + "/temp")
    if capacity or status or temp:
        out: dict = {"status": status or None}
        try:
            out["percent"] = int(capacity)
        except Exception:
            out["percent"] = None
        try:
            value = float(temp)
            out["temperature_c"] = value / 10.0 if value > 80 else value
        except Exception:
            out["temperature_c"] = None
        return out

    # Optional richer fallback when Termux:API is actually installed.
    command = shutil.which("termux-battery-status")
    if command:
        try:
            result = subprocess.run([command], capture_output=True, text=True, timeout=0.7, check=False)
            if result.returncode == 0:
                obj = json.loads(result.stdout)
                return {
                    "percent": obj.get("percentage"),
                    "status": obj.get("status"),
                    "temperature_c": obj.get("temperature"),
                }
        except Exception:
            pass
    return {"percent": None, "status": None, "temperature_c": None}


def _memory() -> dict:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(value.strip().split()[0]) * 1024
    except Exception:
        pass
    return {"total": values.get("MemTotal"), "available": values.get("MemAvailable")}


def _networks() -> list[str]:
    active: list[str] = []
    root = Path("/sys/class/net")
    try:
        for item in root.iterdir():
            if item.name == "lo":
                continue
            if _read(str(item / "operstate")) == "up":
                active.append(item.name)
    except Exception:
        pass
    return active[:6]


def snapshot(store, cache_seconds: int = 30) -> dict:
    now = time.time()
    cached = store.get_state("device_sensor_snapshot", {})
    if isinstance(cached, dict) and now - float(cached.get("at", 0) or 0) < cache_seconds:
        return cached
    try:
        usage = shutil.disk_usage(Path.home())
        storage = {"free": usage.free, "total": usage.total}
    except Exception:
        storage = {}
    try:
        uptime = float(_read("/proc/uptime").split()[0])
    except Exception:
        uptime = None
    data = {
        "at": now,
        "local_time": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(now)),
        "battery": _battery(),
        "memory": _memory(),
        "storage": storage,
        "network_interfaces": _networks(),
        "uptime_seconds": uptime,
        "foreground_package": str(store.get_state("device_foreground_package", "") or ""),
    }
    store.set_state("device_sensor_snapshot", data)
    return data


def context_text(store) -> str:
    data = snapshot(store)
    lines = [f"waktu perangkat: {data.get('local_time')}"]
    battery = data.get("battery") or {}
    if battery.get("percent") is not None:
        suffix = f", {battery.get('status')}" if battery.get("status") else ""
        lines.append(f"baterai: {battery.get('percent')}%{suffix}")
    memory = data.get("memory") or {}
    if memory.get("available") and memory.get("total"):
        lines.append(
            f"RAM tersedia: {round(memory['available'] / 1073741824, 1)} / {round(memory['total'] / 1073741824, 1)} GB"
        )
    storage = data.get("storage") or {}
    if storage.get("free") and storage.get("total"):
        lines.append(f"storage bebas: {round(storage['free'] / 1073741824, 1)} GB")
    networks = data.get("network_interfaces") or []
    if networks:
        lines.append("network aktif: " + ", ".join(networks))
    if data.get("foreground_package"):
        lines.append("app terbaru: " + str(data["foreground_package"]))
    return "\n".join(lines[:6])
