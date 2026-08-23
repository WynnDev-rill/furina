#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
CORE = ROOT / "core/furina_agent"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


def replace_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{name}: expected one function, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start = sum(len(x) for x in lines[: node.lineno - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    body = replacement.rstrip() + "\n"
    path.write_text(text[:start] + body + text[end:], encoding="utf-8")


# Shared model catalog is part of the shipped Core snapshot, not the updater.
shutil.copyfile(HERE / "local_models.py", CORE / "local_models.py")

# Version identity.
version = CORE / "version.py"
v = version.read_text(encoding="utf-8")
v = replace_once(v, 'VERSION = "1.0.0"', 'VERSION = "1.0.1"', "core version")
version.write_text(v, encoding="utf-8")

# Config: AUTO is retired. Existing AUTO installs migrate to ONLINE, and no
# local server is pre-warmed just because Furina opens.
config = CORE / "config.py"
c = config.read_text(encoding="utf-8")
c = c.replace('routing_mode: str = "auto"', 'routing_mode: str = "online"')
c = c.replace('routing_mode: str = \"auto\"', 'routing_mode: str = \"online\"')
c = c.replace('{"local", "auto", "online"}', '{"local", "online"}')
c = c.replace('defaults["routing_mode"] = "auto"', 'defaults["routing_mode"] = "online"')
c = c.replace('auto_start: bool = True', 'auto_start: bool = False')
# Explicit migration for a persisted AUTO string before dataclass construction.
needle = 'defaults = {field.name: raw.get(field.name, field.default) for field in fields(Config)}'
if needle in c and 'raw.get("routing_mode") == "auto"' not in c:
    c = c.replace(needle, needle + '\n    if raw.get("routing_mode") == "auto":\n        defaults["routing_mode"] = "online"', 1)
config.write_text(c, encoding="utf-8")

# Routing becomes deliberately binary: online provider chain OR the one local
# GGUF selected by the user. Online failures never silently switch to local.
routing = CORE / "routing.py"
replace_function(
    routing,
    "health",
'''    def health(self) -> bool:
        if self.cfg.routing_mode == "local":
            return self.local.health()
        return bool(self.secrets.configured())''',
)
replace_function(
    routing,
    "vision",
'''    def vision(self, prompt: str, image_base64: str, *, mime: str = "image/png", max_tokens: int = 420, json_mode: bool = True) -> str:
        if self.cfg.routing_mode == "local":
            try:
                return self.local_vision.analyze(prompt, image_base64, mime=mime, max_tokens=max_tokens, json_mode=json_mode)
            except LocalVisionError as exc:
                raise LLMError(f"Vision lokal tidak tersedia: {exc}") from exc
        if not self.secrets.configured():
            raise LLMError("Provider online belum dikonfigurasi.")
        try:
            return self.vision_router.analyze(prompt, image_base64, mime=mime, max_tokens=max_tokens, json_mode=json_mode)
        except VisionError as exc:
            raise LLMError(f"Vision online tidak tersedia: {exc}") from exc''',
)
replace_function(
    routing,
    "chat",
'''    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        on_token=None,
        json_mode: bool = False,
        role: str | None = None,
    ) -> str:
        max_tokens = self.cfg.max_tokens if max_tokens is None else max_tokens
        temperature = self.cfg.temperature if temperature is None else temperature
        role = self._normalize_role(role, messages, json_mode)
        if self.cfg.routing_mode == "local":
            if not self._ensure_local():
                raise LLMError("Model lokal belum siap. Buka Provider & Model, unduh salah satu model lalu pilih model tersebut.")
            answer = self.local.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
                json_mode=json_mode,
            )
            self._record("local", Path(self.cfg.model_path).name or "GGUF", role)
            return answer
        if not self.secrets.configured():
            raise LLMError("Provider online belum dikonfigurasi. Buka Provider & Model untuk menambahkan API key.")
        answer = self._online_chat(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
            role=role,
        )
        if on_token and answer and not json_mode:
            on_token(answer)
        return answer''',
)

# Simplified Termux product surface.
tui = CORE / "tui.py"
helpers = r'''

def _private_stop_local():
    try:
        from .cli import cmd_stop
        cmd_stop(None)
    except Exception:
        pass


def _private_provider_keys(console):
    secrets = ProviderSecrets()
    while True:
        cfg = load_config()
        _clear(); _header(console, "Provider online")
        for name, label in PROVIDER_LABELS.items():
            console.print(f"[bright_cyan]{label:<12}[/]  [dim]{secrets.masked(name) or 'belum diatur'}[/]")
        if "openrouter" in PROVIDER_LABELS:
            console.print(f"\n[dim]OpenRouter free-only[/]  {'ON' if cfg.provider_prefer_free else 'OFF'}")
        choice = _choose("", ["Tambah / ubah API key", "Hapus API key", "Tes provider", "OpenRouter free-only", "Kembali"], height=7)
        if choice in {"", "Kembali"}: return
        if choice in {"Tambah / ubah API key", "Hapus API key", "Tes provider"}:
            name = _provider_name()
            if not name: continue
            if choice == "Tambah / ubah API key":
                key = _input("API key › ", password=True).strip()
                if key:
                    secrets.set(name, key); console.print("[green]Tersimpan lokal.[/]")
            elif choice == "Hapus API key":
                if _confirm(f"Hapus key {PROVIDER_LABELS[name]}?", default=False): secrets.remove(name)
            else:
                key = secrets.get(name)
                if not key:
                    console.print("[yellow]Key belum diatur.[/]")
                else:
                    try:
                        with console.status(f"[#5de4c7]Menguji {PROVIDER_LABELS[name]}…[/]", spinner="dots"):
                            ok, detail = OpenAICompatibleProvider(name, key, cfg).test()
                        console.print(("[green]OK[/]  " if ok else "[red]FAIL[/]  ") + detail)
                    except Exception as exc:
                        console.print(f"[red]FAIL[/]  {exc}")
            _pause()
        elif choice == "OpenRouter free-only":
            cfg.provider_prefer_free = not cfg.provider_prefer_free; save_config(cfg)


def _private_identity(console):
    cfg = load_config()
    while True:
        _clear(); _header(console, "Identitas")
        console.print(f"[dim]Panggilanmu[/]  {cfg.user_nickname or '—'}")
        console.print(f"[dim]Nama companion[/]  {cfg.persona_name}\n")
        choice = _choose("", ["Ubah panggilanmu", "Ubah nama companion", "Kembali"], height=5)
        if choice in {"", "Kembali"}: return
        if choice == "Ubah panggilanmu": cfg.user_nickname = _input("Panggilan › ", value=cfg.user_nickname).strip()[:48]
        elif choice == "Ubah nama companion": cfg.persona_name = _input("Nama › ", value=cfg.persona_name).strip()[:48] or "Furina"
        cfg.local_reasoning = False; cfg.auto_start = False; save_config(cfg)
'''
if "def _private_provider_keys" not in tui.read_text(encoding="utf-8"):
    tui.write_text(tui.read_text(encoding="utf-8") + helpers, encoding="utf-8")

replace_function(tui, "_main_menu", '''def _main_menu(console) -> str:
    return _choose("", ["Chat", "Provider & Model", "Pengaturan", "Exit"], height=6)''')
replace_function(
    tui,
    "_providers",
'''def _providers(console):
    from .local_models import catalog_state, download_model, retire_legacy_catalog
    while True:
        cfg = load_config()
        if retire_legacy_catalog(cfg):
            save_config(cfg)
        rows = catalog_state(cfg.model_path)
        if cfg.routing_mode == "local" and not any(x["active"] for x in rows):
            cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg)
            rows = catalog_state("")
        _clear(); _header(console, "Provider & Model")
        active = next((x["name"] for x in rows if x["active"] and cfg.routing_mode == "local"), "Online")
        console.print(f"[dim]Dipakai untuk chat[/]  [bold]{active}[/]\n")
        choices = [f"Online · {'Aktif' if cfg.routing_mode == 'online' else 'Pilih'}"]
        lookup = {}
        for row in rows:
            state = "Aktif" if row["active"] and cfg.routing_mode == "local" else ("Pilih" if row["installed"] else "Unduh")
            label = f"{row['name']} · {row['size_label']} · {state}"
            choices.append(label); lookup[label] = row
        choices += ["Kelola API provider", "Kembali"]
        choice = _choose("", choices, height=8)
        if choice in {"", "Kembali"}: return
        if choice.startswith("Online ·"):
            if cfg.routing_mode != "online":
                cfg.routing_mode = "online"; cfg.auto_start = False; save_config(cfg); _private_stop_local()
            continue
        if choice == "Kelola API provider":
            _private_provider_keys(console); continue
        row = lookup.get(choice)
        if not row: continue
        if not row["installed"]:
            if not _confirm(f"Unduh {row['name']} ({row['size_label']})?", default=True): continue
            try:
                with console.status(f"[#5de4c7]Mengunduh {row['name']} · 0%[/]", spinner="dots") as status:
                    def progress(done, total, percent, resumed):
                        status.update(f"[#5de4c7]Mengunduh {row['name']} · {percent}%[/]")
                    download_model(row["id"], progress)
                console.print("[green]Selesai.[/] Model siap dipilih.")
            except Exception as exc:
                console.print(f"[red]Unduhan gagal[/]  {exc}")
            _pause(); continue
        if not (row["active"] and cfg.routing_mode == "local"):
            _private_stop_local()
            cfg.model_path = row["path"]; cfg.routing_mode = "local"; cfg.auto_start = False; cfg.local_reasoning = False
            save_config(cfg)
            console.print(f"[green]Aktif[/]  {row['name']} akan dimuat saat chat lokal pertama dikirim.")
            _pause()''',
)
replace_function(
    tui,
    "_system",
'''def _system(console):
    while True:
        _clear(); _header(console, "Sistem")
        choice = _choose("", ["Status sistem", "Optimalkan model lokal", "Hentikan model lokal", "Kembali"], height=6)
        if choice in {"", "Kembali"}: return
        if choice == "Status sistem":
            _doctor(console); _pause()
        elif choice == "Optimalkan model lokal":
            if _confirm("Benchmark dapat membuat HP hangat. Lanjut?", default=False):
                from .cli import cmd_optimize
                try: cmd_optimize(None)
                except Exception as exc: console.print(f"[red]Optimize gagal[/]  {exc}")
                _pause()
        elif choice == "Hentikan model lokal":
            _private_stop_local(); console.print("[green]Model lokal dihentikan.[/]"); _pause()''',
)
replace_function(
    tui,
    "_settings",
'''def _settings(console):
    while True:
        cfg = load_config()
        _clear(); _header(console, "Pengaturan")
        console.print(f"[dim]Identitas[/]  {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
        console.print(f"[dim]Kontrol[/]    {cfg.device_control_mode.upper()}\n")
        choice = _choose("", ["Identitas", "Kontrol perangkat", "Sistem", "Backup", "Update & Recovery", "Kembali"], height=8)
        if choice in {"", "Kembali"}: return
        if choice == "Identitas": _private_identity(console); continue
        if choice == "Sistem": _system(console); continue
        if choice == "Backup": _lite_backup(console); continue
        if choice == "Update & Recovery": _update_repair(console); continue
        if choice == "Kontrol perangkat":
            mode = _choose("Kontrol perangkat", ["Normal", "Shizuku", "Root", "Kembali"], height=6)
            if mode in {"Normal", "Shizuku", "Root"}:
                cfg.device_control_mode = mode.lower(); cfg.auto_start = False
                if mode in {"Shizuku", "Root"}:
                    try:
                        result = AndroidBridge(cfg).control({"type": "prepare_" + mode.lower(), "mode": mode.lower()})
                        console.print(f"[dim]{result.get('message') or ('Siap' if result.get('ok') else 'Izin belum aktif')}[/]")
                    except Exception:
                        console.print("[yellow]Bridge belum siap. Mode tersimpan; aktifkan izinnya nanti.[/]")
                    _pause()
                save_config(cfg)''',
)
replace_function(
    tui,
    "_setup",
'''def _setup(console):
    from .local_models import catalog_state, retire_legacy_catalog
    cfg = load_config()
    _clear(); _header(console, "Mulai bersama Furina")
    console.print("Kalian memulai sebagai pasangan. Furina hanya mengingat namanya, namamu, dan hubungan kalian.\n")
    cfg.user_nickname = _input("Furina memanggilmu › ", value=cfg.user_nickname).strip()[:48]
    cfg.persona_name = cfg.persona_name.strip() or "Furina"
    cfg.local_reasoning = False; cfg.auto_start = False
    retire_legacy_catalog(cfg)
    if cfg.routing_mode != "local" or not any(x["active"] for x in catalog_state(cfg.model_path)):
        cfg.routing_mode = "online"; cfg.model_path = ""
    save_config(cfg)
    RelationshipEngine(MemoryStore()).snapshot()
    console.print("[bright_cyan]✓[/] Hubungan awal: [bold]Pasangan[/] · ingatan lain masih kosong.")
    console.print("[dim]Tidak ada model lokal yang diunduh saat instalasi. Dua model 1.7B tersedia nanti di Provider & Model.[/]\n")
    if not ProviderSecrets().configured() and _confirm("Atur API provider online sekarang?", default=True):
        _private_provider_keys(console)
    cfg = load_config(); cfg.onboarding_complete = True; cfg.local_reasoning = False; cfg.auto_start = False; save_config(cfg)''',
)
replace_function(
    tui,
    "run_tui",
'''def run_tui():
    Console, _, _, _, _, _, _ = _rich()
    console = _ThemedConsole(Console(highlight=False))
    from .local_models import retire_legacy_catalog
    cfg = load_config()
    if retire_legacy_catalog(cfg): save_config(cfg)
    if not cfg.onboarding_complete: _setup(console)
    while True:
        _clear(); _header(console); _show_due(console)
        choice = _main_menu(console)
        if choice in {"", "Exit"}: return
        if choice == "Chat": _chat(console)
        elif choice == "Provider & Model": _providers(console)
        elif choice == "Pengaturan": _settings(console)''',
)

# Hub shares the same exact catalog and migration. Keep API surface intact while
# refusing AUTO and verifying catalog downloads.
hub = CORE / "hub.py"
h = hub.read_text(encoding="utf-8")
import_marker = "from .hub_web import HTML"
if "from .local_models import" not in h:
    h = replace_once(h, import_marker, import_marker + "\nfrom .local_models import CATALOG as LOCAL_MODEL_CATALOG, catalog_state, download_model, retire_legacy_catalog", "hub import")
pattern = re.compile(r"MODEL_CATALOG = \(\n.*?\n\)\nPLUGIN_LOGOS", re.S)
h, count = pattern.subn("MODEL_CATALOG = tuple(dict(item) for item in LOCAL_MODEL_CATALOG)\nPLUGIN_LOGOS", h, count=1)
if count != 1: raise SystemExit(f"hub catalog: expected one block, got {count}")
h = h.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r33"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.23-r41"')
h = h.replace('{"local", "auto", "online"}', '{"local", "online"}')
h = h.replace('cfg.routing_mode = "auto"', 'cfg.routing_mode = "online"')
h = h.replace('"bundle_id": "furina-2026.08.21-rc63-rc51"', '"bundle_id": "furina-2026.08.23-private-1.0.1"')
# Migrate legacy catalog files as soon as the Hub runtime rebuilds.
old_rebuild = "            self.cfg = load_config()\n            hub = load_hub_settings()"
new_rebuild = "            self.cfg = load_config()\n            if retire_legacy_catalog(self.cfg):\n                save_config(self.cfg)\n            hub = load_hub_settings()"
if old_rebuild in h:
    h = h.replace(old_rebuild, new_rebuild, 1)
hub.write_text(h, encoding="utf-8")
replace_function(
    hub,
    "_download_model",
'''    def _download_model(self, catalog_id: str) -> None:
        item = next((entry for entry in MODEL_CATALOG if entry["id"] == catalog_id), None)
        if not item:
            with self.update_lock:
                self.model_status = {"state": "error", "message": "Model tidak dikenal.", "percent": 0}
            return
        try:
            def progress(received: int, total: int, percent: int, resumed: bool) -> None:
                with self.update_lock:
                    self.model_status = {"state": "running", "message": f"Mengunduh {item['name']}", "percent": percent, "received": received, "total": total, "name": item["name"], "resumed": resumed}
            target = download_model(catalog_id, progress)
            with self.update_lock:
                self.model_status = {"state": "done", "message": f"{item['name']} selesai diunduh. Tekan Pilih untuk menggunakannya.", "percent": 100, "name": item["name"], "path": str(target)}
        except Exception as exc:
            with self.update_lock:
                self.model_status = {"state": "error", "message": f"Unduhan terhenti: {str(exc)[:210]}. Tekan Unduh untuk melanjutkan.", "percent": 0, "name": item["name"], "resumable": True}''',
)
replace_function(
    hub,
    "change_model",
'''    def change_model(self, payload: dict) -> dict:
        action = str(payload.get("action") or "").strip().lower()
        if action == "download":
            catalog_id = str(payload.get("catalog_id") or "").strip()
            item = next((entry for entry in MODEL_CATALOG if entry["id"] == catalog_id), None)
            if not item: raise ValueError("pilih salah satu model lokal Furina")
            with self.update_lock:
                if self.model_status.get("state") in {"starting", "running"}: raise ValueError("unduhan model lain masih berjalan")
                self.model_status = {"state": "starting", "message": f"Menyiapkan {item['name']}", "percent": 0, "name": item["name"]}
            threading.Thread(target=self._download_model, args=(catalog_id,), daemon=True).start()
            return self.get_model_status()
        if action == "delete":
            path = Path(str(payload.get("path") or "")).resolve()
            allowed = {Path(row["path"]).resolve() for row in catalog_state()}
            if path not in allowed or not path.exists(): raise ValueError("model tidak valid")
            cfg = load_config()
            if cfg.model_path and Path(cfg.model_path).resolve() == path:
                cfg.model_path = ""; cfg.routing_mode = "online"; cfg.auto_start = False; save_config(cfg)
            path.unlink(missing_ok=True); path.with_name(path.name + ".part").unlink(missing_ok=True)
            self.rebuild()
            return {"state": "done", "message": f"{path.name} dihapus dari Termux."}
        raise ValueError("aksi model tidak valid")''',
)

# Validate syntax now so failed textual transformations never enter the snapshot.
for path in (config, routing, tui, hub, CORE / "local_models.py", version):
    if path.suffix == ".py": ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print("FURINA_PRIVATE_1_0_1_MODEL_FLOW_OK")
