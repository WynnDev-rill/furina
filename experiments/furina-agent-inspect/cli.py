from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .agent import AndroidAgent
from .bridge import AndroidBridge
from .companion import CompanionSession
from .config import HOME, LOG_DIR, RUN_DIR, load_config, save_config
from .version import VERSION
from .llm import LocalLLM
from .memory import MemoryStore
from .providers import PROVIDER_LABELS, OpenAICompatibleProvider, ProviderSecrets
from .routing import RoutingLLM
from .server import run_server


def _pidfile(name: str) -> Path:
    return RUN_DIR / f"{name}.pid"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid(name: str) -> int | None:
    p = _pidfile(name)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
        return pid if _alive(pid) else None
    except Exception:
        return None


def _spawn(name: str, argv: list[str]) -> int:
    existing = _read_pid(name)
    if existing:
        return existing
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"{name}.log", "ab", buffering=0)
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    _pidfile(name).write_text(str(proc.pid))
    return proc.pid


def cmd_pair(args):
    # Backward-compatible manual recovery command. Normal setup uses auto-pair.
    cfg = load_config()
    cfg.bridge_token = args.token.strip()
    save_config(cfg)
    print("Bridge token tersimpan (manual recovery).")


def cmd_connect(_args):
    cfg = load_config()
    bridge = AndroidBridge(cfg)
    try:
        health = bridge.health()
        print(f"Bridge v{health.get('version', '?')} terdeteksi.")
    except Exception as exc:
        raise SystemExit(f"Bridge belum aktif: {exc}")
    if bridge.ensure_paired():
        print("Termux ↔ Furina Bridge terhubung otomatis. Tidak ada kode pairing yang perlu disalin.")
        return
    raise SystemExit("Auto-connect belum dibuka. Buka aplikasi Furina Bridge sebentar, lalu jalankan `furina connect` lagi.")


def cmd_model(args):
    cfg = load_config()
    p = Path(args.path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"Model tidak ditemukan: {p}")
    cfg.model_path = str(p)
    save_config(cfg)
    print(f"Model: {p}")


