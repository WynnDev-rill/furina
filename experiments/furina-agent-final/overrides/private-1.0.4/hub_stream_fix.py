#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
HUB = CORE / "hub.py"
ASSET = ROOT / "bridge/app/src/main/assets/furinahub/index.html"


def class_node(text: str, name: str) -> ast.ClassDef:
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    if node is None:
        raise SystemExit(f"class missing: {name}")
    return node


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    cls = class_node(text, class_name)
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def insert_before(path: Path, class_name: str, before: str, source: str, guard: str) -> None:
    text = path.read_text(encoding="utf-8")
    if guard in text:
        return
    cls = class_node(text, class_name)
    node = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == before), None)
    if node is None:
        raise SystemExit(f"{class_name}.{before} missing")
    lines = text.splitlines(keepends=True)
    pos = sum(len(x) for x in lines[: node.lineno - 1])
    path.write_text(text[:pos] + source.rstrip() + "\n\n" + text[pos:], encoding="utf-8")


text = HUB.read_text(encoding="utf-8")
text = re.sub(r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r44"', text, count=1)
text = text.replace("furina-2026.08.23-private-1.0.1", "furina-2026.08.24-private-1.0.4")
text = text.replace("furina-2026.08.21-rc63-rc51", "furina-2026.08.24-private-1.0.4")
text = text.replace('"bridge_target": "1.0.3"', '"bridge_target": "1.0.4"')
HUB.write_text(text, encoding="utf-8")

replace_method(HUB, "Runtime", "get_chat_progress", r'''    def get_chat_progress(self, request_id: str) -> dict:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80]
        with self.progress_lock:
            return dict(self.chat_progress.get(rid) or {
                "id": rid, "phase": "waiting", "label": "Menyiapkan…", "events": [],
                "done": False, "error": "", "partial": "", "result": None,
            })''')

# Existing synchronous chat remains compatible for old clients. Add callback
# plumbing rather than a second conversation path.
text = HUB.read_text(encoding="utf-8")
old_sig = '    def chat(self, text: str, image: dict | None = None, plugins: list | None = None, request_id: str = "") -> dict:\n'
new_sig = '    def chat(self, text: str, image: dict | None = None, plugins: list | None = None, request_id: str = "", on_token=None) -> dict:\n'
if text.count(old_sig) != 1:
    raise SystemExit(f"Runtime.chat signature mismatch: {text.count(old_sig)}")
text = text.replace(old_sig, new_sig, 1)
if text.count("answer = self.session.chat.respond(companion_input)") != 1:
    raise SystemExit("image respond marker mismatch")
text = text.replace("answer = self.session.chat.respond(companion_input)", "answer = self.session.chat.respond(companion_input, on_token=on_token)", 1)
if text.count("answer = self.session.chat.respond(text)") != 1:
    raise SystemExit("text respond marker mismatch")
text = text.replace("answer = self.session.chat.respond(text)", "answer = self.session.chat.respond(text, on_token=on_token)", 1)

image_return = '                return {"mode": "chat", "answer": answer, "request_id": request_id}\n\n            intent = self.session.classify(text)\n'
image_new = '''                assistant_row = conn.execute(\n                    "SELECT id FROM messages WHERE conversation_id=? AND id>? AND role='assistant' ORDER BY id DESC LIMIT 1",\n                    (active, int(before)),\n                ).fetchone()\n                return {\n                    "mode": "chat", "answer": answer, "request_id": request_id,\n                    "user_message_id": int(user_row[0]) if user_row else 0,\n                    "assistant_message_id": int(assistant_row[0]) if assistant_row else 0,\n                }\n\n            intent = self.session.classify(text)\n'''
if text.count(image_return) != 1:
    raise SystemExit("image return marker mismatch")
text = text.replace(image_return, image_new, 1)

text_block = '''            if intent.mode == "chat":\n                active = self.store.active_conversation_id()\n                self._set_progress(request_id, "compose", "Menyusun jawaban")\n                answer = self.session.chat.respond(text, on_token=on_token)\n                self._set_progress(request_id, "finalize", "Memeriksa jawaban")\n                self._queue_auto_title(active, text, answer)\n                self._set_progress(request_id, "done", "Selesai", done=True)\n                return {"mode": "chat", "answer": answer, "request_id": request_id}\n'''
text_new = '''            if intent.mode == "chat":\n                active = self.store.active_conversation_id()\n                conn = self.store._conn()\n                before = int(conn.execute(\n                    "SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?", (active,)\n                ).fetchone()[0])\n                self._set_progress(request_id, "compose", "Menyusun jawaban")\n                answer = self.session.chat.respond(text, on_token=on_token)\n                rows = conn.execute(\n                    "SELECT id,role FROM messages WHERE conversation_id=? AND id>? ORDER BY id", (active, before)\n                ).fetchall()\n                user_id = next((int(row["id"]) for row in rows if row["role"] == "user"), 0)\n                assistant_id = next((int(row["id"]) for row in reversed(rows) if row["role"] == "assistant"), 0)\n                self._set_progress(request_id, "finalize", "Memeriksa jawaban")\n                self._queue_auto_title(active, text, answer)\n                self._set_progress(request_id, "done", "Selesai", done=True)\n                return {\n                    "mode": "chat", "answer": answer, "request_id": request_id,\n                    "user_message_id": user_id, "assistant_message_id": assistant_id,\n                }\n'''
if text.count(text_block) != 1:
    raise SystemExit("text chat block mismatch")
text = text.replace(text_block, text_new, 1)
HUB.write_text(text, encoding="utf-8")

insert_before(HUB, "Runtime", "public_job", r'''    def start_chat(self, text: str, image: dict | None = None, plugins: list | None = None, request_id: str = "") -> dict:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(request_id or ""))[:80] or ("chat-" + secrets.token_hex(8))
        now = time.time()
        with self.progress_lock:
            existing = self.chat_progress.get(rid)
            if existing and not existing.get("done"):
                return {"accepted": True, "request_id": rid}
            self.chat_progress[rid] = {
                "id": rid, "phase": "queued", "label": "Menyiapkan…", "events": [],
                "done": False, "error": "", "partial": "", "result": None,
                "created_at": now, "updated_at": now,
            }

        def worker() -> None:
            pieces: list[str] = []

            def emit(piece: str) -> None:
                if not piece:
                    return
                pieces.append(str(piece))
                partial = "".join(pieces)
                with self.progress_lock:
                    state = dict(self.chat_progress.get(rid) or {})
                    events = list(state.get("events") or [])
                    if not events or events[-1].get("phase") != "stream":
                        events.append({"phase": "stream", "label": "Menjawab…", "at": time.time()})
                    state.update({
                        "phase": "stream", "label": "Menjawab…", "partial": partial,
                        "events": events[-8:], "updated_at": time.time(),
                    })
                    self.chat_progress[rid] = state

            try:
                result = self.chat(text, image, plugins, rid, on_token=emit)
                with self.progress_lock:
                    state = dict(self.chat_progress.get(rid) or {})
                    state.update({
                        "done": True, "phase": "done", "label": "Selesai",
                        "partial": str(result.get("answer") or state.get("partial") or ""),
                        "result": result, "updated_at": time.time(),
                    })
                    self.chat_progress[rid] = state
            except Exception as exc:
                with self.progress_lock:
                    state = dict(self.chat_progress.get(rid) or {})
                    state.update({
                        "done": True, "phase": "error", "label": "Gagal",
                        "error": str(exc)[:500], "updated_at": time.time(),
                    })
                    self.chat_progress[rid] = state

        threading.Thread(target=worker, name=f"furinahub-chat-{rid[-12:]}", daemon=True).start()
        return {"accepted": True, "request_id": rid}''', "def start_chat")

text = HUB.read_text(encoding="utf-8")
route = '            if path == "/api/chat":\n                self._json(RUNTIME.chat(body.get("message", ""), body.get("image"), body.get("plugins"), body.get("request_id", ""))); return\n'
if text.count(route) != 1:
    raise SystemExit("POST /api/chat route mismatch")
text = text.replace(
    route,
    '            if path == "/api/chat/start":\n                self._json(RUNTIME.start_chat(body.get("message", ""), body.get("image"), body.get("plugins"), body.get("request_id", ""))); return\n' + route,
    1,
)
HUB.write_text(text, encoding="utf-8")

html = ASSET.read_text(encoding="utf-8")
start = html.index("async function sendMessage(forcedText)")
end = html.index("\nfunction thinkingArchiveKey()", start)
new_send = r'''async function sendMessage(forcedText){
 const input=document.getElementById('chatInput'),plain=String(forcedText??input.value).trim(),attachment=selectedAttachment;
 if((!plain&&!attachment)||!connection.connected)return;
 let text=plain,requestId='chat-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),body={message:plain,request_id:requestId};
 if(attachment?.kind==='text')text=`${plain}\n\n[Lampiran teks: ${attachment.name}]\n${attachment.content}`;
 if(attachment?.kind==='image')body.image={name:attachment.name,mime:attachment.mime,base64:attachment.base64};body.message=text;
 clearAttachment();closeSheets();input.value='';autoGrow(input);
 const pendingUser=addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:'Gambar'),null,attachment),thinking=addThinking(requestId);
 let assistant=null,lastPartial='',finished=false;document.getElementById('sendBtn').disabled=true;
 try{
  await core('POST','/api/chat/start',body);
  for(let i=0;i<3600;i++){
   const state=await core('GET','/api/chat/progress/'+encodeURIComponent(requestId));paintThinking(thinking,state);
   const partial=String(state.partial||'');
   if(partial&&partial!==lastPartial){
    if(!assistant){assistant=addMsg('assistant','');assistant.classList.add('streaming');thinking.classList.add('streamStarted')}
    assistant.dataset.text=partial;const bubble=assistant.querySelector('.bubble');if(bubble)bubble.textContent=partial;lastPartial=partial;
    const messages=document.getElementById('messages');messages.scrollTop=messages.scrollHeight;
   }
   if(state.done){
    finished=true;if(state.error)throw new Error(state.error);const result=state.result||{};
    if(result.mode==='plugin_confirmation'){thinking.remove();assistant?.remove();renderPluginConfirmation(result)}
    else if(result.mode==='device'&&result.job){thinking.remove();assistant?.remove();renderJob(result.job)}
    else{
     const finalText=String(result.answer||partial||'');
     if(!assistant)assistant=addMsg('assistant',finalText);else{assistant.dataset.text=finalText;const bubble=assistant.querySelector('.bubble');if(bubble)bubble.textContent=finalText;assistant.classList.remove('streaming')}
     if(Number(result.user_message_id)>0)pendingUser.dataset.id=String(result.user_message_id);
     if(Number(result.assistant_message_id)>0){assistant.dataset.id=String(result.assistant_message_id);archiveThinking(thinking,Number(result.assistant_message_id));placeThinkingBeforeAssistant(thinking,Number(result.assistant_message_id))}else thinking.remove();
    }
    break;
   }
   await new Promise(r=>setTimeout(r,90));
  }
  if(!finished)throw new Error('respons Core melewati batas waktu');
  setTimeout(refreshConversationTitles,500);setTimeout(refreshConversationTitles,2200);
 }catch(e){thinking.remove();assistant?.remove();pendingUser.remove();if(forcedText===undefined){input.value=plain;autoGrow(input);if(attachment){selectedAttachment=attachment;showAttachment()}}addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}
 finally{document.getElementById('sendBtn').disabled=!connection.connected}
}'''
html = html[:start] + new_send + html[end:]
if "FURINAHUB_STREAM_V3_NO_RERENDER" not in html:
    html = html.replace("function autoGrow(el)", "/* FURINAHUB_STREAM_V3_NO_RERENDER */\nfunction autoGrow(el)", 1)
ASSET.write_text(html, encoding="utf-8")

# The loopback browser surface and native APK surface must use the same UI.
(CORE / "hub_web.py").write_text("HTML = " + repr(html) + "\n", encoding="utf-8")

for path in (HUB, CORE / "hub_web.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_4_HUB_STREAM_FIX_OK")
