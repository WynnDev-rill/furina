#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

PROTOCOL = "furina-update/1"
CLIENT_VERSION = "1.0.0"
STATE_SCHEMA = 7
DEFAULT_CHANNEL = "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/channel.json"
OPENCONNECTOR_REPOSITORY = "https://github.com/oomol-lab/open-connector.git"
OPENCONNECTOR_COMMIT = "d478400141c33bb5ddf823e09b293e9d7154da97"
MAX_CHANNEL_BYTES = 256 * 1024
MAX_CLIENT_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024
MAX_APK_BYTES = 256 * 1024 * 1024


def root_dir() -> Path:
    return Path(os.environ.get("FURINA_HOME") or (Path.home() / ".furina-agent")).expanduser().resolve()


def prefix_dir() -> Path:
    return Path(os.environ.get("PREFIX") or "/data/data/com.termux/files/usr").expanduser().resolve()


def test_mode() -> bool:
    return os.environ.get("FURINA_TEST_MODE") == "1"


def atomic_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".new")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, target: Path, *, expected_sha256: str | None = None, expected_size: int | None = None, limit: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    tmp.unlink(missing_ok=True)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "file":
        source = Path(urllib.parse.unquote(parsed.path))
        if not source.is_file():
            raise RuntimeError(f"asset lokal tidak ditemukan: {source}")
        if source.stat().st_size > limit:
            raise RuntimeError("asset melebihi batas ukuran")
        shutil.copyfile(source, tmp)
    else:
        last: Exception | None = None
        for attempt in range(1, 5):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Furina-Updater/1",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as response, tmp.open("wb") as out:
                    declared = response.headers.get("Content-Length")
                    if declared and int(declared) > limit:
                        raise RuntimeError("asset melebihi batas ukuran")
                    total = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > limit:
                            raise RuntimeError("asset melebihi batas ukuran")
                        out.write(chunk)
                break
            except Exception as exc:
                last = exc
                tmp.unlink(missing_ok=True)
                if attempt == 4:
                    raise RuntimeError(f"gagal mengambil {url}: {exc}") from exc
                time.sleep(attempt * 1.5)
        if last and not tmp.exists():
            raise last
    size = tmp.stat().st_size
    if expected_size is not None and size != int(expected_size):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ukuran asset berubah: {size} != {expected_size}")
    if expected_sha256:
        actual = sha256_path(tmp)
        if actual.lower() != expected_sha256.lower():
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"sha256 asset berubah: {actual}")
    os.replace(tmp, target)


