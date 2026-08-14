#!/usr/bin/env python3
from __future__ import annotations
import pathlib, sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"RC23 marker mismatch {label}: {n}")
    return text.replace(old, new, 1)


def block(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        if new.strip() in text:
            return text
        raise SystemExit(f"RC23 block marker missing {label}")
    return text[:a] + new.rstrip() + "\n\n" + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-semantic-core-rc23.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    companion = core / "companion.py"
    direct = core / "direct_control.py"
    agent = core / "agent.py"
    chat_surface = core / "chat_surface.py"
    version = core / "version.py"
    for p in (companion, direct, agent, chat_surface, version):
        if not p.is_file():
            raise SystemExit(f"missing RC23 source: {p}")

    # Direct mode is only an atomic latency optimization. It must never accept
    # a longer phrase merely because it starts with an installed app label.
    d = direct.read_text(encoding="utf-8")
    d = rep(
        d,
        '''    def _resolve_app(self, name: str) -> str:\n        wanted = " ".join(str(name or "").casefold().split()).strip(" .!?")\n''',
        '''    def _resolve_app(self, name: str, *, exact: bool = False) -> str:\n        wanted = " ".join(str(name or "").casefold().split()).strip(" .!?")\n''',
        "app resolver signature",
    )
    d = rep(
        d,
        '''            if label == wanted:\n                score = 100\n            elif package.casefold() == wanted:\n                score = 100\n            elif label.startswith(wanted) or wanted.startswith(label):\n                score = 80\n            elif wanted in label:\n                score = 65\n            elif wanted in package.casefold():\n                score = 55\n''',
        '''            if label == wanted:\n                score = 100\n            elif package.casefold() == wanted:\n                score = 100\n            elif not exact and (label.startswith(wanted) or wanted.startswith(label)):\n                score = 80\n            elif not exact and wanted in label:\n                score = 65\n            elif not exact and wanted in package.casefold():\n                score = 55\n''',
        "exact app resolution",
    )
    d = rep(d, "            package = self._resolve_app(match.group(1))\n", "            package = self._resolve_app(match.group(1), exact=True)\n", "atomic open exact")
    insert = '''    def try_execute_step(self, step: dict) -> DirectResult:\n        """Execute only a semantically parsed, atomic low-risk primitive."""\n        if not isinstance(step, dict):\n            return DirectResult(False)\n        typ = str(step.get("type") or "")\n        if typ == "open_app":\n            package = str(step.get("package") or "").strip()\n            if not package or package not in {str(x.get("package") or "") for x in self._apps()}:\n                return DirectResult(False)\n            try:\n                result = self._control({"type": "open_app", "package": package})\n                if isinstance(result, dict) and result.get("ok"):\n                    self.store.log_event("direct_control", {"type": "open_app", "package": package, "semantic": True})\n                    return DirectResult(True, "Selesai.")\n            except Exception:\n                pass\n            return DirectResult(False)\n        if typ in {"back", "home", "recents"}:\n            try:\n                result = self._control({"type": typ})\n                if isinstance(result, dict) and result.get("ok"):\n                    self.store.log_event("direct_control", {"type": typ, "semantic": True})\n                    return DirectResult(True, "Selesai.")\n            except Exception:\n                pass\n        return DirectResult(False)\n\n'''
    marker = "    def try_execute(self, text: str) -> DirectResult:\n"
    if insert.strip() not in d:
        if d.count(marker) != 1:
            raise SystemExit("RC23 direct insertion marker mismatch")
        d = d.replace(marker, insert + marker, 1)
    direct.write_text(d, encoding="utf-8")

    # Semantic router: no growing verb/app vocabulary is authoritative for
    # understanding. The model returns a compact canonical intent and steps;
    # fuzzy matching is limited to resolving an app name against installed apps.
    c = companion.read_text(encoding="utf-8")
    c = rep(c, "from dataclasses import dataclass\n", "from dataclasses import dataclass, field\nfrom difflib import SequenceMatcher\n", "semantic imports")
    c = block(
        c,
        "_DEVICE_VERBS = re.compile(\n",
        "\n\n@dataclass\nclass Intent:\n",
        '''@dataclass\nclass Intent:\n    mode: str\n    goal: str\n    confidence: float = 0.0\n    steps: list[dict] = field(default_factory=list)\n    requires_screen: bool = False\n''',
        "remove lexical intent tables",
    )
    duplicate = '''@dataclass\nclass Intent:\n    mode: str\n    goal: str\n    confidence: float = 0.0\n\n\n'''
    if duplicate in c:
        c = c.replace(duplicate, "", 1)
    old_helper_start = c.find("def _obvious_device_intent(text: str) -> bool:\n")
    old_helper_end = c.find("def _first_json_object(raw: str) -> dict | None:\n", old_helper_start) if old_helper_start >= 0 else -1
    if old_helper_start >= 0 and old_helper_end > old_helper_start:
        c = c[:old_helper_start] + c[old_helper_end:]

    semantic_helpers = '''    def _installed_apps(self) -> list[dict]:\n        try:\n            raw = self.bridge.apps()\n            apps = raw.get("apps") if isinstance(raw, dict) else []\n            return [x for x in apps if isinstance(x, dict) and x.get("package")] if isinstance(apps, list) else []\n        except Exception:\n            return []\n\n    @staticmethod\n    def _resolve_app_hint(hint: str, apps: list[dict]) -> str:\n        wanted = "".join(ch for ch in str(hint or "").casefold() if ch.isalnum())\n        if not wanted:\n            return ""\n        best_score = 0.0\n        best_package = ""\n        tied = False\n        for app in apps:\n            label = "".join(ch for ch in str(app.get("label") or "").casefold() if ch.isalnum())\n            package = str(app.get("package") or "")\n            if not label or not package:\n                continue\n            if label == wanted:\n                score = 1.0\n            elif wanted in label or label in wanted:\n                score = 0.88\n            else:\n                score = SequenceMatcher(None, wanted, label).ratio()\n            if score > best_score + 0.02:\n                best_score, best_package, tied = score, package, False\n            elif abs(score - best_score) <= 0.02 and package != best_package:\n                tied = True\n        return best_package if best_score >= 0.62 and not tied else ""\n\n    @classmethod\n    def _normalize_semantic_steps(cls, raw_steps, apps: list[dict]) -> list[dict]:\n        allowed = {"open_app", "search", "tap", "type", "scroll", "back", "home", "recents", "read", "select", "send", "unknown"}\n        packages = {str(x.get("package") or "") for x in apps}\n        out: list[dict] = []\n        if not isinstance(raw_steps, list):\n            return out\n        for item in raw_steps[:18]:\n            if not isinstance(item, dict):\n                continue\n            typ = str(item.get("type") or "").strip().lower()\n            if typ not in allowed:\n                typ = "unknown"\n            step = {"type": typ}\n            package = str(item.get("package") or "").strip()\n            app_hint = str(item.get("app") or "").strip()[:120]\n            if package not in packages and app_hint:\n                package = cls._resolve_app_hint(app_hint, apps)\n            if package in packages:\n                step["package"] = package\n            if app_hint:\n                step["app"] = app_hint\n            for key, limit in (("query", 1000), ("text", 4000), ("target", 180)):\n                value = str(item.get(key) or "").strip()\n                if value:\n                    step[key] = value[:limit]\n            if typ == "scroll":\n                direction = str(item.get("direction") or "forward").strip().lower()\n                step["direction"] = "backward" if direction in {"backward", "up"} else "forward"\n            out.append(step)\n        return out\n\n    @staticmethod\n    def _requires_screen(steps: list[dict]) -> bool:\n        if len(steps) != 1:\n            return bool(steps)\n        return str(steps[0].get("type") or "") not in {"open_app", "back", "home", "recents"}\n\n'''
    marker = "    def try_direct(self, text: str) -> DirectResult:\n"
    if semantic_helpers.strip() not in c:
        if c.count(marker) != 1:
            raise SystemExit("RC23 companion helper marker mismatch")
        c = c.replace(marker, semantic_helpers + marker, 1)

    new_classify = '''    def classify(self, text: str) -> Intent:\n        text = text.strip()\n        if not text:\n            return Intent("chat", text, 1.0)\n        apps = self._installed_apps()\n        app_context = [{"label": str(x.get("label") or "")[:80], "package": str(x.get("package") or "")[:180]} for x in apps[:220]]\n        routed_text = router_view(text)\n        prompt = f"""\nPahami maksud pesan pengguna secara semantik. Jangan mencocokkan daftar frasa atau kata kunci.\nTentukan apakah pengguna sedang mengobrol atau meminta tindakan nyata pada perangkat Android, lalu pecah tindakan perangkat menjadi langkah konseptual berurutan.\n\nPesan pengguna (pertahankan seluruh maksud, termasuk typo, singkatan, bahasa kasual/campuran):\n{routed_text}\n\nAplikasi terpasang:\n{json.dumps(app_context, ensure_ascii=False)[:12000]}\n\nOutput JSON tunggal:\n{{\n  "mode":"chat|device",\n  "goal":"maksud lengkap pengguna tanpa membuang sub-tugas",\n  "confidence":0.0,\n  "steps":[\n    {{"type":"open_app|search|tap|type|scroll|back|home|recents|read|select|send|unknown","app":"nama aplikasi bila relevan","package":"package dari daftar bila diketahui","query":"","text":"","target":"","direction":"forward|backward"}}\n  ]\n}}\n\nAturan:\n- Pahami makna, bukan ejaan literal. Typo dan singkatan tidak boleh membuat perintah perangkat berubah menjadi chat bila maksudnya jelas.\n- Untuk mode device, jangan hilangkan langkah. Jika pengguna meminta membuka aplikasi DAN mencari sesuatu, steps harus memuat open_app dan search.\n- Untuk open_app, isi app dengan nama aplikasi yang dimaksud secara semantik. Pilih package hanya dari daftar aplikasi terpasang bila yakin; jika tidak, kosongkan package dan resolver lokal akan mencocokkan app secara fuzzy.\n- search berarti benar-benar membuka UI pencarian, mengisi query, dan submit; bukan sekadar membuka aplikasi.\n- Jika pengguna hanya bertanya atau meminta penjelasan, mode=chat dan steps=[].\n- Jangan menambah tindakan yang tidak diminta.\n""".strip()\n        try:\n            raw = self.llm.chat(\n                [\n                    {"role": "system", "content": "Kamu semantic intent parser Android internal. Output JSON valid saja."},\n                    {"role": "user", "content": prompt},\n                ],\n                max_tokens=360,\n                temperature=0.0,\n                json_mode=True,\n            )\n            obj = _first_json_object(raw) or {}\n            mode = str(obj.get("mode") or "chat").strip().lower()\n            if mode not in {"chat", "device"}:\n                mode = "chat"\n            try:\n                confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.5) or 0.5)))\n            except Exception:\n                confidence = 0.5\n            steps = self._normalize_semantic_steps(obj.get("steps"), apps) if mode == "device" else []\n            goal = str(obj.get("goal") or text).strip() or text\n            if mode == "device":\n                goal = text\n            return Intent(mode, goal, confidence, steps, self._requires_screen(steps))\n        except Exception as exc:\n            self.store.log_event("semantic_intent_error", {"error": str(exc)[:300]})\n            return Intent("chat", text, 0.0)\n\n    def try_direct_intent(self, intent: Intent) -> DirectResult:\n        if intent.mode != "device" or intent.requires_screen or len(intent.steps) != 1:\n            return DirectResult(False)\n        try:\n            return self.direct.try_execute_step(intent.steps[0])\n        except Exception as exc:\n            self.store.log_event("direct_semantic_error", {"error": str(exc)[:240]})\n            return DirectResult(False)\n'''
    c = block(c, "    def classify(self, text: str) -> Intent:\n", "    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:\n", new_classify, "semantic classify")
    old_respond = '''    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:\n        direct = self.try_direct(text)\n        if direct.handled:\n            self.store.add_message("user", text)\n            self.store.add_message("assistant", direct.reply)\n            return direct.reply, direct.kind\n        intent = self.classify(text)\n        if intent.mode == "device":\n            result = self.agent.run(intent.goal, approve, task_authorized=task_authorized)\n            return result, "device"\n        return self.chat.respond(text), "chat"\n'''
    new_respond = '''    def respond(self, text: str, approve, *, task_authorized: bool = False) -> tuple[str, str]:\n        direct = self.try_direct(text)\n        if direct.handled:\n            self.store.add_message("user", text)\n            self.store.add_message("assistant", direct.reply)\n            return direct.reply, direct.kind\n        intent = self.classify(text)\n        semantic_direct = self.try_direct_intent(intent)\n        if semantic_direct.handled:\n            self.store.add_message("user", text)\n            self.store.add_message("assistant", semantic_direct.reply)\n            return semantic_direct.reply, semantic_direct.kind\n        if intent.mode == "device":\n            result = self.agent.run(intent.goal, approve, task_authorized=task_authorized, semantic_steps=intent.steps)\n            return result, "device"\n        return self.chat.respond(text), "chat"\n'''
    c = rep(c, old_respond, new_respond, "companion respond")
    companion.write_text(c, encoding="utf-8")

    # Consume the semantic plan directly. Common open/search/type tasks no
    # longer need another planner call before Bridge can act.
    a = agent.read_text(encoding="utf-8")
    semantic_agent = '''    def _semantic_contract(self, goal: str, steps: list[dict], apps: list[dict]) -> TaskContract | None:\n        if not steps:\n            return None\n        installed = {str(x.get("package") or "") for x in apps if isinstance(x, dict)}\n        target_package = ""\n        criteria: list[str] = []\n        required_scrolls = 0\n        required_write_text = ""\n        external_expected = False\n        for step in steps:\n            if not isinstance(step, dict):\n                continue\n            typ = str(step.get("type") or "")\n            package = str(step.get("package") or "")\n            if typ == "open_app" and package in installed:\n                target_package = package\n                criteria.append("aplikasi tujuan aktif")\n            elif typ == "search":\n                query = str(step.get("query") or "").strip()[:320]\n                if query:\n                    required_write_text = query\n                    criteria.append(f"hasil pencarian untuk {query} sudah tampil setelah query disubmit")\n            elif typ == "type":\n                value = str(step.get("text") or "").strip()[:320]\n                if value:\n                    required_write_text = value\n                    criteria.append("teks yang diminta benar-benar masuk ke field")\n            elif typ == "scroll":\n                required_scrolls += 1\n                criteria.append("scroll yang diminta benar-benar terjadi")\n            elif typ in {"tap", "select", "read"}:\n                criteria.append("sub-tugas UI yang diminta sudah terpenuhi")\n            elif typ == "send":\n                external_expected = True\n                criteria.append("aksi eksternal yang diminta benar-benar berhasil")\n        if not criteria:\n            return None\n        unique: list[str] = []\n        for item in criteria:\n            if item not in unique:\n                unique.append(item)\n        return TaskContract(goal[:300], unique[:5], external_expected, min(required_scrolls, 20), required_write_text, target_package)\n\n    def _compile_semantic_sequence(self, steps: list[dict], apps: list[dict]) -> list[dict]:\n        installed = {str(x.get("package") or "") for x in apps if isinstance(x, dict)}\n        out: list[dict] = []\n        for item in steps[:18]:\n            if not isinstance(item, dict):\n                break\n            typ = str(item.get("type") or "")\n            if typ == "open_app":\n                package = str(item.get("package") or "")\n                if package not in installed:\n                    break\n                out.append({"type": "open_app", "package": package})\n            elif typ == "search":\n                query = str(item.get("query") or "").strip()\n                if not query:\n                    break\n                out.extend([\n                    {"type": "tap_text", "role": "search", "max_scrolls": 0},\n                    {"type": "set_text_best", "text": query[:4000]},\n                    {"type": "ime_best"},\n                ])\n            elif typ == "type":\n                value = str(item.get("text") or "")\n                if not value:\n                    break\n                out.append({"type": "set_text_best", "text": value[:4000]})\n            elif typ == "scroll":\n                out.append({"type": "scroll_best", "direction": "backward" if str(item.get("direction") or "") == "backward" else "forward"})\n            elif typ in {"back", "home", "recents"}:\n                out.append({"type": typ})\n            elif typ == "tap":\n                target = sanitize(str(item.get("target") or "")).strip()[:100]\n                if not target or EXTERNAL_WORDS.search(target) or DESTRUCTIVE_WORDS.search(target):\n                    break\n                out.append({"type": "tap_text", "target": target, "max_scrolls": 2})\n            else:\n                break\n            if len(out) >= 18:\n                return out[:18]\n        return out[:18]\n\n'''
    marker = "    def _contract(self, goal: str, apps: list[dict]) -> TaskContract:\n"
    if semantic_agent.strip() not in a:
        if a.count(marker) != 1:
            raise SystemExit("RC23 agent semantic insertion mismatch")
        a = a.replace(marker, semantic_agent + marker, 1)
    a = rep(a, "    def _contract(self, goal: str, apps: list[dict]) -> TaskContract:\n        fast = compile_fast_contract(goal, apps) if getattr(self.cfg, \"fast_path_enabled\", True) else None\n", "    def _contract(self, goal: str, apps: list[dict], semantic_steps: list[dict] | None = None) -> TaskContract:\n        semantic = self._semantic_contract(goal, semantic_steps or [], apps)\n        if semantic is not None:\n            self.store.log_event(\"agent_contract_semantic\", {\"goal\": str(goal)[:240], \"steps\": len(semantic_steps or [])})\n            return semantic\n        fast = compile_fast_contract(goal, apps) if getattr(self.cfg, \"fast_path_enabled\", True) else None\n", "semantic contract hook")
    a = rep(a, "    def _try_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict], approve, task_authorized: bool, history: list[dict]):\n        steps = self._compile_ui_sequence(goal, contract, apps)\n", "    def _try_ui_sequence(self, goal: str, contract: TaskContract, apps: list[dict], approve, task_authorized: bool, history: list[dict], semantic_steps: list[dict] | None = None):\n        steps = self._compile_semantic_sequence(semantic_steps or [], apps)\n        if not steps:\n            steps = self._compile_ui_sequence(goal, contract, apps)\n", "semantic sequence hook")
    a = rep(a, "    def run(self, goal: str, approve, *, task_authorized: bool = False) -> str:\n        history: list[dict] = []\n        apps = self._apps()\n        contract = self._contract(goal, apps)\n", "    def run(self, goal: str, approve, *, task_authorized: bool = False, semantic_steps: list[dict] | None = None) -> str:\n        history: list[dict] = []\n        apps = self._apps()\n        contract = self._contract(goal, apps, semantic_steps)\n", "agent run semantic signature")
    a = rep(a, "        sequence_result, sequence_screen, sequence_attempted = self._try_ui_sequence(\n            goal, contract, apps, approve, task_authorized, history\n        )\n", "        sequence_result, sequence_screen, sequence_attempted = self._try_ui_sequence(\n            goal, contract, apps, approve, task_authorized, history, semantic_steps\n        )\n", "semantic sequence run")
    agent.write_text(a, encoding="utf-8")

    cs = chat_surface.read_text(encoding="utf-8")
    old = '''                direct = self.session.try_direct(text)\n                if direct.handled:\n                    self.session.store.add_message("user", text)\n                    self.session.store.add_message("assistant", direct.reply)\n                    self.call_from_thread(self._finalize, assistant_id, direct.reply)\n                    return\n                intent = self.session.classify(text)\n                if intent.mode == "device":\n                    allowed = self._request_device_confirmation()\n'''
    new = '''                direct = self.session.try_direct(text)\n                if direct.handled:\n                    self.session.store.add_message("user", text)\n                    self.session.store.add_message("assistant", direct.reply)\n                    self.call_from_thread(self._finalize, assistant_id, direct.reply)\n                    return\n                intent = self.session.classify(text)\n                semantic_direct = self.session.try_direct_intent(intent)\n                if semantic_direct.handled:\n                    self.session.store.add_message("user", text)\n                    self.session.store.add_message("assistant", semantic_direct.reply)\n                    self.call_from_thread(self._finalize, assistant_id, semantic_direct.reply)\n                    return\n                if intent.mode == "device":\n                    allowed = self._request_device_confirmation()\n'''
    cs = rep(cs, old, new, "chat semantic direct")
    cs = rep(cs, "                        task_authorized=True,\n                    )\n", "                        task_authorized=True,\n                        semantic_steps=intent.steps,\n                    )\n", "chat semantic agent")
    chat_surface.write_text(cs, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = rep(v, 'VERSION = "1.0.0-rc22"', 'VERSION = "1.0.0-rc23"', "version")
    version.write_text(v, encoding="utf-8")

    for p in (companion, direct, agent, chat_surface, version):
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    checks = [
        (companion, "semantic intent parser Android internal"),
        (companion, "_resolve_app_hint"),
        (companion, "try_direct_intent"),
        (direct, "exact=True"),
        (direct, "try_execute_step"),
        (agent, "_compile_semantic_sequence"),
        (agent, "semantic_steps: list[dict] | None = None"),
        (chat_surface, "semantic_steps=intent.steps"),
        (version, 'VERSION = "1.0.0-rc23"'),
    ]
    missing = [needle for p, needle in checks if needle not in p.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC23 incomplete: " + ", ".join(missing))
    print("Furina Core RC23 semantic intent + complete-goal execution: OK")


if __name__ == "__main__":
    main()
