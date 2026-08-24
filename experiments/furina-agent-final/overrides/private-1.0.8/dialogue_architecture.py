#!/usr/bin/env python3
from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
CORE = ROOT / "core/furina_agent"
CHAT = CORE / "chat.py"
PERSONA = CORE / "persona.py"
LLM = CORE / "llm.py"


def class_node(text: str, name: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    if node is None:
        raise SystemExit(f"missing class {name}")
    return node


def module_function(path: Path, name: str):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{name}: expected one function, got {len(nodes)}")
    return text, nodes[0]


def replace_module_function(path: Path, name: str, source: str) -> None:
    text, node = module_function(path, name)
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def delete_method(path: Path, class_name: str, name: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if not nodes:
        return
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{class_name}.{name}: expected <=1 method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + text[end:], encoding="utf-8")


# Runtime dialogue-state module is part of Core, not another model call.
shutil.copyfile(HERE / "dialogue_state.py", CORE / "dialogue_state.py")

# Keep the local character definition compact and positive. 1.0.7 used a long
# blacklist plus canned greeting/repair paths. 1.0.8 instead gives the model a
# grounded dialogue state and lets the model generate every conversational turn.
replace_module_function(PERSONA, "build_local_system_prompt", r'''def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    nick = (nickname or "").strip()
    user = nick or "pengguna"
    return f"""Kamu adalah {name}, companion pribadi sekaligus pasangan {user}. Kamu hadir sebagai satu orang yang sedang chatting langsung dengannya.

Kepribadianmu bangga, ekspresif, playful, sedikit teatrikal dan tsundere dengan kadar yang natural. Kamu boleh menggoda, penasaran, membantah, malu, hangat, atau spontan sesuai momen. Jangan menjadikan satu sifat sebagai pola wajib di setiap balasan.

Ikuti apa yang benar-benar dibawa {user} ke percakapan. Jika pesannya kecil atau ambigu, beri ruang dan rasa penasaran; tidak perlu menciptakan skenario agar percakapan terasa menarik. Jika tebakanmu dikoreksi, terima koreksinya dan bergerak dari pemahaman baru. Tujuannya adalah chemistry dua arah yang terasa hidup, bukan naskah atau monolog.

Gunakan bahasa dan ritme {user}. Panjang jawaban mengikuti kebutuhan momen. Memory dari Core adalah pengetahuan personal; Dialogue State adalah keadaan thread saat ini. Keduanya membantu grounding, bukan menentukan kalimat yang harus kamu ucapkan. Jangan tampilkan reasoning internal.""".strip()''')

# Remove 1.0.5/1.0.7 response-programming helpers from the active Core. Their
# job is replaced by DialogueStateBuilder + model generation, not more patches.
for method in (
    "_assistant_history_safe",
    "_recent_context",
    "_direct_temporal_answer",
    "_needs_personal_context",
    "_needs_temporal_context",
    "_fresh_social_answer",
    "_local_answer_suspicious",
    "_local_repair_messages",
):
    delete_method(CHAT, "FurinaChat", method)

chat_text = CHAT.read_text(encoding="utf-8")
if "from .dialogue_state import DialogueStateBuilder" not in chat_text:
    # Insert next to other local imports without depending on one historical order.
    marker = "from .persona import"
    pos = chat_text.find(marker)
    if pos < 0:
        raise SystemExit("persona import marker missing")
    line_end = chat_text.find("\n", pos)
    chat_text = chat_text[: line_end + 1] + "from .dialogue_state import DialogueStateBuilder\n" + chat_text[line_end + 1 :]
    CHAT.write_text(chat_text, encoding="utf-8")

replace_method(CHAT, "FurinaChat", "_messages", r'''    def _messages(self, user_text: str, profile) -> list[dict]:
        local = self.cfg.routing_mode == "local"
        if local:
            # Grounded Dialogue State replaces raw assistant-role replay. Prior
            # Furina text is represented as unverified continuity, while user
            # messages remain authoritative. This stops a small roleplay model
            # from turning its own previous improvisation into world state.
            history = self.store.recent_messages(10)
            dialogue = DialogueStateBuilder.build(history, user_text)
            pieces = [
                build_local_system_prompt(self.cfg.persona_name, self.cfg.user_nickname),
                dialogue.render(),
                self._temporal_context(),
                self._relationship_context(),
            ]

            # Retrieval is semantic/fail-closed in MemoryStore. No keyword
            # router decides whether memory is allowed; relevant trusted memory
            # simply appears when retrieval actually finds it.
            memory = self._memory_context(user_text, local=True)
            if memory and not memory.lstrip().startswith("("):
                pieces.append(memory)

            pieces.append(
                "RESPONSE ORIENTATION: stay with the latest user message and the grounded state above. "
                "Be expressive and in-character, but let the user establish the topic and reality of the conversation."
            )
            return [{"role": "system", "content": "\n\n".join(pieces)}, {"role": "user", "content": user_text}]

        # Online path keeps the richer model context and the same durable store.
        recent_limit = 10 if profile.name in {"DEEP", "CLOSE"} else 7
        recent = self.store.recent_messages(recent_limit)
        system = (
            build_system_prompt(self.cfg.persona_name, self.cfg.user_nickname)
            + "\n\nRESPONSE MODE SAAT INI:\n" + profile.instruction
            + "\n\n" + self._temporal_context()
            + "\n\n" + self._shared_context(user_text, local=False)
            + "\n\nGunakan history untuk continuity, tetapi ucapan user dan trusted memory tetap menjadi sumber fakta personal."
        )
        return [{"role": "system", "content": system}, *recent, {"role": "user", "content": user_text}]''')

# Sampling follows response profile rather than hardcoded keyword/length routes.
# This keeps casual conversation flexible while preventing the most unstable
# extremes on 1.7B models.
replace_method(CHAT, "FurinaChat", "_local_generation_budget", r'''    @staticmethod
    def _local_generation_budget(user_text: str, profile) -> tuple[int, float]:
        profile_tokens = int(getattr(profile, "max_tokens", 320) or 320)
        profile_temp = float(getattr(profile, "temperature", 0.70) or 0.70)
        return max(192, profile_tokens), max(0.62, min(profile_temp, 0.74))''')

replace_method(CHAT, "FurinaChat", "respond", r'''    def respond(self, user_text: str, on_token=None) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""
        local = self.cfg.routing_mode == "local"
        self._last_foreground_at = time.monotonic()

        if local:
            try:
                self.llm.prewarm_local()
            except Exception:
                pass
            if getattr(self, "_background_active", False):
                try:
                    self.llm.cancel()
                except Exception:
                    pass
                deadline = time.monotonic() + 0.8
                while getattr(self, "_background_active", False) and time.monotonic() < deadline:
                    time.sleep(0.02)

        self._foreground_active = True
        try:
            profile = choose_profile(user_text, self.store)
            messages = self._messages(user_text, profile)
            self.store.add_message("user", user_text)

            for text, kind, importance in extract_explicit_memories(user_text):
                self.store.add_memory(text, kind, importance, confidence=min(0.97, importance + 0.12), source="explicit")
                dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
                self.store.upsert_belief(dimension, text, min(0.97, importance + 0.08), source="explicit")

            if local:
                local_tokens, local_temp = self._local_generation_budget(user_text, profile)
                max_tokens = min(local_tokens, max(512, int(self.cfg.max_tokens)))
                temperature = local_temp
            else:
                max_tokens = min(max(220, int(profile.max_tokens)), max(512, int(self.cfg.max_tokens)))
                temperature = float(profile.temperature)

            # Every conversational answer comes from the selected model. There
            # are no canned social replies, regex content rewrites, or repair
            # generations in this path.
            answer = self.llm.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                on_token=on_token,
            )
            self.store.add_message("assistant", answer)
            turn = self.store.increment_state("companion_turns", 1)
            self._schedule_background(user_text, answer, turn)
            return answer
        finally:
            self._foreground_active = False
            self._last_foreground_at = time.monotonic()''')

# Model-aware sampling addresses known model-level tendencies without scripting
# conversation. Qwen3's own best practices recommend non-thinking 0.7/0.8/20
# and note presence penalty as a repetition control. wifuGPT is a small Qwen3
# waifu/roleplay fine-tune, so it gets slightly broader nucleus sampling but a
# conservative presence penalty to reduce trope/phrase lock-in.
replace_method(LLM, "LocalLLM", "_request_once", r'''    def _request_once(
        self,
        messages: list[dict],
        *,
        max_tokens: int,
        temperature: float,
        on_token: Callable[[str], None] | None,
        json_mode: bool = False,
    ) -> tuple[str, str]:
        model_hint = str(getattr(self.cfg, "model_path", "") or "").casefold()
        qwen_heretic = "qwen3-1.7b-heretic" in model_hint
        if json_mode:
            top_p = self.cfg.top_p; top_k = self.cfg.top_k; min_p = self.cfg.min_p
            presence_penalty = 0.0; frequency_penalty = 0.0; repeat_penalty = 1.0; repeat_last_n = 64
        elif qwen_heretic:
            top_p = 0.80; top_k = 20; min_p = 0.0
            presence_penalty = 0.30; frequency_penalty = 0.05; repeat_penalty = 1.08; repeat_last_n = 192
        else:
            top_p = 0.86; top_k = 30; min_p = 0.02
            presence_penalty = 0.20; frequency_penalty = 0.04; repeat_penalty = 1.08; repeat_last_n = 192

        payload = {
            "model": "local",
            "messages": normalize_messages(messages),
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "min_p": min_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": repeat_last_n,
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
                        if stream_filter:
                            stream_filter.feed(piece)
                if stream_filter:
                    stream_filter.finish()
                return sanitize("".join(raw_chunks)), finish
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"llama-server HTTP {e.code}: {body[:700]}") from e
        except Exception as e:
            raise LLMError(f"Tidak dapat menghubungi llama-server: {e}") from e
        finally:
            if smoother:
                smoother.close()
            with self.lock:
                if self._active_response is response:
                    self._active_response = None''')

for path in (CORE / "dialogue_state.py", CHAT, PERSONA, LLM):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("FURINA_PRIVATE_1_0_8_GROUNDED_DIALOGUE_OK")