def find_llama_server() -> str:
    candidates = [
        HOME / "llama.cpp" / "build" / "bin" / "llama-server",
        Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    from shutil import which
    found = which("llama-server")
    if found:
        return found
    raise SystemExit("llama-server belum ditemukan. Jalankan kembali install.sh atau build llama.cpp.")


def _server_help(binary: str) -> str:
    try:
        return subprocess.run([binary, "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8).stdout
    except Exception:
        return ""


def cmd_start(_args):
    cfg = load_config()
    from shutil import which
    if which("termux-wake-lock"):
        subprocess.run(["termux-wake-lock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not cfg.model_path or not Path(cfg.model_path).exists():
        raise SystemExit("Model belum dikonfigurasi. Jalankan setup/update final atau: furina model /path/model.gguf")
    llama = find_llama_server()
    help_text = _server_help(llama)
    argv = [
        llama,
        "-m", cfg.model_path,
        "-c", str(cfg.context_size),
        "-t", str(cfg.threads),
        "--host", cfg.llama_host,
        "--port", str(cfg.llama_port),
        "--parallel", "1",
        "--jinja",
    ]
    # Only pass flags that the pinned runtime actually advertises. This keeps
    # updates compatible while enabling assistant-oriented prompt cache reuse.
    if "--threads-batch" in help_text:
        argv += ["--threads-batch", str(cfg.threads)]
    if "--cache-reuse" in help_text and cfg.cache_reuse > 0:
        argv += ["--cache-reuse", str(cfg.cache_reuse)]
    if "--keep" in help_text:
        argv += ["--keep", "-1"]
    if "--flash-attn" in help_text:
        argv += ["--flash-attn", "auto"]
    if "--prio" in help_text:
        argv += ["--prio", str(cfg.server_priority)]
    # Qwen3/3.5 thinking can consume a large fraction of generation time for
    # casual companion chat. Default final mode is non-thinking; users can
    # toggle it in Settings. Prefer the current server flag when available.
    if not cfg.local_reasoning:
        if "--reasoning " in help_text or "--reasoning [" in help_text:
            argv += ["--reasoning", "off"]
        elif "--reasoning-budget" in help_text:
            argv += ["--reasoning-budget", "0"]
    if cfg.cpu_mask and "--cpu-mask" in help_text:
        argv += ["--cpu-mask", cfg.cpu_mask]
        if cfg.cpu_strict and "--cpu-strict" in help_text:
            argv += ["--cpu-strict", "1"]
        if "--cpu-mask-batch" in help_text:
            argv += ["--cpu-mask-batch", cfg.cpu_mask]
        if cfg.cpu_strict and "--cpu-strict-batch" in help_text:
            argv += ["--cpu-strict-batch", "1"]

    llama_pid = _spawn("llama", argv)
    print(f"llama-server PID {llama_pid}")
    llm = LocalLLM(cfg)
    for _ in range(150):
        if llm.health():
            break
        time.sleep(1)
    else:
        raise SystemExit(f"llama-server gagal siap. Lihat {LOG_DIR / 'llama.log'}")
    core_pid = _spawn("core", [sys.executable, "-m", "furina_agent.cli", "serve"])
    print(f"Furina Core PID {core_pid}")
    print(f"API lokal: http://{cfg.core_host}:{cfg.core_port}")


def cmd_stop(_args):
    for name in ("core", "llama"):
        pid = _read_pid(name)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
            except Exception:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            print(f"{name}: stop PID {pid}")
        _pidfile(name).unlink(missing_ok=True)
    from shutil import which
    if which("termux-wake-unlock"):
        subprocess.run(["termux-wake-unlock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cmd_status(_args):
    cfg = load_config()
    local = LocalLLM(cfg)
    bridge = AndroidBridge(cfg)
    secrets = ProviderSecrets()
    status = {
        "version": VERSION,
        "home": str(HOME),
        "nickname": cfg.user_nickname or None,
        "routing_mode": cfg.routing_mode,
        "online_providers": secrets.configured(),
        "model": cfg.model_path or None,
        "llama_pid": _read_pid("llama"),
        "core_pid": _read_pid("core"),
        "llama_ready": local.health(),
        "bridge_authenticated": bool(cfg.bridge_token),
    }
    try:
        status["bridge"] = bridge.health()
    except Exception as e:
        status["bridge"] = {"ok": False, "error": str(e)}
    print(json.dumps(status, indent=2, ensure_ascii=False))


def _terminal_approve(summary, action, risk, detail):
    print(f"\nRencana: {summary}\nRisk: {risk} • {detail}\nAksi: {json.dumps(action, ensure_ascii=False)}")
    return input("Izinkan? [y/N] ").strip().lower() in {"y", "yes", "ya"}


def _chat_once(session: CompanionSession, llm: RoutingLLM, text: str) -> str:
    intent = session.classify(text)
    if intent.mode == "device":
        if not sys.stdin.isatty():
            return "Perintah Android membutuhkan sesi interaktif untuk persetujuan. Jalankan `furina` lalu gunakan menu Chat."
        ok = input(f"Tugas Android terdeteksi: {intent.goal}\nIzinkan navigasi+input untuk tugas ini? [y/N] ").strip().lower() in {"y", "yes", "ya"}
        if not ok:
            return "Kontrol Android dibatalkan."
        return session.agent.run(intent.goal, _terminal_approve, task_authorized=True)
    return session.chat.respond(text)


def cmd_chat(args):
    cfg = load_config()
    llm = RoutingLLM(cfg)
    session = CompanionSession(cfg, MemoryStore(), llm)
    if args.message:
        print(_chat_once(session, llm, " ".join(args.message)))
        return
    print("Furina chat + Android agent. /exit untuk keluar.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text in {"/exit", "/quit"}:
            return
        if text:
            print("furina> " + _chat_once(session, llm, text))


def cmd_screen(_args):
    print(json.dumps(AndroidBridge(load_config()).screen(), indent=2, ensure_ascii=False))


def cmd_apps(_args):
    print(json.dumps(AndroidBridge(load_config()).apps(), indent=2, ensure_ascii=False))


def cmd_screenshot(args):
    out = Path(args.output).expanduser()
    AndroidBridge(load_config()).screenshot(out)
    print(out.resolve())


def cmd_agent(args):
    cfg = load_config()
    llm = RoutingLLM(cfg)
    agent = AndroidAgent(cfg, MemoryStore(), llm, AndroidBridge(cfg))
    task_authorized = bool(args.auto)
    if not task_authorized:
        task_authorized = input("Izinkan Furina menavigasi dan mengetik untuk tugas ini? [y/N] ").strip().lower() in {"y", "yes", "ya"}
    if not task_authorized:
        print("Dibatalkan.")
        return
    print(agent.run(" ".join(args.goal), _terminal_approve, task_authorized=True))


def cmd_memories(_args):
    for m in MemoryStore().list_memories():
        print(f"[{m.kind} {m.importance:.2f}] {m.text}")


def collect_doctor_checks():
    cfg = load_config()
    checks = []
    checks.append(("Python", sys.version.split()[0], True))
    try:
        llama = find_llama_server()
        checks.append(("llama-server", llama, True))
    except SystemExit as e:
        checks.append(("llama-server", str(e), False))
    model_exists = bool(cfg.model_path and Path(cfg.model_path).exists())
    local_required = cfg.routing_mode != "online"
    checks.append(("model", cfg.model_path or "belum diatur", model_exists or not local_required))
    configured = ProviderSecrets().configured()
    provider_detail = ", ".join(PROVIDER_LABELS[p] for p in configured) if configured else "none"
    providers_ok = True if cfg.routing_mode == "local" else bool(configured) or (cfg.routing_mode == "auto" and model_exists)
    checks.append(("AI routing", f"{cfg.routing_mode} • providers={provider_detail}", providers_ok))
    try:
        bridge = AndroidBridge(cfg)
        b = bridge.health()
        fg = bool(b.get("foreground", b.get("ok")))
        acc = bool(b.get("accessibility"))
        auth_ok = bridge.ensure_paired()
        checks.append(("bridge", json.dumps(b, ensure_ascii=False), fg and auth_ok))
        checks.append(("accessibility", "BOUND" if acc else "UNBOUND", acc))
    except Exception as e:
        checks.append(("bridge", str(e), False))
    checks.append(("nickname", cfg.user_nickname or "belum diatur", True))
    checks.append(("performance", f"threads={cfg.threads} mask={cfg.cpu_mask or 'scheduler'} tuned={cfg.performance_tuned}", True))
    return checks


def cmd_doctor(_args):
    for name, detail, ok in collect_doctor_checks():
        print(f"{'OK' if ok else 'FAIL':4} {name:14} {detail}")


def cmd_provider_status(_args):
    cfg = load_config()
    secrets = ProviderSecrets()
    print(f"Routing: {cfg.routing_mode}")
    for name, label in PROVIDER_LABELS.items():
        print(f"{label:12} {secrets.masked(name)}")
    print(f"OpenRouter free-only: {'ON' if cfg.provider_prefer_free else 'OFF'}")


def cmd_provider_test(args):
    cfg = load_config()
    key = ProviderSecrets().get(args.provider)
    if not key:
        raise SystemExit(f"API key {args.provider} belum diatur. Gunakan TUI: furina → AI Provider / API key")
    ok, detail = OpenAICompatibleProvider(args.provider, key, cfg).test()
    print(("OK " if ok else "FAIL ") + detail)
    if not ok:
        raise SystemExit(1)


def cmd_optimize(_args):
    from .performance import tune_threads
    cfg = load_config()
    was_running = LocalLLM(cfg).health()
    if was_running:
        cmd_stop(None)
    print("Benchmark CPU lokal dimulai. Ini hanya dilakukan saat diminta dan dapat memakan beberapa menit.")
    result = tune_threads(cfg)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if was_running or cfg.routing_mode == "local":
        cmd_start(None)


def cmd_repair(_args):
    cfg = load_config()
    bridge = AndroidBridge(cfg)
    print("Memeriksa Furina Bridge…")
    try:
        health = bridge.health()
        print(f"Bridge: v{health.get('version', '?')} • foreground={health.get('foreground')} • accessibility={health.get('accessibility')}")
    except Exception as exc:
        raise SystemExit(f"Bridge tidak dapat dijangkau: {exc}. Buka Furina Bridge dan pastikan Persistent Bridge aktif.")
    if bridge.ensure_paired():
        print("Auto-connect: OK")
    else:
        raise SystemExit("Buka Furina Bridge di layar selama beberapa detik lalu ulangi `furina repair`.")
    print("Repair selesai. Jalankan `furina doctor` untuk verifikasi lengkap.")


def cmd_update(_args):
    import urllib.request
    url = "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
    target = RUN_DIR / "furina-update.sh"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            target.write_bytes(r.read())
    except Exception as exc:
        raise SystemExit(f"Tidak dapat mengambil updater: {exc}")
    target.chmod(0o700)
    print("Menjalankan updater final…")
    raise SystemExit(subprocess.run(["bash", str(target), "--update"], check=False).returncode)


def cmd_ui(_args):
    from .tui import run_tui
    run_tui()


def cmd_setup(_args):
    from .tui import _rich, _setup, _header
    _, Console, _, _, _, _, _, _, _ = _rich()
    console = Console()
    _header(console)
    _setup(console)


def build_parser():
    p = argparse.ArgumentParser(
        prog="furina",
        description="Furina Agent by Wynn — local/online AI companion + permission-gated Android agent",
    )
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("pair"); sp.add_argument("token"); sp.set_defaults(func=cmd_pair)
    sp = sub.add_parser("connect"); sp.set_defaults(func=cmd_connect)
    sp = sub.add_parser("model"); sp.add_argument("path"); sp.set_defaults(func=cmd_model)
    sp = sub.add_parser("start"); sp.set_defaults(func=cmd_start)
    sp = sub.add_parser("stop"); sp.set_defaults(func=cmd_stop)
    sp = sub.add_parser("status"); sp.set_defaults(func=cmd_status)
    sp = sub.add_parser("chat"); sp.add_argument("message", nargs="*"); sp.set_defaults(func=cmd_chat)
    sp = sub.add_parser("screen"); sp.set_defaults(func=cmd_screen)
    sp = sub.add_parser("apps"); sp.set_defaults(func=cmd_apps)
    sp = sub.add_parser("screenshot"); sp.add_argument("output", nargs="?", default="furina-screen.png"); sp.set_defaults(func=cmd_screenshot)
    sp = sub.add_parser("agent"); sp.add_argument("--auto", action="store_true", help="approve ordinary navigation/input for this task; external Send still asks"); sp.add_argument("goal", nargs="+"); sp.set_defaults(func=cmd_agent)
    sp = sub.add_parser("memories"); sp.set_defaults(func=cmd_memories)
    sp = sub.add_parser("doctor"); sp.set_defaults(func=cmd_doctor)
    sp = sub.add_parser("providers"); sp.set_defaults(func=cmd_provider_status)
    sp = sub.add_parser("provider-test"); sp.add_argument("provider", choices=list(PROVIDER_LABELS)); sp.set_defaults(func=cmd_provider_test)
    sp = sub.add_parser("setup"); sp.set_defaults(func=cmd_setup)
    sp = sub.add_parser("optimize"); sp.set_defaults(func=cmd_optimize)
    sp = sub.add_parser("repair"); sp.set_defaults(func=cmd_repair)
    sp = sub.add_parser("update"); sp.set_defaults(func=cmd_update)
    sp = sub.add_parser("ui"); sp.set_defaults(func=cmd_ui)
    sp = sub.add_parser("serve"); sp.set_defaults(func=lambda _: run_server())
    return p


def main():
    args = build_parser().parse_args()
    if not getattr(args, "cmd", None):
        cmd_ui(args)
        return
    args.func(args)


if __name__ == "__main__":
    main()
