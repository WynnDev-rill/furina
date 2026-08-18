#!/usr/bin/env python3
from __future__ import annotations
import asyncio, importlib.util, json, os, sys, types
from pathlib import Path


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def install_compat_stubs(mode: int, batch: int):
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    sys.modules["torch"] = torch
    sys.modules["numpy"] = types.ModuleType("numpy")
    st = types.ModuleType("sentence_transformers")
    class SentenceTransformer:
        def __init__(self, *a, **k):
            raise RuntimeError("embedding disabled in Furina Termux sidecar")
    st.SentenceTransformer = SentenceTransformer
    sys.modules["sentence_transformers"] = st
    app_pkg = types.ModuleType("app"); app_pkg.__path__ = []
    cfg_pkg = types.ModuleType("app.configuration"); cfg_pkg.__path__ = []
    cfg_mod = types.ModuleType("app.configuration.configuration")
    class ConfigurationCharacters:
        def load_configuration(self): return {"character_list": {"Furina": {"current_chat": "default"}}}
    class ConfigurationSettings:
        def get_main_setting(self, key):
            if key == "soul_memory_mode": return mode
            if key == "soul_memory_batch": return batch
            return None
    cfg_mod.ConfigurationCharacters = ConfigurationCharacters
    cfg_mod.ConfigurationSettings = ConfigurationSettings
    cfg_pkg.configuration = cfg_mod; app_pkg.configuration = cfg_pkg
    sys.modules["app"] = app_pkg
    sys.modules["app.configuration"] = cfg_pkg
    sys.modules["app.configuration.configuration"] = cfg_mod


def load_upstream(path: Path):
    spec = importlib.util.spec_from_file_location("furina_vendored_soul_memory", path)
    if spec is None or spec.loader is None: raise RuntimeError("cannot load Soul Memory upstream")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


async def main():
    request = json.loads(sys.stdin.readline())
    upstream = Path(request["upstream"]).resolve()
    data_root = Path(request["data_root"]).resolve(); data_root.mkdir(parents=True, exist_ok=True)
    os.chdir(data_root)
    mode = int(request.get("mode", 1)); batch = int(request.get("batch", 4))
    install_compat_stubs(mode, batch)
    mod = load_upstream(upstream / "app/utils/soul_memory.py")
    seq = 0

    async def llm_generate(messages):
        nonlocal seq
        seq += 1
        emit({"event": "llm_request", "id": seq, "messages": messages, "json_mode": True, "temperature": 0.10})
        while True:
            line = sys.stdin.readline()
            if not line: raise RuntimeError("parent closed during LLM request")
            reply = json.loads(line)
            if reply.get("event") == "llm_response" and reply.get("id") == seq:
                if reply.get("error"): raise RuntimeError(str(reply["error"]))
                return str(reply.get("text", ""))

    agent = mod.SoulMemoryAgent(llm_generate)
    character = str(request.get("character") or "Furina")
    user = str(request.get("user") or "User")
    chat_id = str(request.get("chat_id") or "default")
    if request.get("op", "context") == "update":
        await agent.update_memory_after_response(
            request.get("messages") or [], character, user,
            activated_lorebook=None, force=bool(request.get("force", False)), chat_id=chat_id,
        )
    emit({"event":"done","context":agent.get_full_memory_context(character,chat_id),"profile":agent.get_user_profile(character,chat_id),"stats":agent.get_memory_stats(character,chat_id)})


if __name__ == "__main__": asyncio.run(main())
