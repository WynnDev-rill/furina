#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
CORE = ROOT / "core/furina_agent"
SOURCE = PROJECT / "overrides/core/furina_agent"


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
    path.write_text(text[:start] + replacement.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_once(path: Path, marker: str, value: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if value.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f"{label}: expected one marker, got {text.count(marker)}")
    path.write_text(text.replace(marker, marker + value, 1), encoding="utf-8")


# Performance helpers are copied into the final snapshot. They are deliberately
# separate from the historical patch chain and do not change model artifacts.
for name in ("local_runtime.py", "streaming.py", "performance.py", "stream_state.py", "stream_protocol.py"):
    shutil.copyfile(SOURCE / name, CORE / name)

# Version.
version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.0.1"' not in text:
    raise SystemExit("expected Core 1.0.1 before Local Performance V2")
version.write_text(text.replace('VERSION = "1.0.1"', 'VERSION = "1.0.2"', 1), encoding="utf-8")

# Phone-first defaults. Existing deliberate user overrides survive config
# migration; only old Furina defaults are migrated at runtime.
config = CORE / "config.py"
text = config.read_text(encoding="utf-8")
text = re.sub(r"config_revision: int = \d+", "config_revision: int = 6", text, count=1)
text = re.sub(r"context_size: int = 6144", "context_size: int = 4096", text, count=1)
text = re.sub(r"threads: int = 6", "threads: int = 5", text, count=1)
text = re.sub(r"max_tokens: int = 2048", "max_tokens: int = 1536", text, count=1)
text = re.sub(r"response_continuations: int = 4", "response_continuations: int = 2", text, count=1)
anchor = "    threads: int = 5\n"
extra = (
    "    batch_size: int = 512\n"
    "    ubatch_size: int = 128\n"
    "    cache_reuse: int = 256\n"
    "    flash_attention: str = \"auto\"\n"
    "    accel_backend: str = \"auto\"\n"
    "    keep_warm_seconds: int = 600\n"
    "    prewarm_on_local_select: bool = True\n"
)
if "keep_warm_seconds" not in text:
    if anchor not in text:
        raise SystemExit("config threads anchor missing")
    text = text.replace(anchor, anchor + extra, 1)
# Add migration before final normalization, once.
if "Local Performance V2 migration" not in text:
    marker = '    defaults["max_tokens"] = max(128, min(int(defaults["max_tokens"]), 8192))\n'
    migration = '''    # Local Performance V2 migration: change old Furina defaults only.\n    if revision < 6:\n        if int(raw.get("context_size", 0) or 0) in {0, 6144}: defaults["context_size"] = 4096\n        if int(raw.get("threads", 0) or 0) in {0, 6}: defaults["threads"] = 5\n        if int(raw.get("max_tokens", 0) or 0) in {0, 2048}: defaults["max_tokens"] = 1536\n        if int(raw.get("response_continuations", 0) or 0) in {0, 4}: defaults["response_continuations"] = 2\n\n'''
    if marker not in text:
        raise SystemExit("config normalization marker missing")
    text = text.replace(marker, migration + marker, 1)
# Normalize new fields; dataclass defaults supply them for legacy JSON.
if 'defaults["batch_size"]' not in text:
    marker = '    defaults["context_size"] = max(2048, min(int(defaults["context_size"]), 16384))\n'
    norms = '''    defaults["batch_size"] = max(64, min(int(defaults["batch_size"]), 2048))\n    defaults["ubatch_size"] = max(32, min(int(defaults["ubatch_size"]), defaults["batch_size"]))\n    defaults["cache_reuse"] = max(0, min(int(defaults["cache_reuse"]), 4096))\n    defaults["keep_warm_seconds"] = max(0, min(int(defaults["keep_warm_seconds"]), 3600))\n    defaults["flash_attention"] = str(defaults.get("flash_attention") or "auto").lower()\n    if defaults["flash_attention"] not in {"auto", "on", "off"}: defaults["flash_attention"] = "auto"\n    defaults["accel_backend"] = str(defaults.get("accel_backend") or "auto").lower()\n    if defaults["accel_backend"] not in {"auto", "cpu", "opencl", "vulkan"}: defaults["accel_backend"] = "auto"\n'''
    if marker not in text:
        raise SystemExit("context normalization marker missing")
    text = text.replace(marker, marker + norms, 1)
config.write_text(text, encoding="utf-8")

# Local streaming: patch only the transport function so later companion logic is
# preserved. Closing the active response stops generation while llama-server
# remains warm.
llm = CORE / "llm.py"
text = llm.read_text(encoding="utf-8")
if "from .streaming import SmoothStream" not in text:
    text = text.replace("from .config import Config\n", "from .config import Config\nfrom .streaming import SmoothStream\n", 1)
if "self._active_response = None" not in text:
    text = text.replace("        self.lock = threading.RLock()\n", "        self.lock = threading.RLock()\n        self._active_response = None\n", 1)
if "    def cancel(self) -> None:" not in text:
    marker = "    @property\n    def base_url"
    cancel = '''    def cancel(self) -> None:\n        with self.lock:\n            response = self._active_response\n        if response is not None:\n            try: response.close()\n            except Exception: pass\n\n'''
    if marker not in text:
        raise SystemExit("llm base_url marker missing")
    text = text.replace(marker, cancel + marker, 1)
llm.write_text(text, encoding="utf-8")
replace_function(
    llm,
    "_request_once",
    r'''    def _request_once(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        on_token: Callable[[str], None] | None,
        json_mode: bool = False,
    ) -> tuple[str, str]:
        payload = {
            "model": "local",
            "messages": normalize_messages(messages),
            "temperature": temperature,
            "top_p": self.cfg.top_p,
            "top_k": self.cfg.top_k,
            "min_p": self.cfg.min_p,
            "max_tokens": max_tokens,
            "stream": bool(on_token) and not json_mode,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = None
        smoother = None
        try:
            response = urllib.request.urlopen(req, timeout=180)
            with self.lock:
                self._active_response = response
            with response as r:
                if not payload["stream"]:
                    raw = json.loads(r.read().decode("utf-8"))
                    choice = raw["choices"][0]
                    content = choice.get("message", {}).get("content") or ""
                    return sanitize(content), str(choice.get("finish_reason") or "")
                raw_chunks: list[str] = []
                finish = ""
                smoother = SmoothStream(on_token, frame_ms=22, max_buffer_chars=96) if on_token else None
                stream_filter = _VisibleStreamFilter(smoother.feed) if smoother else None
                for raw_line in r:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data); choice = obj.get("choices", [{}])[0]
                    except Exception:
                        continue
                    finish = str(choice.get("finish_reason") or finish or "")
                    piece = str((choice.get("delta") or {}).get("content") or "")
                    if piece:
                        raw_chunks.append(piece)
                        if stream_filter: stream_filter.feed(piece)
                if stream_filter: stream_filter.finish()
                return sanitize("".join(raw_chunks)), finish
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"llama-server HTTP {e.code}: {body[:700]}") from e
        except Exception as e:
            raise LLMError(f"Tidak dapat menghubungi llama-server: {e}") from e
        finally:
            if smoother: smoother.close()
            with self.lock:
                if self._active_response is response: self._active_response = None''',
)

# Online provider transport now streams native SSE instead of waiting for a
# full answer and replaying it as a single fake chunk.
providers = CORE / "providers.py"
text = providers.read_text(encoding="utf-8")
if "from .streaming import SmoothStream" not in text:
    text = text.replace("from .llm import normalize_messages, sanitize\n", "from .llm import normalize_messages, sanitize\nfrom .streaming import SmoothStream\n", 1)
if "self._active_response = None" not in text:
    text = text.replace("        self.state = ProviderState()\n", "        self.state = ProviderState()\n        self._active_response = None\n", 1)
providers.write_text(text, encoding="utf-8")
replace_function(
    providers,
    "_chat_once",
    r'''    def _chat_once(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        on_token=None,
    ) -> tuple[str, str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": normalize_messages(messages),
            "max_tokens": max_tokens,
            "stream": bool(on_token) and not json_mode,
        }
        if self.name != "gemini": payload["temperature"] = temperature
        if json_mode: payload["response_format"] = {"type": "json_object"}
        self._apply_hidden_reasoning(payload, model)
        if not payload["stream"]:
            try:
                raw = self._json("POST", self.base_url + "/chat/completions", payload, timeout=120)
            except ProviderError as e:
                if json_mode and e.status in {400, 422} and "response_format" in payload:
                    payload.pop("response_format", None)
                    raw = self._json("POST", self.base_url + "/chat/completions", payload, timeout=120)
                else: raise
            try:
                choice = raw["choices"][0]; message = choice.get("message") or {}
                return sanitize(str(message.get("content") or "")), str(choice.get("finish_reason") or "")
            except Exception as e:
                raise ProviderError(self.name, f"Format respons {PROVIDER_LABELS[self.name]} tidak dikenali: {str(raw)[:500]}") from e

        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"), headers=self._headers(), method="POST")
        response = None; smoother = SmoothStream(on_token, frame_ms=22, max_buffer_chars=96)
        chunks: list[str] = []; finish = ""
        try:
            response = urllib.request.urlopen(req, timeout=120); self._active_response = response
            with response as r:
                for raw_line in r:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"): continue
                    data = line[5:].strip()
                    if data == "[DONE]": break
                    try:
                        obj=json.loads(data); choice=obj.get("choices",[{}])[0]
                    except Exception: continue
                    finish=str(choice.get("finish_reason") or finish or "")
                    piece=str((choice.get("delta") or {}).get("content") or "")
                    if piece: chunks.append(piece); smoother.feed(piece)
        except urllib.error.HTTPError as e:
            body=e.read().decode("utf-8",errors="replace")
            raise ProviderError(self.name,f"{PROVIDER_LABELS[self.name]} HTTP {e.code}",status=e.code,body=body[:1200]) from e
        except Exception as e:
            raise ProviderError(self.name,f"{PROVIDER_LABELS[self.name]} tidak dapat dihubungi: {e}") from e
        finally:
            smoother.close(); self._active_response=None
        return sanitize("".join(chunks)), finish''',
)
replace_function(
    providers,
    "chat_model",
    r'''    def chat_model(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
        on_token=None,
    ) -> str:
        normalized = normalize_messages(messages)
        answer, finish = self._chat_once(model, normalized, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode, on_token=on_token)
        if not json_mode:
            for _ in range(self.cfg.response_continuations):
                if finish not in {"length", "max_tokens"}: break
                continuation_messages = list(normalized) + [
                    {"role":"assistant","content":answer[-6000:]},
                    {"role":"user","content":"Lanjutkan tepat dari bagian terakhir tanpa mengulang pembukaan. Berhenti sendiri setelah jawaban benar-benar selesai."},
                ]
                more, finish = self._chat_once(model, continuation_messages, max_tokens=max(384,min(max_tokens,1536)), temperature=temperature, json_mode=False, on_token=on_token)
                if not more: break
                answer=(answer.rstrip()+" "+more.lstrip()).strip()
        answer=sanitize(answer)
        if not answer: raise ProviderError(self.name,f"{PROVIDER_LABELS[self.name]} tidak mengembalikan jawaban final yang dapat ditampilkan")
        self.state.mark_success(self.name,model)
        return answer''',
)

# Runtime/routing integration. The selected model is prewarmed only when Local
# is explicitly active; ordinary Furina startup does no model work.
routing = CORE / "routing.py"
text = routing.read_text(encoding="utf-8")
if "from .local_runtime import get_local_runtime" not in text:
    text = text.replace("from .llm import LocalLLM, LLMError\n", "from .llm import LocalLLM, LLMError\nfrom .local_runtime import get_local_runtime\n", 1)
if "self.runtime = get_local_runtime" not in text:
    text = text.replace("        self.local = LocalLLM(cfg)\n", "        self.local = LocalLLM(cfg)\n        self.runtime = get_local_runtime(cfg, lambda: Path(self.cfg.model_path) if self.cfg.model_path else None)\n        self._active_online_provider = None\n", 1)
routing.write_text(text, encoding="utf-8")
replace_function(
    routing,
    "_ensure_local",
    r'''    def _ensure_local(self, on_status=None) -> bool:
        if self.local.health():
            self.runtime.touch(); return True
        if not self.cfg.model_path or not Path(self.cfg.model_path).exists(): return False
        return self.runtime.ensure_ready(timeout=45.0, status_cb=on_status)''',
)
replace_function(
    routing,
    "_online_chat",
    r'''    def _online_chat(self, messages, *, max_tokens: int, temperature: float, json_mode: bool = False, on_token=None) -> str:
        self.last_failures = []
        configured = self.configured_online()
        if not configured: raise LLMError("Belum ada API key online yang dikonfigurasi.")
        emitted = 0
        def emit(piece):
            nonlocal emitted
            emitted += len(piece or "")
            if on_token: on_token(piece)
        for name in configured:
            key=self.secrets.get(name)
            if not key: continue
            provider=OpenAICompatibleProvider(name,key,self.cfg); self._active_online_provider=provider
            try: candidates=provider.candidate_models()
            except ProviderError as e:
                self.last_failures.append(f"{name}: {provider_error_summary(e)}"); continue
            for candidate in candidates:
                try:
                    answer=provider.chat_model(candidate.id,messages,max_tokens=max_tokens,temperature=temperature,json_mode=json_mode,on_token=None if json_mode else emit)
                    self.last=RouteResult(name,candidate.id); self._active_online_provider=None; return answer
                except ProviderError as e:
                    self.last_failures.append(f"{name}/{candidate.id}: {provider_error_summary(e)}")
                    # Never fail over after visible text has streamed; doing so
                    # would duplicate/rewrite the user's partial response.
                    if emitted: self._active_online_provider=None; raise LLMError(self.last_failures[-1]) from e
                    if e.invalid_key or e.status is None: break
                    continue
        self._active_online_provider=None
        detail="; ".join(self.last_failures[-5:])
        raise LLMError("Semua provider online gagal"+(f": {detail}" if detail else ""))''',
)
replace_function(
    routing,
    "chat",
    r'''    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        on_token=None,
        json_mode: bool = False,
        role: str | None = None,
        on_status=None,
    ) -> str:
        max_tokens=self.cfg.max_tokens if max_tokens is None else max_tokens
        temperature=self.cfg.temperature if temperature is None else temperature
        role=self._normalize_role(role,messages,json_mode)
        if self.cfg.routing_mode == "local":
            if not self._ensure_local(on_status=on_status):
                raise LLMError("Model lokal belum siap. Buka Provider & Model, pastikan model sudah diunduh lalu pilih kembali.")
            if on_status: on_status("Menjawab…")
            answer=self.local.chat(messages,max_tokens=max_tokens,temperature=temperature,on_token=on_token,json_mode=json_mode)
            self.runtime.touch(); self._record("local",Path(self.cfg.model_path).name or "GGUF",role); return answer
        if not self.secrets.configured(): raise LLMError("Provider online belum dikonfigurasi. Buka Provider & Model untuk menambahkan API key.")
        if on_status: on_status("Menjawab…")
        return self._online_chat(messages,max_tokens=max_tokens,temperature=temperature,json_mode=json_mode,role=role,on_token=on_token)''',
)
# The 1.0.1 routing helper takes role; normalize call signature if present in
# generated stage by removing an unsupported role argument from this replacement.
rtext = routing.read_text(encoding="utf-8")
rtext = rtext.replace("json_mode=json_mode,role=role,on_token=on_token)", "json_mode=json_mode,on_token=on_token)")
# Add lifecycle methods once before health().
if "    def prewarm_local(self)" not in rtext:
    marker = "    def health(self) -> bool:\n"
    methods = '''    def prewarm_local(self) -> None:\n        if self.cfg.routing_mode == "local": self.runtime.prewarm()\n\n    def stop_local(self) -> None:\n        self.runtime.stop()\n\n    def cancel(self) -> None:\n        self.local.cancel()\n        provider=self._active_online_provider\n        if provider and getattr(provider,"_active_response",None) is not None:\n            try: provider._active_response.close()\n            except Exception: pass\n\n'''
    if marker not in rtext: raise SystemExit("routing health marker missing")
    rtext = rtext.replace(marker, methods + marker, 1)
routing.write_text(rtext, encoding="utf-8")

# TUI selection starts preparing the chosen local model in the background.
tui = CORE / "tui.py"
text = tui.read_text(encoding="utf-8")
old = '            save_config(cfg)\n            console.print(f"[green]Aktif[/]  {row[\'name\']} akan dimuat saat chat lokal pertama dikirim.")'
new = '''            save_config(cfg)\n            try:\n                from .routing import RoutingLLM\n                RoutingLLM(cfg).prewarm_local()\n                console.print(f"[green]Aktif[/]  {row['name']} sedang disiapkan di background.")\n            except Exception:\n                console.print(f"[green]Aktif[/]  {row['name']} akan disiapkan saat chat dibuka.")'''
if old in text: text = text.replace(old,new,1)
elif "sedang disiapkan di background" not in text: raise SystemExit("TUI local-select marker missing")
tui.write_text(text,encoding="utf-8")

# FurinaHub uses the same prewarm state. saveCore remains the source of truth;
# /api/models prewarm merely starts the selected model without changing config.
hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if "from .routing import RoutingLLM" not in text:
    marker = "from .hub_web import HTML"
    text = text.replace(marker, marker + "\nfrom .routing import RoutingLLM", 1)
needle = '        action = str(payload.get("action") or "").strip().lower()\n'
if 'action == "prewarm"' not in text:
    add = '''        if action == "prewarm":\n            cfg = load_config()\n            if cfg.routing_mode != "local" or not cfg.model_path:\n                return {"ok": False, "state": "idle", "message": "Model lokal belum dipilih."}\n            RoutingLLM(cfg).prewarm_local()\n            return {"ok": True, "state": "loading", "message": "Menyiapkan model lokal…"}\n        if action == "stop-generation":\n            RoutingLLM(load_config()).cancel()\n            return {"ok": True, "state": "stopped"}\n'''
    if needle not in text: raise SystemExit("hub change_model action marker missing")
    # Target the occurrence inside change_model; private 1.0.1 only has one.
    text = text.replace(needle, needle + add, 1)
hub.write_text(text,encoding="utf-8")

print("FURINA_PRIVATE_1_0_2_LOCAL_PERFORMANCE_OK")
