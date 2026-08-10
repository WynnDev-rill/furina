#!/usr/bin/env python3
"""Wait only for exact-head CI workflows required by the PR diff."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENGINEERING_PREFIXES = ("engineering/", "scripts/", "android-wrapper/")
BUILD_PREFIXES = ("src/", "android-wrapper/", "scripts/", ".agents/")
BUILD_EXACT = {"package.json", "package-lock.json", ".github/workflows/build-furina-apk.yml"}
COMPANION_PREFIX = "android-wrapper/app/src/main/java/com/wynndev/furina/"
COMPANION_EXACT = {
    "scripts/apply-companion-runtime-policy.py",
    "scripts/apply-offline-stability-policy.py",
    "scripts/companion-quality-gate.py",
    "scripts/offline-load-safety-gate.py",
    "scripts/bootstrap-llama-android.sh",
}
COMPANION_PREFIXES = ("scripts/overlays/",)

class CIWaitError(RuntimeError):
    pass

def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise CIWaitError(p.stderr.strip())
    return p.stdout

def changed_paths() -> list[str]:
    return [x for x in git("diff", "--name-only", "origin/main...HEAD").splitlines() if x.strip()]

def required_workflows(paths: list[str]) -> set[str]:
    required = set()
    if any(p.startswith(ENGINEERING_PREFIXES) or p == ".github/workflows/furina-engineering-os.yml" for p in paths):
        required.add("Furina Engineering OS")
    if any(p.startswith(BUILD_PREFIXES) or p in BUILD_EXACT for p in paths):
        required.add("Build Furina Stable APK")
    if any(
        p.startswith(COMPANION_PREFIX) or p.startswith(COMPANION_PREFIXES) or p in COMPANION_EXACT
        for p in paths
    ):
        required.add("Furina Companion Quality Gate")
    return required

def api_runs(repo: str, head: str, token: str) -> list[dict]:
    query = urllib.parse.urlencode({"head_sha": head, "event": "pull_request", "per_page": 100})
    url = f"https://api.github.com/repos/{repo}/actions/runs?{query}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("workflow_runs", [])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CIWaitError(f"Actions API HTTP {exc.code}: {detail[:800]}") from exc

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--discovery-seconds", type=int, default=120)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise CIWaitError("GITHUB_TOKEN missing")

    paths = changed_paths()
    required = required_workflows(paths)
    print("Changed paths:", ", ".join(paths) if paths else "(none)")
    print("Required external CI:", ", ".join(sorted(required)) if required else "(none)")
    if not required:
        return 0

    start = time.monotonic()
    last_report = None

    while True:
        elapsed = time.monotonic() - start
        if elapsed > args.timeout_seconds:
            raise CIWaitError(f"timed out waiting for exact-head CI: {sorted(required)}")

        runs = api_runs(args.repo, args.head, token)
        by_name: dict[str, list[dict]] = {}
        for run in runs:
            by_name.setdefault(run.get("name", ""), []).append(run)

        status = {}
        for name in required:
            candidates = by_name.get(name, [])
            if candidates:
                candidates.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                run = candidates[0]
                status[name] = (run.get("status"), run.get("conclusion"), run.get("id"))
            else:
                status[name] = ("missing", None, None)

        report = json.dumps(status, sort_keys=True)
        if report != last_report:
            print("CI state:", report, flush=True)
            last_report = report

        missing = [name for name, (state, _, _) in status.items() if state == "missing"]
        if missing and elapsed > args.discovery_seconds:
            raise CIWaitError(f"required workflow did not appear for exact head: {missing}")

        failed = [
            name for name, (state, conclusion, _) in status.items()
            if state == "completed" and conclusion not in {"success", "neutral", "skipped"}
        ]
        if failed:
            raise CIWaitError(f"required exact-head CI failed: {failed}")

        if all(state == "completed" and conclusion in {"success", "neutral", "skipped"}
               for state, conclusion, _ in status.values()):
            print("All required exact-head CI passed")
            return 0

        time.sleep(15)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CIWaitError as exc:
        print(f"Furina CI wait failed: {exc}", flush=True)
        raise SystemExit(1)
