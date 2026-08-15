#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC47 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    settings_path = core / "hub_settings.py"
    direct_path = core / "direct_control.py"
    hub_path = core / "hub.py"
    version_path = core / "version.py"
    for path in (settings_path, direct_path, hub_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC47 source hilang: {path}")

    version = version_path.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc47"' in version:
        print("FurinaHub Core RC47 already applied")
        return
    if 'VERSION = "1.0.0-rc46"' not in version:
        raise SystemExit("RC47 hanya dapat diterapkan dari Core RC46")

    settings = settings_path.read_text(encoding="utf-8")
    skill_block = '''# RC47 direct Agent recipes. These are separately toggleable while still\n# respecting the lower-level ACTION_SKILLS safety gates above.\nDEFAULT_SKILLS.update({\n    "app_launcher": True,\n    "quick_navigation": True,\n    "semantic_tap": True,\n    "smart_scroll": True,\n    "focused_typing": True,\n    "local_reminders": True,\n    "screen_reader": True,\n    "app_finder": True,\n    "form_fill": True,\n    "workflow_macros": True,\n})\nSKILL_META.update({\n    "app_launcher": {"label": "Peluncur Aplikasi", "description": "Buka aplikasi terpasang dari nama atau package dengan pencocokan lokal."},\n    "quick_navigation": {"label": "Navigasi Cepat", "description": "Jalankan Home, Back, dan Recents langsung tanpa menunggu planner AI."},\n    "semantic_tap": {"label": "Ketuk Berdasarkan Teks", "description": "Cari label tombol di Accessibility lalu ketuk target yang cocok secara semantik."},\n    "smart_scroll": {"label": "Scroll Cerdas", "description": "Pilih container yang dapat di-scroll sebelum memakai gesture layar sebagai fallback."},\n    "focused_typing": {"label": "Ketik ke Field Aktif", "description": "Isi field editable yang sedang fokus atau satu-satunya field yang relevan."},\n    "local_reminders": {"label": "Pengingat Lokal", "description": "Jadwalkan pengingat Android lokal melalui Bridge tanpa daemon Termux tetap hidup."},\n    "screen_reader": {"label": "Ringkas Layar", "description": "Baca teks dan deskripsi elemen layar melalui Accessibility lalu ringkas secara lokal."},\n    "app_finder": {"label": "Pencari Aplikasi", "description": "Cari aplikasi yang terpasang dan laporkan label serta package yang cocok."},\n    "form_fill": {"label": "Isi Formulir", "description": "Temukan field berdasarkan label lalu masukkan nilai melalui aksi Accessibility terverifikasi."},\n    "workflow_macros": {"label": "Macro Multi-langkah", "description": "Rangkai maksimal enam aksi lokal sederhana seperti buka, scroll, ketuk, dan ketik."},\n})\n\n'''
    settings = replace_once(settings, "\ndef _default_traits() -> dict[str, int]:\n", "\n" + skill_block + "def _default_traits() -> dict[str, int]:\n", "skill registry")
    settings_path.write_text(settings, encoding="utf-8")

    direct = direct_path.read_text(encoding="utf-8")
    direct = replace_once(
        direct,
        'from .hub_settings import effective_device_mode, load_hub_settings',
        'from .hub_settings import effective_device_mode, load_hub_settings, skill_enabled',
        "skill_enabled import",
    )
    direct = replace_once(
        direct,
        '''_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout)\\b", re.I)\n''',
        '''_SENSITIVE = re.compile(r"\\b(?:kirim|send|submit|post|publish|share|bagikan|hapus|delete|remove|uninstall|reset|bayar|pay|purchase|beli|transfer|subscribe|berlangganan|login|logout)\\b", re.I)\n_SCREEN_READ = re.compile(r"^\\s*(?:baca|lihat|jelaskan|ringkas|apa(?:\\s+saja)?\\s+yang\\s+ada\\s+di)\\s+(?:layar|screen)(?:\\s+(?:ini|sekarang))?\\s*[.!?]?\\s*$", re.I)\n_APP_FIND = re.compile(r"^\\s*(?:cari|temukan|cek)\\s+(?:aplikasi|app|apk)\\s+(.+?)\\s*[.!?]?\\s*$", re.I)\n_FORM_FILL = re.compile(r"^\\s*(?:isi|isikan|masukkan)\\s+(?:kolom|field)\\s+(.+?)\\s+(?:dengan|menjadi|:)\\s+(.+?)\\s*[.!]?\\s*$", re.I)\n''',
        "recipe regex",
    )
    direct = replace_once(
        direct,
        '''    def _mode(self) -> str:\n        fallback = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").lower()\n''',
        '''    def _skill(self, name: str) -> bool:\n        try:\n            return skill_enabled(name, load_hub_settings())\n        except Exception:\n            return False\n\n    def _mode(self) -> str:\n        fallback = str(getattr(self.cfg, "device_control_mode", "normal") or "normal").lower()\n''',
        "skill helper",
    )
    helper_block = '''    def _screen_summary(self) -> str:\n        try:\n            screen = self.bridge.screen() or {}\n        except Exception:\n            return ""\n        seen, values = set(), []\n        for node in screen.get("nodes") or []:\n            if not isinstance(node, dict):\n                continue\n            for key in ("text", "desc"):\n                value = " ".join(str(node.get(key) or "").split()).strip()\n                folded = value.casefold()\n                if not value or folded in seen:\n                    continue\n                seen.add(folded); values.append(value[:140])\n                if len(values) >= 24:\n                    break\n            if len(values) >= 24:\n                break\n        package = str(screen.get("package") or "").strip()\n        title = str(screen.get("window_title") or "").strip()\n        head = " · ".join(x for x in (title, package) if x)\n        body = "; ".join(values)\n        return (((head + ": ") if head else "") + body) if body else ((head + ". Tidak ada teks Accessibility yang terbaca.").strip())\n\n    def _macro_action(self, part: str) -> tuple[str, dict] | None:\n        text = " ".join(str(part or "").split()).strip()\n        match = _SIMPLE_OPEN.match(text)\n        if match:\n            package = self._resolve_app(match.group(1), exact=True)\n            return ("control", {"type": "open_app", "package": package}) if package else None\n        if _BACK.match(text): return "control", {"type": "back"}\n        if _HOME.match(text): return "control", {"type": "home"}\n        if _RECENTS.match(text): return "control", {"type": "recents"}\n        match = _SCROLL.match(text)\n        if match:\n            direction = match.group(2).casefold()\n            return "bridge", {"type": "scroll_best", "direction": "backward" if direction in {"atas", "up"} else "forward"}\n        match = _TAP.match(text)\n        if match and not _SENSITIVE.search(match.group(1)):\n            return "bridge", {"type": "tap_text", "target": match.group(1)}\n        match = _TYPE.match(text)\n        if match and len(match.group(1)) <= 500:\n            return "bridge", {"type": "set_text_best", "text": match.group(1)}\n        return None\n\n    def _try_macro(self, raw: str) -> DirectResult:\n        if not self._skill("workflow_macros") or not _CHAIN.search(raw) or _SENSITIVE.search(raw):\n            return DirectResult(False)\n        parts = [p.strip(" ,") for p in _CHAIN.split(raw) if p.strip(" ,")]\n        if not 2 <= len(parts) <= 6:\n            return DirectResult(False)\n        plan = [self._macro_action(part) for part in parts]\n        if any(item is None for item in plan):\n            return DirectResult(False)\n        for transport, action in plan:\n            try:\n                result = self._control(action) if transport == "control" else self.bridge.action(action)\n            except Exception:\n                return DirectResult(False)\n            if not isinstance(result, dict) or not result.get("ok"):\n                return DirectResult(False)\n            time.sleep(0.18)\n        self.store.log_event("direct_control", {"type": "workflow_macro", "steps": len(plan)})\n        return DirectResult(True, "Selesai.", "workflow_macro")\n\n'''
    direct = replace_once(direct, "    def try_execute_step(self, step: dict) -> DirectResult:\n", helper_block + "    def try_execute_step(self, step: dict) -> DirectResult:\n", "recipe helpers")

    recipe_block = '''        if self._skill("screen_reader") and _SCREEN_READ.match(raw):\n            summary = self._screen_summary()\n            if summary:\n                self.store.log_event("direct_control", {"type": "screen_reader"})\n                return DirectResult(True, summary, "screen_reader")\n\n        match = _APP_FIND.match(raw) if self._skill("app_finder") else None\n        if match:\n            package = self._resolve_app(match.group(1), exact=False)\n            if package:\n                app = next((x for x in self._apps() if str(x.get("package") or "") == package), {})\n                label = str(app.get("label") or match.group(1)).strip()\n                self.store.log_event("direct_control", {"type": "app_finder", "package": package})\n                return DirectResult(True, f"Ditemukan: {label} ({package}).", "app_finder")\n            return DirectResult(True, "Aplikasi yang cocok tidak ditemukan.", "app_finder")\n\n        match = _FORM_FILL.match(raw) if self._skill("form_fill") else None\n        if match and len(match.group(2)) <= 500 and not _SENSITIVE.search(raw):\n            label, value = match.group(1).strip(), match.group(2).strip()\n            node = self._single_node(label, editable=True)\n            try:\n                if node:\n                    result = self.bridge.action({"type": "set_text", "node": int(node.get("id", -1)), "text": value})\n                else:\n                    tapped = self.bridge.action({"type": "tap_text", "target": label})\n                    result = self.bridge.action({"type": "set_text_best", "text": value}) if isinstance(tapped, dict) and tapped.get("ok") else {"ok": False}\n                if isinstance(result, dict) and result.get("ok"):\n                    self.store.log_event("direct_control", {"type": "form_fill", "label": label[:120]})\n                    return DirectResult(True, "Selesai.", "form_fill")\n            except Exception:\n                pass\n            return DirectResult(False)\n\n        macro = self._try_macro(raw)\n        if macro.handled:\n            return macro\n\n'''
    direct = replace_once(direct, "        # Android Bridge owns scheduling. No Termux daemon is required after\n", recipe_block + "        # Android Bridge owns scheduling. No Termux daemon is required after\n", "recipe execution")
    direct = replace_once(direct, "        if reminders:\n", "        if reminders and self._skill(\"local_reminders\"):\n", "reminder gate")
    direct = replace_once(direct, "        match = _SIMPLE_OPEN.match(raw)\n        if match:\n", "        match = _SIMPLE_OPEN.match(raw)\n        if match and self._skill(\"app_launcher\"):\n", "app launcher gate")
    direct = replace_once(direct, "        if typ:\n            try:\n                result = self._control({\"type\": typ})\n", "        if typ and self._skill(\"quick_navigation\"):\n            try:\n                result = self._control({\"type\": typ})\n", "quick navigation gate")
    direct = replace_once(direct, "        match = _SCROLL.match(raw)\n        if match:\n", "        match = _SCROLL.match(raw)\n        if match and self._skill(\"smart_scroll\"):\n", "smart scroll gate")
    direct = replace_once(direct, "        match = _TAP.match(raw)\n        if match and not _SENSITIVE.search(match.group(1)):\n", "        match = _TAP.match(raw)\n        if match and self._skill(\"semantic_tap\") and not _SENSITIVE.search(match.group(1)):\n", "semantic tap gate")
    direct = replace_once(direct, "        match = _TYPE.match(raw)\n        if match and len(match.group(1)) <= 500:\n", "        match = _TYPE.match(raw)\n        if match and self._skill(\"focused_typing\") and len(match.group(1)) <= 500:\n", "focused typing gate")
    direct_path.write_text(direct, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    count = hub.count('"bridge_target": "1.0.0-rc28"')
    if count < 1:
        raise SystemExit(f"RC47 bridge target marker mismatch: {count}")
    hub = hub.replace('"bridge_target": "1.0.0-rc28"', '"bridge_target": "1.0.0-rc30"')
    hub_path.write_text(hub, encoding="utf-8")
    version_path.write_text(version.replace('VERSION = "1.0.0-rc46"', 'VERSION = "1.0.0-rc47"', 1), encoding="utf-8")

    for path in (settings_path, direct_path, hub_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (settings_path, direct_path, hub_path, version_path))
    required = ('VERSION = "1.0.0-rc47"', '"bridge_target": "1.0.0-rc30"', '"workflow_macros": True', '"label": "Ringkas Layar"', 'def _try_macro(', 'self._skill("local_reminders")', 'self._skill("form_fill")')
    missing = [marker for marker in required if marker not in combined]
    if missing:
        raise SystemExit(f"RC47 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC47_OK")


if __name__ == "__main__":
    main()
