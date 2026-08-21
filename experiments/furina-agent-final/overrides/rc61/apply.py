#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

TARGET_VERSION = "1.0.0-rc61"
TARGET_REVISION = "2026.08.21-r31"
SUPPORTED = {"1.0.0-rc60", TARGET_VERSION}


def read_version(path: Path) -> str:
    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)', path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def replace_method(text: str, class_name: str, method_name: str, replacement: str) -> str:
    tree = ast.parse(text)
    cls = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name), None)
    if cls is None:
        raise SystemExit(f"RC61 class missing: {class_name}")
    matches = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name]
    if len(matches) != 1:
        raise SystemExit(f"RC61 method mismatch: {class_name}.{method_name} ({len(matches)})")
    node = matches[0]
    lines = text.splitlines(keepends=True)
    start = min([node.lineno] + [item.lineno for item in node.decorator_list]) - 1
    return "".join(lines[:start]) + replacement.rstrip() + "\n" + "".join(lines[node.end_lineno:])


def atomic(path: Path, content: str) -> None:
    temp = path.with_name(path.name + ".rc61.new")
    temp.write_text(content, encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    hub_path = core / "hub.py"
    chat_path = core / "chat.py"
    bridge_path = core / "upstream_bridge.py"
    version_path = core / "version.py"
    for path in (hub_path, chat_path, bridge_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC61 required source missing: {path}")
    current = read_version(version_path)
    if current not in SUPPORTED:
        raise SystemExit(f"RC61 requires RC60 foundation, found {current or 'unknown'}")

    hub = hub_path.read_text(encoding="utf-8")
    chat = chat_path.read_text(encoding="utf-8")
    bridge = bridge_path.read_text(encoding="utf-8")

    if "import queue\n" not in hub:
        hub = hub.replace("import os\n", "import os\nimport queue\n", 1)
    init_marker = "        self.progress_lock = threading.RLock()\n"
    title_init = (
        init_marker
        + "        self._title_guard = threading.Lock()\n"
        + "        self._title_pending: set[int] = set()\n"
    )
    if "self._title_pending" not in hub:
        if init_marker not in hub:
            raise SystemExit("RC61 title guard boundary missing")
        hub = hub.replace(init_marker, title_init, 1)

    auto_title = r'''    def _queue_auto_title(self, conversation_id: int, user_text: str, assistant_text: str) -> None:
        conversation_id = int(conversation_id)
        user_text = " ".join(str(user_text or "").split())[:1200]
        assistant_text = " ".join(str(assistant_text or "").split())[:1200]
        fallback = self._fallback_title(user_text)
        try:
            self._ensure_conversation_schema()
            conn = self.store._conn()
            row = conn.execute(
                "SELECT title_locked,(SELECT COUNT(*) FROM messages WHERE conversation_id=?) "
                "FROM conversations WHERE id=?", (conversation_id, conversation_id),
            ).fetchone()
            # A title is metadata for the first exchange, not another model job
            # after every message. Manual titles are never touched.
            if not row or int(row[0] or 0) or int(row[1] or 0) > 2:
                return
            with self._title_guard:
                if conversation_id in self._title_pending:
                    return
                self._title_pending.add(conversation_id)
            if fallback != "Percakapan baru":
                conn.execute(
                    "UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0",
                    (fallback[:72], conversation_id),
                )
                conn.commit()
        except Exception:
            with self._title_guard:
                self._title_pending.discard(conversation_id)
            return

        def worker() -> None:
            try:
                # Conversation work has priority. If it is busy, the deterministic
                # title remains useful and we avoid delaying the next answer.
                time.sleep(0.8)
                if not user_text or not self.lock.acquire(blocking=False):
                    return
                try:
                    raw = self.session.llm.chat([
                        {"role": "system", "content": "Buat judul percakapan sangat singkat dalam bahasa pengguna. Gunakan 3-7 kata, tanpa tanda kutip, tanpa titik akhir, jangan memakai kata 'Percakapan baru'. Tangkap topik atau tujuan utama. Jawab judul saja."},
                        {"role": "user", "content": f"User: {user_text}\nAssistant: {assistant_text}\nJudul:"},
                    ], max_tokens=48, temperature=0.2, role="conversation_title")
                finally:
                    self.lock.release()
                candidate = " ".join(str(raw or "").replace("\n", " ").split()).strip(" \"'`.-:;!?")
                candidate = re.sub(r"^(judul|title)\s*:\s*", "", candidate, flags=re.I)
                if candidate and len(candidate) <= 72 and candidate.casefold() != "percakapan baru":
                    conn = self.store._conn()
                    conn.execute(
                        "UPDATE conversations SET title=? WHERE id=? AND COALESCE(title_locked,0)=0",
                        (candidate, conversation_id),
                    )
                    conn.commit()
            except Exception:
                pass
            finally:
                with self._title_guard:
                    self._title_pending.discard(conversation_id)

        threading.Thread(target=worker, name=f"furinahub-title-{conversation_id}", daemon=True).start()'''
    hub = replace_method(hub, "Runtime", "_queue_auto_title", auto_title)

    download_model = r'''    def _download_model(self, url: str, name: str) -> None:
        target = MODELS_DIR / name
        part = MODELS_DIR / (name + ".part")
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            offset = part.stat().st_size if part.is_file() else 0
            headers = {"User-Agent": "FurinaHub/1.0"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req, timeout=45)
            code = int(getattr(response, "status", response.getcode()) or 200)
            if offset and code != 206:
                response.close()
                offset = 0
                req = urllib.request.Request(url, headers={"User-Agent": "FurinaHub/1.0"})
                response = urllib.request.urlopen(req, timeout=45)
            with response, part.open("ab" if offset else "wb") as out:
                remaining = max(0, int(response.headers.get("Content-Length") or 0))
                total = offset + remaining if remaining else 0
                received = offset
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    percent = min(99, int(received * 100 / total)) if total else 0
                    with self.update_lock:
                        self.model_status = {"state": "running", "message": f"Mengunduh {name}", "percent": percent, "received": received, "total": total, "name": name, "resumed": bool(offset)}
            if received < 1024:
                raise RuntimeError("file unduhan kosong atau tidak valid")
            with part.open("rb") as check:
                if check.read(4) != b"GGUF":
                    raise RuntimeError("file unduhan bukan GGUF yang valid")
            os.replace(part, target)
            os.chmod(target, 0o600)
            with self.update_lock:
                self.model_status = {"state": "done", "message": f"{name} siap digunakan.", "percent": 100, "name": name}
        except Exception as exc:
            # Keep the verified prefix so a transient disconnect can resume.
            kept = part.stat().st_size if part.is_file() else 0
            with self.update_lock:
                self.model_status = {"state": "error", "message": f"Unduhan terhenti: {str(exc)[:210]}. Tekan unduh untuk melanjutkan.", "percent": 0, "received": kept, "name": name, "resumable": bool(kept)}'''
    hub = replace_method(hub, "Runtime", "_download_model", download_model)

    run_update = r'''    def _run_core_update(self) -> None:
        log_path = HOME / "logs" / "furinahub-inapp-update.log"
        proc = None
        try:
            command = shutil.which("furina")
            if not command:
                raise RuntimeError("launcher furina tidak ditemukan")
            self._set_update_status(state="running", result="", stage="checking", message="Memeriksa pembaruan Core & dependency…", percent=1, source="furinahub", target_version=VERSION, target_revision=EXPECTED_DEPENDENCY_REVISION, restart_required=False)
            with log_path.open("w", encoding="utf-8") as log:
                update_env = dict(os.environ)
                update_env["FURINAHUB_MACHINE_PROGRESS"] = "1"
                update_env["FURINA_UPDATE_SOURCE"] = "furinahub"
                proc = subprocess.Popen([command, "update"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=update_env)
                assert proc.stdout is not None
                events: queue.Queue[tuple[str, str]] = queue.Queue()
                def reader() -> None:
                    try:
                        for line in proc.stdout:
                            events.put(("line", line))
                    finally:
                        events.put(("eof", ""))
                threading.Thread(target=reader, name="furinahub-update-reader", daemon=True).start()
                started = time.monotonic()
                deadline = started + 1500.0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("updater melewati batas waktu 25 menit")
                    try:
                        kind, line = events.get(timeout=min(1.0, remaining))
                    except queue.Empty:
                        if proc.poll() is not None:
                            break
                        continue
                    if kind == "eof":
                        break
                    log.write(line); log.flush()
                    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()
                    match = re.match(r"PROGRESS\s+(\d{1,3})\s+(.+)", clean)
                    if match:
                        self._set_update_status(state="running", percent=max(1, min(99, int(match.group(1)))), message=match.group(2)[:180], elapsed_seconds=int(time.monotonic() - started))
                proc.wait(timeout=5)
            if proc.returncode != 0:
                detail = self._update_failure_detail(log_path)
                raise RuntimeError(detail or f"updater berhenti (kode {proc.returncode})")
            current = self.get_update_status()
            if current.get("state") != "done":
                disk_version, revision = self._disk_update_versions()
                self._set_update_status(state="done", result="updated" if disk_version != VERSION else "no_update", stage="done", message=f"Pemeriksaan selesai. Core {disk_version or VERSION} · runtime {revision.rsplit('-', 1)[-1] if revision else '?'} aktif.", percent=100, source="furinahub", target_version=disk_version or VERSION, target_revision=revision or EXPECTED_DEPENDENCY_REVISION, restart_required=bool(disk_version and disk_version != VERSION))
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            current = self.get_update_status()
            self._set_update_status(state="error", result="error", stage=str(current.get("stage") or "updater"), message=f"Pembaruan gagal pada tahap {current.get('stage') or 'updater'}: {str(exc)[:260]}", percent=int(current.get("percent") or 0), source="furinahub", restart_required=False)'''
    hub = replace_method(hub, "Runtime", "_run_core_update", run_update)
    hub = re.sub(r'EXPECTED_DEPENDENCY_REVISION\s*=\s*["\'][^"\']+["\']', f'EXPECTED_DEPENDENCY_REVISION = "{TARGET_REVISION}"', hub, count=1)

    chat_worker = r'''    def _background_worker_loop(self) -> None:
        while True:
            first = self._background_queue.get()
            batch = [first]
            time.sleep(1.5)
            while len(batch) < 8:
                try:
                    batch.append(self._background_queue.get_nowait())
                except queue.Empty:
                    break
            try:
                transcript = "\n\n".join(
                    f"Turn {i + 1}\nUser: {item[0]}\nFurina: {item[1]}"
                    for i, item in enumerate(batch)
                )
                self._background(
                    transcript,
                    "Integrasikan seluruh transkrip berurutan di atas sebagai satu batch tanpa membuang turn.",
                    max(int(item[2]) for item in batch),
                )
            except Exception as exc:
                self.store.log_event("background_worker_error", {"error": str(exc)[:300]})
            finally:
                for _ in batch:
                    self._background_queue.task_done()'''
    chat = replace_method(chat, "FurinaChat", "_background_worker_loop", chat_worker)
    stale_schedule = "            self._schedule_background(episode_id, generation, turn)"
    correct_schedule = "            self._schedule_background(user_text, answer, turn)"
    if stale_schedule in chat:
        chat = chat.replace(stale_schedule, correct_schedule, 1)
    elif correct_schedule not in chat:
        raise SystemExit("RC61 background schedule call boundary missing")

    if "episodes = self.store.search_episodes(user_text, 3)" not in bridge:
        bridge = bridge.replace(
            "            memories = [self._to_lumi_memory(m) for m in relevant]\n            seen = {m[\"id\"] for m in memories}\n            for ep in self.store.search_episodes(user_text, 3):",
            "            episodes = self.store.search_episodes(user_text, 3)\n            if not relevant and not priority and not episodes:\n                return \"\"\n            memories = [self._to_lumi_memory(m) for m in relevant]\n            seen = {m[\"id\"] for m in memories}\n            for ep in episodes:",
            1,
        )
    zerochat = r'''    def _run_zerochat(self, user_text: str, answer: str, turns: list[dict] | None = None) -> None:
        source = self._source_root("zerochat")
        worker = self.runtime / "zerochat_worker.py"
        if not source or not worker.is_file():
            return
        req = {
            "op": "update", "upstream": str(source),
            "data_root": str(self.data / "zerochat"), "role_id": "furina",
            "user_text": user_text, "answer": answer,
            "turns": turns or [], "allow_summary": True,
        }
        try:
            event = self._rpc_worker([sys.executable, str(worker)], req, "upstream-zerochat.log", timeout=75)
            if event:
                self.store.set_state("upstream_zerochat_context", event.get("context") or "")
                self.store.set_state("upstream_zerochat_stats", {
                    "short_term_count": event.get("short_term_count", 0),
                    "message_count_since_summary": event.get("message_count_since_summary", 0),
                })
                self.store.set_state("upstream_zerochat_active", True)
        except Exception as exc:
            self._log("upstream_zerochat_error", exc)'''
    bridge = replace_method(bridge, "UpstreamCompanionBridge", "_run_zerochat", zerochat)

    bridge_worker = r'''    def _turn_worker_loop(self) -> None:
        while True:
            first = self._turn_queue.get()
            batch = [first]
            time.sleep(1.0)
            while len(batch) < 8:
                try:
                    batch.append(self._turn_queue.get_nowait())
                except queue.Empty:
                    break
            try:
                # Utsuwa is deterministic and keeps per-turn relationship fidelity.
                for user_text, _ in batch:
                    self._run_utsuwa(user_text)
                # ZeroChat receives every pair in original order but summarizes
                # only once after the batch is appended.
                turns = [{"user_text": item[0], "answer": item[1]} for item in batch]
                self._run_zerochat("", "", turns=turns)
            except Exception as exc:
                self._log("upstream_turn_worker_error", exc)
            finally:
                for _ in batch:
                    self._turn_queue.task_done()'''
    bridge = replace_method(bridge, "UpstreamCompanionBridge", "_turn_worker_loop", bridge_worker)

    zero_worker_path = core / "upstream_runtime" / "zerochat_worker.py"
    zero_worker = zero_worker_path.read_text(encoding="utf-8")
    old_zero = '''        user_text = str(req.get("user_text") or "").strip()
        answer = str(req.get("answer") or "").strip()
        if user_text:
            mod.append_short_term(role_id, "user", user_text)
        if answer:
            mod.append_short_term(role_id, "assistant", answer)
        if bool(req.get("allow_summary", True)) and mod.should_summarize(role_id):'''
    new_zero = '''        turns = req.get("turns") if isinstance(req.get("turns"), list) else []
        if turns:
            for turn in turns[:8]:
                if not isinstance(turn, dict):
                    continue
                user_text = str(turn.get("user_text") or "").strip()
                answer = str(turn.get("answer") or "").strip()
                if user_text:
                    mod.append_short_term(role_id, "user", user_text)
                if answer:
                    mod.append_short_term(role_id, "assistant", answer)
        else:
            user_text = str(req.get("user_text") or "").strip()
            answer = str(req.get("answer") or "").strip()
            if user_text:
                mod.append_short_term(role_id, "user", user_text)
            if answer:
                mod.append_short_term(role_id, "assistant", answer)
        if bool(req.get("allow_summary", True)) and mod.should_summarize(role_id):'''
    if old_zero in zero_worker:
        zero_worker = zero_worker.replace(old_zero, new_zero, 1)
    elif new_zero not in zero_worker:
        raise SystemExit("RC61 ZeroChat ordered batch boundary missing")

    version = re.sub(r'VERSION\s*=\s*(["\'])([^"\']+)\1', f'VERSION = "{TARGET_VERSION}"', version_path.read_text(encoding="utf-8"), count=1)
    for label, content in ((hub_path, hub), (chat_path, chat), (bridge_path, bridge), (zero_worker_path, zero_worker), (version_path, version)):
        compile(content, str(label), "exec")
    required = (
        "updater melewati batas waktu 25 menit", "self._title_pending", "COUNT(*) FROM messages",
        'headers["Range"]', 'part.open("ab" if offset else "wb")', "get_nowait()",
        "if not relevant and not priority and not episodes", "turns=turns",
        "self._schedule_background(user_text, answer, turn)", TARGET_REVISION,
    )
    combined = hub + chat + bridge
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit("RC61 integration incomplete: " + ", ".join(missing))
    atomic(hub_path, hub)
    atomic(chat_path, chat)
    atomic(bridge_path, bridge)
    atomic(zero_worker_path, zero_worker)
    atomic(version_path, version)
    print("FURINA_RC61_EFFICIENT_QUALITY_PIPELINE_OK")


if __name__ == "__main__":
    main()
