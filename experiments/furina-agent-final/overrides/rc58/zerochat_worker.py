#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("furina_vendored_zerochat_memory", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ZeroChat memory_service.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main() -> None:
    req = json.loads(sys.stdin.readline())
    upstream = Path(req["upstream"]).resolve()
    data_root = Path(req["data_root"]).resolve()
    data_root.mkdir(parents=True, exist_ok=True)

    seq = 0
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    ai_service = types.ModuleType("services.ai_service")

    async def call_ai(messages, temperature=0.3, **kwargs):
        nonlocal seq
        seq += 1
        emit({
            "event": "llm_request",
            "id": seq,
            "messages": messages,
            "temperature": float(temperature or 0.3),
        })
        while True:
            line = sys.stdin.readline()
            if not line:
                return {"success": False, "content": "", "error": "parent closed"}
            answer = json.loads(line)
            if answer.get("event") == "llm_response" and answer.get("id") == seq:
                if answer.get("error"):
                    return {"success": False, "content": "", "error": str(answer["error"])}
                return {"success": True, "content": str(answer.get("text", "")), "error": None}

    ai_service.call_ai = call_ai
    services_pkg.ai_service = ai_service
    sys.modules["services"] = services_pkg
    sys.modules["services.ai_service"] = ai_service

    mod = load_module(upstream / "server/services/memory_service.py")
    # Keep the upstream implementation unchanged while redirecting only its
    # storage roots into Furina's private data directory.
    mod.DATA_DIR = data_root
    mod.ROLES_DIR = data_root / "roles"

    role_id = str(req.get("role_id") or "furina")
    op = str(req.get("op") or "context")
    if op == "update":
        user_text = str(req.get("user_text") or "").strip()
        answer = str(req.get("answer") or "").strip()
        if user_text:
            mod.append_short_term(role_id, "user", user_text)
        if answer:
            mod.append_short_term(role_id, "assistant", answer)
        if bool(req.get("allow_summary", True)) and mod.should_summarize(role_id):
            await mod.trigger_memory_summary(role_id, {})

    memory = mod.load_memory(role_id)
    emit({
        "event": "done",
        "context": mod.get_memory_context_string(role_id),
        "core_memory": mod.get_core_memory(role_id),
        "short_term_count": len(memory.get("short_term", [])),
        "message_count_since_summary": int(memory.get("message_count_since_summary", 0) or 0),
    })


if __name__ == "__main__":
    asyncio.run(main())
