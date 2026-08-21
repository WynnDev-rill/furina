#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


BUNDLE_ID = "furina-2026.08.21-rc62-rc50"
DATEPARSER_VERSION = "1.4.2"


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC62 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    version_path = core / "version.py"
    prospective_path = core / "prospective.py"
    hub_path = core / "hub.py"
    for path in (version_path, prospective_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"RC62 source missing: {path}")

    version = once(
        version_path.read_text(encoding="utf-8"),
        'VERSION = "1.0.0-rc61"',
        'VERSION = "1.0.0-rc62"',
        "core version",
    )

    prospective = prospective_path.read_text(encoding="utf-8")
    prospective = once(
        prospective,
        "import time\n",
        '''import time

try:
    import dateparser
    from dateparser.search import search_dates
except ImportError:  # Installer binds 1.4.2; fallback preserves recovery installs.
    dateparser = None
    search_dates = None

DATEPARSER_VERSION = "1.4.2"
''',
        "dateparser import",
    )
    helper = '''def _dateparser_future(raw: str, current: dt.datetime) -> dt.datetime | None:
    if search_dates is None:
        return None
    normalized = raw.lower()
    numbers = {
        "satu": "1", "dua": "2", "tiga": "3", "empat": "4", "lima": "5",
        "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
    }
    for word, number in numbers.items():
        normalized = re.sub(rf"\\b{word}\\b", number, normalized)
    for name, hour in _DAYPART.items():
        normalized = re.sub(rf"\\b{name}\\b", f"{hour:02d}:00", normalized)
    try:
        found = search_dates(
            normalized,
            languages=["id", "en"],
            settings={
                "RELATIVE_BASE": current,
                "PREFER_DATES_FROM": "future",
                "USE_GIVEN_LANGUAGE_ORDER": True,
                "IGNORE_SURROUNDING_TEXT": True,
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
            strategy="ngram",
        ) or []
    except (TypeError, ValueError, OverflowError):
        return None
    candidates = [
        parsed for _, parsed in found
        if isinstance(parsed, dt.datetime) and parsed.timestamp() > current.timestamp() + 30
    ]
    return min(candidates) if candidates else None


'''
    prospective = once(
        prospective,
        "def extract_prospectives(text: str, now: float | None = None) -> list[tuple[str, float]]:\n",
        helper + "def extract_prospectives(text: str, now: float | None = None) -> list[tuple[str, float]]:\n",
        "dateparser helper",
    )
    prospective = once(
        prospective,
        "    due: dt.datetime | None = None\n\n    relative = _IN.search(low) or _LATER.search(low)",
        "    due: dt.datetime | None = _dateparser_future(raw, current)\n\n    relative = None if due else (_IN.search(low) or _LATER.search(low))",
        "dateparser primary path",
    )
    prospective = once(
        prospective,
        "    else:\n        date_match = _DATE.search(low)",
        "    elif due is None:\n        date_match = _DATE.search(low)",
        "manual parser fallback",
    )

    hub = hub_path.read_text(encoding="utf-8")
    bootstrap_old = '            "core_version": VERSION,\n            "bridge_target": "1.0.0-rc49",'
    if bootstrap_old not in hub:
        bootstrap_old = '            "core_version": VERSION,\n            "bridge_target": "1.0.0-rc48",'
    hub = once(
        hub,
        bootstrap_old,
        f'            "core_version": VERSION,\n            "bundle_id": "{BUNDLE_ID}",\n            "bridge_target": "1.0.0-rc50",',
        "bootstrap bundle id",
    )
    hub = once(
        hub,
        '''        try:
            dependency_revision = revision_path.read_text(encoding="utf-8").strip()
        except Exception:
            dependency_revision = "belum diperiksa"
''',
        '''        try:
            dependency_revision = revision_path.read_text(encoding="utf-8").strip()
        except Exception:
            dependency_revision = "belum diperiksa"
        bundle_path = HOME / "data" / "bundle_id"
        try:
            bundle_id = bundle_path.read_text(encoding="utf-8").strip()
        except Exception:
            bundle_id = ""
        bridge_bundle_id = str(bridge.get("bundle_id") or "")
''',
        "shared bundle state",
    )
    hub = once(
        hub,
        '''            "core_version": VERSION,
            "bridge_target": "1.0.0-rc45",
            "dependency_revision": dependency_revision,
            "bridge": bridge,
''',
        f'''            "core_version": VERSION,
            "bundle_id": bundle_id,
            "expected_bundle_id": "{BUNDLE_ID}",
            "bridge_bundle_id": bridge_bundle_id,
            "bundle_synced": bundle_id == "{BUNDLE_ID}" and bridge_bundle_id == "{BUNDLE_ID}",
            "bridge_target": "1.0.0-rc50",
            "dependency_revision": dependency_revision,
            "bridge": bridge,
''',
        "system bundle state",
    )

    checks = (
        'VERSION = "1.0.0-rc62"', 'DATEPARSER_VERSION = "1.4.2"',
        "search_dates(", '"IGNORE_SURROUNDING_TEXT": True', 'languages=["id", "en"]',
        f'"expected_bundle_id": "{BUNDLE_ID}"', '"bundle_synced":',
    )
    combined = "\n".join((version, prospective, hub))
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit("RC62 integration incomplete: " + ", ".join(missing))

    version_path.write_text(version, encoding="utf-8")
    prospective_path.write_text(prospective, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")
    print("FURINA_RC62_DATEPARSER_BUNDLE_STATE_OK")


if __name__ == "__main__":
    main()