def load_json_path(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("metadata bukan object")
    return data


def validate_channel(channel: dict) -> dict:
    if channel.get("schema") != 1 or channel.get("protocol") != PROTOCOL:
        raise RuntimeError("protokol channel update tidak kompatibel")
    for key in ("bundle_id", "core", "apk", "client"):
        if key not in channel:
            raise RuntimeError(f"metadata update tidak lengkap: {key}")
    core = channel["core"]
    apk = channel["apk"]
    client = channel["client"]
    for label, item, required in (
        ("core", core, ("version", "revision", "url", "sha256", "size")),
        ("apk", apk, ("version", "version_code", "package", "url", "sha256", "size")),
        ("client", client, ("version", "url", "sha256", "size")),
    ):
        if not isinstance(item, dict):
            raise RuntimeError(f"metadata {label} tidak valid")
        missing = [name for name in required if not item.get(name)]
        if missing:
            raise RuntimeError(f"metadata {label} tidak lengkap: {', '.join(missing)}")
        if len(str(item["sha256"])) != 64:
            raise RuntimeError(f"sha256 {label} tidak valid")
    return channel


def load_channel(work: Path, override: str | None) -> dict:
    if override:
        src = Path(override).expanduser().resolve()
        return validate_channel(load_json_path(src))
    target = work / "channel.json"
    url = os.environ.get("FURINA_CHANNEL_URL", DEFAULT_CHANNEL)
    fetch(url, target, limit=MAX_CHANNEL_BYTES)
    return validate_channel(load_json_path(target))


class State:
    def __init__(self, root: Path, source: str) -> None:
        self.root = root
        self.path = root / "run/furinahub-update.json"
        self.source = source
        self.stage = "checking"
        self.percent = 0

    def write(self, *, state: str, result: str = "", stage: str | None = None, percent: int | None = None, message: str = "", channel: dict | None = None) -> None:
        if stage is not None:
            self.stage = stage
        if percent is not None:
            self.percent = percent
        payload = {
            "schema": STATE_SCHEMA,
            "protocol": PROTOCOL,
            "state": state,
            "result": result,
            "stage": self.stage,
            "percent": self.percent,
            "message": message,
            "source": self.source,
            "bundle_id": (channel or {}).get("bundle_id", ""),
            "target_version": ((channel or {}).get("core") or {}).get("version", ""),
            "target_revision": ((channel or {}).get("core") or {}).get("revision", ""),
            "updated_at": time.time(),
        }
        atomic_text(self.path, json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def progress(self, percent: int, stage: str, message: str, channel: dict | None = None) -> None:
        self.write(state="running", stage=stage, percent=percent, message=message, channel=channel)
        print(f"PROGRESS {percent} {message}", flush=True)


def acquire_lock(root: Path):
    import fcntl
    path = root / "run/update.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def parse_core_version(root: Path) -> str:
    path = root / "core/furina_agent/version.py"
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = 'VERSION = "'
    start = text.find(marker)
    if start < 0:
        return "unknown"
    start += len(marker)
    end = text.find('"', start)
    return text[start:end] if end > start else "unknown"


def installed_bundle(root: Path) -> dict:
    path = root / "data/installed_bundle.json"
    try:
        data = load_json_path(path)
        return data
    except Exception:
        return {}


def installed_is_current(root: Path, channel: dict) -> bool:
    installed = installed_bundle(root)
    return (
        installed.get("bundle_id") == channel["bundle_id"]
        and installed.get("core_sha256") == channel["core"]["sha256"]
        and parse_core_version(root) == channel["core"]["version"]
        and (root / "bridge/app/build.gradle").is_file()
    )


def safe_extract(snapshot: Path, stage: Path) -> None:
    with tarfile.open(snapshot, "r:*") as archive:
        members = archive.getmembers()
        if not members:
            raise RuntimeError("snapshot kosong")
        for member in members:
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] not in {"core", "bridge"}:
                raise RuntimeError(f"path snapshot tidak aman: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"tipe snapshot tidak aman: {member.name}")
        archive.extractall(stage, members=members)


def validate_stage(stage: Path, channel: dict) -> None:
    version = stage / "core/furina_agent/version.py"
    build = stage / "bridge/app/build.gradle"
    main = stage / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    for path in (version, build, main):
        if not path.is_file():
            raise RuntimeError(f"snapshot tidak lengkap: {path.relative_to(stage)}")
    vt = version.read_text(encoding="utf-8")
    bt = build.read_text(encoding="utf-8")
    mt = main.read_text(encoding="utf-8")
    if f'VERSION = "{channel["core"]["version"]}"' not in vt or f'UPDATE_PROTOCOL = "{PROTOCOL}"' not in vt:
        raise RuntimeError("Core snapshot tidak cocok dengan channel")
    if f"versionCode {channel['apk']['version_code']}" not in bt or f"versionName '{channel['apk']['version']}'" not in bt:
        raise RuntimeError("Bridge snapshot tidak cocok dengan channel")
    if channel["bundle_id"] not in mt:
        raise RuntimeError("bundle id Android tidak cocok dengan channel")


def run_checked(args: list[str], *, cwd: Path | None = None, env: dict | None = None, quiet: bool = True) -> None:
    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None
    subprocess.run(args, cwd=str(cwd) if cwd else None, env=env, stdout=stdout, stderr=stderr, check=True)


def ensure_termux_properties() -> None:
    path = Path.home() / ".termux/termux.properties"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not line.strip().startswith("allow-external-apps=")]
    lines.append("allow-external-apps=true")
    atomic_text(path, "\n".join(lines) + "\n", 0o600)
    reload_cmd = shutil.which("termux-reload-settings")
    if reload_cmd:
        subprocess.run([reload_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def ensure_termux_packages() -> None:
    if test_mode():
        return
    packages: list[str] = []
    for command, package in (("git", "git"), ("node", "nodejs-lts")):
        if not shutil.which(command):
            packages.append(package)
    if packages:
        pkg = shutil.which("pkg")
        if not pkg:
            raise RuntimeError("pkg Termux tidak tersedia")
        run_checked([pkg, "install", "-y", *packages], quiet=False)


def ensure_openconnector(root: Path, state: State, channel: dict) -> None:
    if test_mode():
        return
    marker = root / "data/openconnector_revision"
    app = root / "openconnector"
    healthy = (
        marker.exists()
        and marker.read_text(encoding="utf-8").strip() == OPENCONNECTOR_COMMIT
        and (app / "src/server/index.ts").is_file()
        and (app / "node_modules").is_dir()
    )
    if healthy:
        return
    ensure_termux_packages()
    state.progress(18, "dependencies", "Menyiapkan runtime Plugin sekali saja", channel)
    with tempfile.TemporaryDirectory(prefix="furina-openconnector-") as td:
        source = Path(td) / "openconnector"
        run_checked(["git", "init", "-q", str(source)])
        run_checked(["git", "-C", str(source), "remote", "add", "origin", OPENCONNECTOR_REPOSITORY])
        run_checked(["git", "-C", str(source), "fetch", "-q", "--depth", "1", "origin", OPENCONNECTOR_COMMIT])
        run_checked(["git", "-C", str(source), "checkout", "-q", "--detach", "FETCH_HEAD"])
        run_checked(["npm", "install", "--omit=dev", "--workspaces=false", "--no-audit", "--no-fund"], cwd=source, quiet=False)
        run_checked(["node", "scripts/ensure-generated.ts"], cwd=source)
        shutil.rmtree(source / ".git", ignore_errors=True)
        previous = root / "openconnector.previous"
        shutil.rmtree(previous, ignore_errors=True)
        if app.exists():
            os.replace(app, previous)
        os.replace(source, app)
    atomic_text(marker, OPENCONNECTOR_COMMIT + "\n")
    key = root / "data/openconnector-encryption.key"
    if not key.exists() or key.stat().st_size < 32:
        import secrets
        atomic_text(key, secrets.token_urlsafe(48) + "\n")


def launcher_texts(root: Path) -> dict[str, str]:
    update_py = root / "updater/update_client.py"
    shell = "#!/data/data/com.termux/files/usr/bin/bash\nset -euo pipefail\n"
    return {
        "furina": shell + 'PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"\nif [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi\nexec "$PREFIX/bin/furina-real" "$@"\n',
        "furina-real": shell + 'ROOT="$HOME/.furina-agent"\nexport FURINA_HOME="$ROOT"\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\nexec python -m furina_agent "$@"\n',
        "furina-hub": shell + 'ROOT="$HOME/.furina-agent"\nexport FURINA_HOME="$ROOT"\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\nexec python -m furina_agent.hub "$@"\n',
        "furina-update": shell + f'CLIENT="{update_py}"\nif [[ ! -s "$CLIENT" ]]; then\n  RECOVERY="$HOME/.furina-agent/run/furina-install.sh"\n  mkdir -p "$(dirname "$RECOVERY")"\n  curl -fsSL --retry 4 --retry-all-errors "{DEFAULT_CHANNEL.rsplit("/",1)[0]}/furina-install.sh" -o "$RECOVERY"\n  exec bash "$RECOVERY" --update "$@"\nfi\nexec python "$CLIENT" update "$@"\n',
        "furina-update-apk": shell + f'exec python "{update_py}" apk-only "$@"\n',
        "furina-apk-confirm": shell + f'exec python "{update_py}" confirm-apk "$@"\n',
    }


def install_launchers(root: Path) -> None:
    bindir = prefix_dir() / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    for name, text in launcher_texts(root).items():
        path = bindir / name
        atomic_text(path, text, 0o755)


def install_client_self(root: Path, channel: dict, work: Path) -> bool:
    target = root / "updater/update_client.py"
    wanted = channel["client"]
    current = sha256_path(target) if target.is_file() else ""
    if current == wanted["sha256"]:
        return False
    candidate = work / "update_client.py"
    fetch(wanted["url"], candidate, expected_sha256=wanted["sha256"], expected_size=wanted["size"], limit=MAX_CLIENT_BYTES)
    compile(candidate.read_text(encoding="utf-8"), str(candidate), "exec")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, target)
    os.chmod(target, 0o700)
    return True


def maybe_reexec(root: Path, channel: dict, work: Path, argv: list[str]) -> None:
    changed = install_client_self(root, channel, work)
    if not changed or os.environ.get("FURINA_UPDATER_REEXEC") == "1" or test_mode():
        return
    env = os.environ.copy()
    env["FURINA_UPDATER_REEXEC"] = "1"
    client = root / "updater/update_client.py"
    os.execve(sys.executable, [sys.executable, str(client), *argv], env)


def commit_snapshot(root: Path, stage: Path, channel: dict) -> None:
    rollback = root / "rollback"
    rollback.mkdir(parents=True, exist_ok=True)
    old_core = rollback / "core.previous"
    old_bridge = rollback / "bridge.previous"
    shutil.rmtree(old_core, ignore_errors=True)
    shutil.rmtree(old_bridge, ignore_errors=True)
    core = root / "core"
    bridge = root / "bridge"
    moved_core = moved_bridge = False
    try:
        if core.exists():
            os.replace(core, old_core)
            moved_core = True
        if bridge.exists():
            os.replace(bridge, old_bridge)
            moved_bridge = True
        os.replace(stage / "core", core)
        os.replace(stage / "bridge", bridge)
        validate_stage(root, channel)
    except Exception:
        shutil.rmtree(core, ignore_errors=True)
        shutil.rmtree(bridge, ignore_errors=True)
        if moved_core and old_core.exists():
            os.replace(old_core, core)
        if moved_bridge and old_bridge.exists():
            os.replace(old_bridge, bridge)
        raise
    shutil.rmtree(old_core, ignore_errors=True)
    shutil.rmtree(old_bridge, ignore_errors=True)


def install_core(root: Path, channel: dict, work: Path, state: State, *, force: bool) -> bool:
    if installed_is_current(root, channel) and not force:
        return False
    core = channel["core"]
    snapshot = work / "core-bridge.tar"
    state.progress(30, "download", f"Mengunduh Core {core['version']}", channel)
    fetch(core["url"], snapshot, expected_sha256=core["sha256"], expected_size=core["size"], limit=MAX_SNAPSHOT_BYTES)
    stage = work / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    state.progress(55, "validation", "Memverifikasi snapshot", channel)
    safe_extract(snapshot, stage)
    validate_stage(stage, channel)
    state.progress(72, "commit", "Mengaktifkan Core secara atomik", channel)
    commit_snapshot(root, stage, channel)
    data = {
        "schema": 1,
        "protocol": PROTOCOL,
        "bundle_id": channel["bundle_id"],
        "core_version": core["version"],
        "core_revision": core["revision"],
        "core_sha256": core["sha256"],
        "installed_at": time.time(),
    }
    atomic_text(root / "data/installed_bundle.json", json.dumps(data, separators=(",", ":")) + "\n")
    return True


def sync_apk(root: Path, channel: dict, work: Path, state: State) -> bool:
    confirmed = root / "data/furinahub_apk_bundle"
    if confirmed.exists() and confirmed.read_text(encoding="utf-8").strip() == channel["bundle_id"]:
        return False
    apk = channel["apk"]
    target = Path.home() / f"FurinaHub-v{apk['version']}.apk"
    state.progress(86, "bridge", f"Mengunduh FurinaHub {apk['version']}", channel)
    fetch(apk["url"], target, expected_sha256=apk["sha256"], expected_size=apk["size"], limit=MAX_APK_BYTES)
    atomic_text(root / "data/pending_apk_bundle", channel["bundle_id"] + "\n")
    if test_mode():
        return True
    opener = shutil.which("termux-open")
    if opener:
        subprocess.run([opener, "--content-type", "application/vnd.android.package-archive", str(target)], check=False)
    print(f"APK siap: {target}")
    return True


def confirm_apk(root: Path, bundle_id: str) -> int:
    pending = root / "data/pending_apk_bundle"
    if not pending.exists() or pending.read_text(encoding="utf-8").strip() != bundle_id:
        return 0
    atomic_text(root / "data/furinahub_apk_bundle", bundle_id + "\n")
    pending.unlink(missing_ok=True)
    return 0


def update(args: argparse.Namespace) -> int:
    root = root_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    source = os.environ.get("FURINA_UPDATE_SOURCE", "termux")
    state = State(root, source)
    with acquire_lock(root), tempfile.TemporaryDirectory(prefix="furina-update-") as td:
        work = Path(td)
        channel: dict | None = None
        try:
            state.progress(3, "checking", "Memeriksa channel update Furina")
            channel = load_channel(work, args.channel_file)
            maybe_reexec(root, channel, work, sys.argv[1:])
            install_launchers(root)
            if args.command == "apk-only":
                changed = sync_apk(root, channel, work, state)
                message = "Installer FurinaHub dibuka" if changed else "FurinaHub sudah dikonfirmasi terbaru"
                state.write(state="done", result="updated" if changed else "no_update", stage="done", percent=100, message=message, channel=channel)
                print(f"PROGRESS 100 {message}")
                return 0

            ensure_termux_properties()
            ensure_termux_packages()
            ensure_openconnector(root, state, channel)
            changed_core = install_core(root, channel, work, state, force=args.force or args.command == "repair")
            install_launchers(root)
            changed_apk = sync_apk(root, channel, work, state)
            if changed_core and changed_apk:
                message = "Core diperbarui; installer FurinaHub dibuka"
                result = "updated"
            elif changed_core:
                message = "Core diperbarui"
                result = "updated"
            elif changed_apk:
                message = "Core sudah terbaru; installer FurinaHub dibuka"
                result = "updated"
            else:
                message = "Tidak ada pembaruan terbaru"
                result = "no_update"
            state.write(state="done", result=result, stage="done", percent=100, message=message, channel=channel)
            print(f"PROGRESS 100 {message}")
            return 0
        except Exception as exc:
            state.write(state="error", result="error", message=f"Pembaruan gagal: {exc}", channel=channel)
            print(f"ERROR {state.stage} {exc}", file=sys.stderr)
            return 1


def status(args: argparse.Namespace) -> int:
    root = root_dir()
    payload = {
        "protocol": PROTOCOL,
        "client_version": CLIENT_VERSION,
        "core_version": parse_core_version(root),
        "installed_bundle": installed_bundle(root),
        "apk_bundle": (root / "data/furinahub_apk_bundle").read_text(encoding="utf-8").strip() if (root / "data/furinahub_apk_bundle").exists() else "",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="furina-update")
    sub = parser.add_subparsers(dest="command")
    for name in ("update", "repair", "apk-only"):
        p = sub.add_parser(name)
        p.add_argument("--channel-file")
        p.add_argument("--force", action="store_true")
    confirm = sub.add_parser("confirm-apk")
    confirm.add_argument("bundle_id")
    sub.add_parser("status")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(["update"])
    if args.command == "confirm-apk":
        return confirm_apk(root_dir(), args.bundle_id)
    if args.command == "status":
        return status(args)
    return update(args)


if __name__ == "__main__":
    raise SystemExit(main())
