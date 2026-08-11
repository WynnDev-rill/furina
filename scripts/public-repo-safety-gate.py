#!/usr/bin/env python3
"""Fail closed on repository state that is unsafe to publish."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED = {
    ".env",
    "android-wrapper/furina-release.jks.b64",
    "android-wrapper/app/furina-release.jks",
}
FORBIDDEN_SUFFIXES = (".jks", ".keystore", ".p12", ".pfx", ".pem", ".key")


def fail(messages: list[str]) -> None:
    if messages:
        print("Public repository safety gate failed:")
        for message in messages:
            print(f"- {message}")
        raise SystemExit(1)


def main() -> int:
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True
    ).splitlines()
    errors: list[str] = []

    tracked_set = set(tracked)
    for path in sorted(FORBIDDEN_TRACKED & tracked_set):
        errors.append(f"sensitive file must not be tracked: {path}")

    for path in tracked:
        lower = path.lower()
        if lower == ".env.example":
            continue
        if lower.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"private-key/signing file must not be tracked: {path}")

    gradle_path = ROOT / "android-wrapper/app/build.gradle"
    gradle = gradle_path.read_text(encoding="utf-8")
    if re.search(r"\b(?:storePassword|keyPassword)\s+['\"]", gradle):
        errors.append("build.gradle contains a literal signing password")
    if "FURINA_KEYSTORE_PASSWORD" not in gradle or "FURINA_KEY_PASSWORD" not in gradle:
        errors.append("build.gradle must source signing passwords from environment variables")

    workflow_path = ROOT / ".github/workflows/build-furina-apk.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    required_markers = (
        "secrets.FURINA_RELEASE_KEYSTORE_B64",
        "secrets.FURINA_KEYSTORE_PASSWORD",
        "secrets.FURINA_KEY_ALIAS",
        "secrets.FURINA_KEY_PASSWORD",
        "github.event.pull_request.head.repo.full_name == github.repository",
    )
    for marker in required_markers:
        if marker not in workflow:
            errors.append(f"APK workflow missing public-safe signing marker: {marker}")

    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        errors.append(".env.example is required after .env is untracked")
    else:
        text = env_example.read_text(encoding="utf-8")
        privileged_markers = (
            "SERVICE_ROLE",
            "PRIVATE_KEY",
            "KEYSTORE_PASSWORD",
            "KEY_PASSWORD",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
        )
        for marker in privileged_markers:
            if marker in text:
                errors.append(f".env.example contains privileged marker: {marker}")

    fail(errors)
    print("Public repository safety gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
