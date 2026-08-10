#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "engineering/evals/companion-scenarios.json"


def load() -> dict:
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1:
        raise SystemExit("unsupported behavioral benchmark schema")
    return data


def inputs_manifest(data: dict) -> dict:
    return {
        "schemaVersion": 1,
        "benchmarkVersion": str(data["schemaVersion"]),
        "scenarios": [
            {
                "scenarioId": scenario["id"],
                "setup": scenario["setup"],
                "user": scenario["user"],
            }
            for scenario in data["scenarios"]
        ],
    }


def judge_manifest(data: dict) -> dict:
    return {
        "schemaVersion": 1,
        "benchmarkVersion": str(data["schemaVersion"]),
        "rubric": data["rubric"],
        "scenarios": [
            {
                "scenarioId": scenario["id"],
                "category": scenario["category"],
                "expect": scenario["expect"],
            }
            for scenario in data["scenarios"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Furina behavioral benchmark manifests")
    parser.add_argument("mode", choices=("inputs", "judge"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    data = load()
    manifest = inputs_manifest(data) if args.mode == "inputs" else judge_manifest(data)
    print(json.dumps(manifest, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
