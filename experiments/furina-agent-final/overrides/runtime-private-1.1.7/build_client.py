#!/usr/bin/env python3
"""Build the transitional-compatible, Termux-only updater."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "runtime-private-1.1.6" / "build_client.py"
spec = importlib.util.spec_from_file_location("furina_116_builder", BASE)
if spec is None or spec.loader is None:
    raise SystemExit("base builder unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def replace_function(text: str, name: str, replacement: str) -> str:
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{name}: expected one top-level function, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start = sum(len(x) for x in lines[:node.lineno - 1])
    end = sum(len(x) for x in lines[:node.end_lineno])
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def build(base: Path, output: Path) -> None:
    module.module.build(base, output)
    text = output.read_text(encoding="utf-8")
    # Remove the obsolete APK decorator before AST replacement; otherwise the
    # generated client contains two top-level update() definitions.
    marker = "# FURINA_FINAL_113_APK_INSTALL_GATE"
    start = text.find(marker)
    end = text.find('\nif __name__ == "__main__":', start)
    if start >= 0 and end >= 0:
        text = text[:start] + "# FURINA_TERMUX_ONLY_NO_APK_SYNC\n" + text[end:]
    text = text.replace('CLIENT_VERSION = "1.2.0"', 'CLIENT_VERSION = "1.3.0"', 1)

    text = replace_function(text, "validate_channel", r'''def validate_channel(channel: dict) -> dict:
    if channel.get("schema") != 1 or channel.get("protocol") != PROTOCOL:
        raise RuntimeError("protokol channel update tidak kompatibel")
    for key in ("bundle_id", "core", "client"):
        if key not in channel: raise RuntimeError(f"metadata update tidak lengkap: {key}")
    for label, item, required in (
        ("core", channel["core"], ("version","revision","url","sha256","size")),
        ("client", channel["client"], ("version","url","sha256","size")),
    ):
        if not isinstance(item, dict): raise RuntimeError(f"metadata {label} tidak valid")
        missing=[name for name in required if not item.get(name)]
        if missing: raise RuntimeError(f"metadata {label} tidak lengkap: {', '.join(missing)}")
        if len(str(item["sha256"])) != 64: raise RuntimeError(f"sha256 {label} tidak valid")
    return channel''')

    text = replace_function(text, "installed_is_current", r'''def installed_is_current(root: Path, channel: dict) -> bool:
    installed=installed_bundle(root)
    return (installed.get("bundle_id")==channel["bundle_id"] and installed.get("core_sha256")==channel["core"]["sha256"] and parse_core_version(root)==channel["core"]["version"] and (root/"core/furina_agent/version.py").is_file())''')

    text = replace_function(text, "safe_extract", r'''def safe_extract(snapshot: Path, stage: Path) -> None:
    with tarfile.open(snapshot,"r:*") as archive:
        members=archive.getmembers()
        if not members: raise RuntimeError("snapshot kosong")
        for member in members:
            pure=PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0]!="core": raise RuntimeError(f"path snapshot tidak aman: {member.name}")
            if member.issym() or member.islnk() or member.isdev(): raise RuntimeError(f"tipe snapshot tidak aman: {member.name}")
        archive.extractall(stage,members=members)''')

    text = replace_function(text, "validate_stage", r'''def validate_stage(stage: Path, channel: dict) -> None:
    required=(stage/"core/furina_agent/version.py",stage/"core/furina_agent/memory.py",stage/"core/furina_agent/chat.py",stage/"core/furina_agent/tui.py",stage/"core/furina_agent/local_models.py")
    for path in required:
        if not path.is_file(): raise RuntimeError(f"snapshot Core tidak lengkap: {path.relative_to(stage)}")
    vt=required[0].read_text(encoding="utf-8")
    if f'VERSION = "{channel["core"]["version"]}"' not in vt or f'UPDATE_PROTOCOL = "{PROTOCOL}"' not in vt: raise RuntimeError("Core snapshot tidak cocok dengan channel")''')

    text = replace_function(text, "commit_snapshot", r'''def commit_snapshot(root: Path, stage: Path, channel: dict) -> None:
    rollback=root/"rollback"; rollback.mkdir(parents=True,exist_ok=True); old_core=rollback/"core.previous"; shutil.rmtree(old_core,ignore_errors=True)
    core=root/"core"; moved=False
    try:
        if core.exists(): os.replace(core,old_core); moved=True
        os.replace(stage/"core",core); validate_stage(root,channel)
    except Exception:
        shutil.rmtree(core,ignore_errors=True)
        if moved and old_core.exists(): os.replace(old_core,core)
        raise
    shutil.rmtree(old_core,ignore_errors=True)''')

    text = replace_function(text, "launcher_texts", r'''def launcher_texts(root: Path) -> dict[str,str]:
    update_py=root/"updater/update_client.py"; shell="#!/data/data/com.termux/files/usr/bin/bash\nset -euo pipefail\n"
    return {
      "furina":shell+'PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"\nif [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi\nexec "$PREFIX/bin/furina-real" "$@"\n',
      "furina-real":shell+'ROOT="$HOME/.furina-agent"\nexport FURINA_HOME="$ROOT"\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\nexec python -m furina_agent "$@"\n',
      "furina-hub":shell+'ROOT="$HOME/.furina-agent"\nexport FURINA_HOME="$ROOT"\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\nexec python -m furina_agent.hub "$@"\n',
      "furina-update":shell+f'CLIENT="{update_py}"\nif [[ ! -s "$CLIENT" ]]; then RECOVERY="$HOME/.furina-agent/run/furina-install.sh"; mkdir -p "$(dirname "$RECOVERY")"; curl -fsSL --retry 4 --retry-all-errors "{DEFAULT_CHANNEL.rsplit("/",1)[0]}/furina-install.sh" -o "$RECOVERY"; exec bash "$RECOVERY" --update "$@"; fi\nexec python "$CLIENT" update "$@"\n',
      "furina-apk-confirm":shell+f'exec python "{update_py}" confirm-apk "$@"\n',
      "hapus":shell+f'if [[ "${{1:-}}" != "furina" ]]; then echo "Gunakan: hapus furina" >&2; exit 2; fi\nshift\nexec python "{update_py}" uninstall "$@"\n',
    }''')

    text = replace_function(text, "install_launchers", r'''def install_launchers(root: Path) -> None:
    bindir=prefix_dir()/"bin"; bindir.mkdir(parents=True,exist_ok=True)
    for name,text in launcher_texts(root).items(): atomic_text(bindir/name,text,0o755)
    for retired in ("furina-update-apk",):
        try: (bindir/retired).unlink()
        except OSError: pass''')

    text = replace_function(text, "update", r'''def update(args: argparse.Namespace) -> int:
    # FURINA_TERMUX_ONLY_UPDATER_116
    root=root_dir(); root.mkdir(parents=True,exist_ok=True); (root/"data").mkdir(parents=True,exist_ok=True); (root/"logs").mkdir(parents=True,exist_ok=True)
    source=os.environ.get("FURINA_UPDATE_SOURCE","termux"); state=State(root,source)
    with acquire_lock(root),tempfile.TemporaryDirectory(prefix="furina-update-") as td:
        work=Path(td); channel=None
        try:
            state.progress(3,"checking","Memeriksa channel update Furina")
            channel=load_channel(work,args.channel_file); maybe_reexec(root,channel,work,sys.argv[1:]); install_launchers(root)
            changed=install_core(root,channel,work,state,force=args.force or args.command=="repair")
            install_launchers(root)
            message="Pembaruan Core selesai" if changed else "Tidak ada pembaruan terbaru"
            state.write(state="done",result="updated" if changed else "no_update",stage="done",percent=100,message=message,channel=channel)
            print(f"PROGRESS 100 {message}"); return 0
        except Exception as exc:
            state.write(state="error",result="error",message=f"Pembaruan gagal: {exc}",channel=channel); print(f"ERROR {state.stage} {exc}",file=sys.stderr); return 1''')

    text = replace_function(text, "status", r'''def status(args: argparse.Namespace) -> int:
    root=root_dir(); print(json.dumps({"protocol":PROTOCOL,"client_version":CLIENT_VERSION,"surface":"termux","core_version":parse_core_version(root),"installed_bundle":installed_bundle(root)},ensure_ascii=False,indent=2)); return 0''')

    text = replace_function(text, "build_parser", r'''def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="furina-update"); sub=parser.add_subparsers(dest="command")
    for name in ("update","repair"):
        p=sub.add_parser(name); p.add_argument("--channel-file"); p.add_argument("--force",action="store_true")
    confirm=sub.add_parser("confirm-apk"); confirm.add_argument("bundle_id")
    uninstall=sub.add_parser("uninstall"); uninstall.add_argument("--yes",action="store_true")
    sub.add_parser("status"); return parser''')

    compile(text,str(output),"exec"); output.write_text(text,encoding="utf-8"); output.chmod(0o755)


def main() -> int:
    if len(sys.argv) not in {2,3}:
        print(f"usage: {sys.argv[0]} [base-update-client.py] OUTPUT",file=sys.stderr); return 2
    base,output=(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve()) if len(sys.argv)==3 else (module.module.module.module.module.DEFAULT_BASE,Path(sys.argv[1]).resolve())
    build(base,output); print("FURINA_TERMUX_116_UPDATER_BUILD_OK"); return 0


if __name__=="__main__": raise SystemExit(main())
