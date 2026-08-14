#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import shutil
import sys


RC33_MARKER = "RC33_PSYCHE_CORE"


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC33 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    root = pathlib.Path(sys.argv[1]).resolve()
    templates = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent
    core = root / "core/furina_agent"
    version = core / "version.py"
    providers = core / "providers.py"

    if not core.exists():
        raise SystemExit(f"Core Furina tidak ditemukan: {core}")

    current = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc33"' in current:
        print("Furina Core RC33: already applied")
        return
    if 'VERSION = "1.0.0-rc32"' not in current:
        raise SystemExit("RC33 hanya dapat diterapkan dari Core RC32")

    replacement_files = (
        "psyche.py",
        "chat.py",
        "persona.py",
        "response.py",
        "mind_v2.py",
        "routing.py",
    )
    for name in replacement_files:
        source = templates / name
        if not source.exists():
            raise SystemExit(f"Template RC33 hilang: {source}")
        shutil.copyfile(source, core / name)

    p = providers.read_text(encoding="utf-8")
    p = rep(
        p,
        '''    def last_good(self, provider: str) -> str | None:
        value = self._load().get(provider, {}).get("last_good_model")
        return str(value) if value else None

    def mark_success(self, provider: str, model: str) -> None:
        data = self._load()
        data[provider] = {"last_good_model": model, "updated_at": time.time()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
''',
        '''    def last_good(self, provider: str, role: str = "conversation") -> str | None:
        data = self._load()
        row = data.get(provider, {}) if isinstance(data.get(provider), dict) else {}
        roles = row.get("roles", {}) if isinstance(row.get("roles"), dict) else {}
        role_row = roles.get(role, {}) if isinstance(roles.get(role), dict) else {}
        value = role_row.get("last_good_model")
        if value:
            return str(value)
        if role == "conversation":
            legacy = row.get("last_good_model")
            return str(legacy) if legacy else None
        return None

    def mark_success(self, provider: str, model: str, role: str = "conversation") -> None:
        data = self._load()
        row = data.get(provider, {}) if isinstance(data.get(provider), dict) else {}
        roles = row.get("roles", {}) if isinstance(row.get("roles"), dict) else {}
        roles[role] = {"last_good_model": model, "updated_at": time.time()}
        row["roles"] = roles
        if role == "conversation":
            row["last_good_model"] = model
            row["updated_at"] = time.time()
        data[provider] = row
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
''',
        "provider role state",
    )
    p = rep(
        p,
        '''class OpenAICompatibleProvider:
    def __init__(self, name: str, api_key: str, cfg: Config):
        if name not in PROVIDER_LABELS:
            raise ValueError(name)
        self.name = name
        self.api_key = api_key
        self.cfg = cfg
        self.base_url = PROVIDER_BASE_URLS[name].rstrip("/")
        self.state = ProviderState()
''',
        '''class OpenAICompatibleProvider:
    def __init__(self, name: str, api_key: str, cfg: Config, role: str = "conversation"):
        if name not in PROVIDER_LABELS:
            raise ValueError(name)
        self.name = name
        self.api_key = api_key
        self.cfg = cfg
        self.role = str(role or "conversation")[:32]
        self.base_url = PROVIDER_BASE_URLS[name].rstrip("/")
        self.state = ProviderState()
''',
        "provider constructor role",
    )
    p = rep(
        p,
        '        last = self.state.last_good(self.name)\n',
        '        last = self.state.last_good(self.name, self.role)\n',
        "role-aware ranking",
    )
    p = rep(
        p,
        '        self.state.mark_success(self.name, model)\n',
        '        self.state.mark_success(self.name, model, self.role)\n',
        "role-aware success",
    )
    providers.write_text(p, encoding="utf-8")

    current = current.replace('VERSION = "1.0.0-rc32"', 'VERSION = "1.0.0-rc33"', 1)
    version.write_text(current, encoding="utf-8")

    for path in tuple(core / name for name in replacement_files) + (providers, version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    chat = (core / "chat.py").read_text(encoding="utf-8")
    psyche = (core / "psyche.py").read_text(encoding="utf-8")
    routing = (core / "routing.py").read_text(encoding="utf-8")
    persona = (core / "persona.py").read_text(encoding="utf-8")
    for marker in (
        "PSYCHE_STATE_V1",
        "trusted_conversation",
        "Personality moves far slower",
        "apply_integration",
    ):
        if marker not in psyche:
            raise SystemExit(f"RC33 psyche marker hilang: {marker}")
    for marker in ("MIND PACKET", "Experience Integrator", 'role="conversation"', 'role="memory"'):
        if marker not in chat:
            raise SystemExit(f"RC33 chat marker hilang: {marker}")
    if "last_by_role" not in routing or "_infer_role" not in routing:
        raise SystemExit("RC33 role router tidak aktif")
    if "Bangga, teatrikal" in persona or "tsundere" in persona.casefold():
        raise SystemExit("Persona kaku lama masih aktif")
    if "ProviderState" not in p or "roles" not in p:
        raise SystemExit("Provider role state tidak aktif")

    print("Furina Core RC33 Psyche: OK")


if __name__ == "__main__":
    main()
