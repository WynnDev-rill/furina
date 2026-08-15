#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC30 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    for path in (html_path, gradle, main_activity):
        if not path.is_file():
            raise SystemExit(f"RC30 source missing: {path}")

    html = html_path.read_text(encoding="utf-8")
    polish = r'''
/* RC30: single-owner WindowInsets + tighter native layout */
html,body{height:100%;min-height:0}.app{height:100%;min-height:0}.content{height:100%;min-height:0;display:flex;flex-direction:column}.chatview{height:100%;min-height:0;flex:1}.view{padding-top:10px;padding-bottom:88px}.messages{padding-top:12px}.composer{padding:7px 12px 7px}.drawer{padding:14px 10px 14px}.sheet{bottom:10px}.sheet.compact{bottom:72px}.viewerActions{padding-bottom:12px}.editorBottom{padding-bottom:12px}.toast{bottom:84px}
.nav[data-view="plugins"] svg{width:20px;height:20px;flex:none;color:currentColor}
@media(max-width:380px){.view{padding-top:8px}.composer{padding-left:10px;padding-right:10px}}
'''
    html = replace_once(html, "</style>", polish + "\n</style>", "inset polish CSS")

    pattern = re.compile(r'<button class="nav" data-view="plugins" onclick="go\(\'plugins\'\)"><img[^>]*>Plugin</button>')
    replacement = '<button class="nav" data-view="plugins" onclick="go(\'plugins\')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4v5M15 4v5M7 9h10v3a5 5 0 0 1-5 5 5 5 0 0 1-5-5V9ZM12 17v3"/></svg>Plugin</button>'
    html, count = pattern.subn(replacement, html, count=1)
    if count != 1:
        if 'data-view="plugins"' not in html or 'M9 4v5M15 4v5' not in html:
            raise SystemExit(f"RC30 plugin icon marker mismatch: {count}")

    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10029", "versionCode 10030", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc29'", "versionName '1.0.0-rc30'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = {
        html_path: (
            "RC30: single-owner WindowInsets",
            ".chatview{height:100%",
            ".composer{padding:7px 12px 7px}",
            ".drawer{padding:14px 10px 14px}",
            'data-view="plugins"',
            "M9 4v5M15 4v5",
        ),
        gradle: ("versionCode 10030", "versionName '1.0.0-rc30'"),
        main_activity: ("webFrame.setPadding(0, 0, 0, bottomInset);", "setOnApplyWindowInsetsListener"),
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"RC30 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_ANDROID_RC30_OK")


if __name__ == "__main__":
    main()
