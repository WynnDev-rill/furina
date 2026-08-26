#!/usr/bin/env python3
"""Build Core 1.1.17: canonical Termux runtime, hybrid recall and memory reconciliation."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.1.16"' not in text:
    raise SystemExit("expected Core 1.1.16")
version.write_text(text.replace('VERSION = "1.1.16"', 'VERSION = "1.1.17"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r66"' not in text:
    raise SystemExit("expected dependency r66")
text = text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r66"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r67"', 1)
text = text.replace("furina-2026.08.25-termux-1.1.16", "furina-2026.08.26-termux-1.1.17")
text = text.replace('expected_revision = "2026.08.25-r66"', 'expected_revision = "2026.08.26-r67"')
hub.write_text(text, encoding="utf-8")

# Personalization remains the existing 20-item UI. Only compilation changes:
# 2-4 relevant facets are selected for the current conversational situation.
personality = CORE / "personality.py"
append_once(
    personality,
    "FURINA_TERMUX_117_CONTEXTUAL_FACETS",
    r'''
# FURINA_TERMUX_117_CONTEXTUAL_FACETS
def contextual_traits(values, user_text: str, minimum: int = 2, maximum: int = 4) -> list[str]:
    import hashlib, re
    selected = normalize_traits(values)
    if len(selected) <= maximum:
        return selected
    text = " ".join(str(user_text or "").casefold().split())
    if re.search(r"\b(error|bug|kode|script|termux|api|model|provider|build|install|update)\b", text):
        wanted = {"composure": 1.0, "maturity": .8, "caretaking": .35, "energy": -.25}
    elif re.search(r"\b(sedih|takut|cemas|kecewa|kesepian|capek|lelah|marah|sakit hati)\b", text):
        wanted = {"warmth": 1.0, "caretaking": 1.0, "maturity": .7, "openness": .45, "teasing": -.7}
    elif re.search(r"\b(sayang|cinta|rindu|kangen|cemburu|peluk|cium|pasangan)\b", text):
        wanted = {"warmth": 1.0, "intensity": .75, "openness": .65, "shyness": .25}
    elif re.search(r"\b(haha|hehe|wkwk|godain|goda|ledek|bercanda|lucu)\b", text):
        wanted = {"teasing": 1.0, "energy": .75, "warmth": .45, "composure": -.2}
    else:
        wanted = {"warmth": .55, "composure": .35, "teasing": .3, "energy": .2}
    salt = int.from_bytes(hashlib.blake2s(text.encode("utf-8"), digest_size=2).digest(), "little")
    ranked = []
    for index, trait_id in enumerate(selected):
        vector = TRAIT_BY_ID[trait_id].vector
        score = sum(float(vector.get(dim, 0.0)) * weight for dim, weight in wanted.items())
        score += ((salt + index * 17) % 101) / 10000.0
        ranked.append((score, -index, trait_id))
    count = max(minimum, min(maximum, 2 + (1 if len(text.split()) >= 8 else 0) + (1 if len(text.split()) >= 28 else 0)))
    return [item[2] for item in sorted(ranked, reverse=True)[:count]]


def compile_contextual_personality(values, user_text: str) -> str:
    active = contextual_traits(values, user_text)
    rendered = compile_personality(active)
    return rendered.replace(
        f"memiliki {len(active)} facet aktif",
        f"menonjolkan {len(active)} facet yang paling relevan untuk momen ini",
        1,
    )
''',
)

hub_settings = CORE / "hub_settings.py"
text = hub_settings.read_text(encoding="utf-8")
old = '''def personalization_prompt(settings: dict | None = None) -> str:
    state = normalize(settings) if settings is not None else load_hub_settings()
    return (
        "[PERSONAL EXPRESSION — soft behavioral facets]\\n"
        + compile_personality(state.get("personality_traits"))
        + "\\nGunakan sebagai kecenderungan ekspresi, bukan skrip, bukan daftar yang harus ditampilkan, dan bukan fakta tentang user."
    )'''
new = '''def personalization_prompt(settings: dict | None = None, user_text: str = "") -> str:
    from .personality import compile_contextual_personality
    state = normalize(settings) if settings is not None else load_hub_settings()
    return (
        "[PERSONAL EXPRESSION — contextual behavioral facets]\\n"
        + compile_contextual_personality(state.get("personality_traits"), user_text)
        + "\\nFacet lain tetap tersedia untuk momen lain. Gunakan sebagai kecenderungan ekspresi, bukan skrip, bukan daftar yang harus ditampilkan, dan bukan fakta tentang user."
    )'''
if old not in text:
    raise SystemExit("expected schema-v3 personalization prompt")
hub_settings.write_text(text.replace(old, new, 1), encoding="utf-8")

chat = CORE / "chat.py"
text = chat.read_text(encoding="utf-8")
if "personal = personalization_prompt()" not in text:
    raise SystemExit("expected contextual personalization callsite")
text = text.replace("personal = personalization_prompt()", "personal = personalization_prompt(user_text=user_text)", 1)
text = text.replace("idle >= 120.0", "idle >= 20.0 or bool(getattr(self, '_force_memory_flush', False))", 1)
text = text.replace("120.0 - idle", "20.0 - idle", 1)
text = text.replace(
    "HANYA ucapan USER boleh menjadi bukti fakta personal pengguna. Jawaban Furina BUKAN bukti. Jangan mengarang.",
    "HANYA ucapan USER boleh menjadi bukti fakta personal pengguna. Jawaban Furina BUKAN bukti. Jangan mengarang. Jika user mengoreksi atau mengubah preferensi lama, pertahankan penanda perubahan seperti 'sekarang' atau 'tidak lagi' di text/value.",
    1,
)
chat.write_text(text, encoding="utf-8")

append_once(
    CORE / "memory.py",
    "FURINA_TERMUX_117_HYBRID_VERSIONED_MEMORY",
    r'''
# FURINA_TERMUX_117_HYBRID_VERSIONED_MEMORY
_furina_117_previous_init_db = MemoryStore._init_db
def _furina_117_init_db(self, _previous=_furina_117_previous_init_db):
    _previous(self)
    conn = self._conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS message_vectors (
      message_id INTEGER PRIMARY KEY, vector BLOB NOT NULL, dims INTEGER NOT NULL,
      model TEXT NOT NULL DEFAULT 'local', updated_at REAL NOT NULL,
      FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS memory_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL,
      old_id INTEGER, new_id INTEGER, old_value TEXT NOT NULL, new_value TEXT NOT NULL,
      reason TEXT NOT NULL, created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS memory_versions_entity_idx ON memory_versions(entity_type,created_at DESC);
    """)
    conn.commit()


def _furina_117_index_message(self, message_id: int, content: str) -> bool:
    vec = self._embed_text(content)
    if not vec:
        return False
    model = "local"
    try: model = Path(self._embedder.model_path).name if self._embedder else "local"
    except Exception: pass
    self._conn().execute(
        "INSERT OR REPLACE INTO message_vectors(message_id,vector,dims,model,updated_at) VALUES(?,?,?,?,?)",
        (int(message_id), self._pack_vector(vec), len(vec), model[:120], time.time()),
    )
    self._conn().commit()
    return True


def _furina_117_message_importance(text: str) -> float:
    low = str(text or "").casefold()
    score = .20
    if re.search(r"\b(namaku|aku tinggal|aku kerja|aku suka|aku tidak suka|tujuanku|rencanaku|mulai sekarang|jangan pernah|ingat)\b", low): score += .45
    if re.search(r"\b(sedih|takut|cinta|sayang|kecewa|bangga|penting)\b", low): score += .18
    if len(low) >= 100: score += .08
    return min(1.0, score)


def _furina_117_search_conversation_context(self, query: str, limit: int = 4):
    """Hybrid FTS/embedding retrieval; weak evidence returns nothing."""
    conn = self._conn(); clean = " ".join(str(query or "").strip().split())
    limit = max(1, min(int(limit), 6))
    if not clean: return []
    current = self.active_conversation_id(); qterms = self._retrieval_terms(clean)
    candidates = {}
    if qterms:
        try:
            rows = conn.execute(
                "SELECT m.id,m.content,m.created_at,m.conversation_id,c.surface,bm25(user_message_fts) rank "
                "FROM user_message_fts f JOIN messages m ON m.id=f.rowid JOIN conversations c ON c.id=m.conversation_id "
                "WHERE user_message_fts MATCH ? AND m.conversation_id<>? AND m.role='user' "
                "ORDER BY rank,m.created_at DESC LIMIT 40",
                (self._fts_query(" ".join(sorted(qterms))), current),
            ).fetchall()
            for row in rows:
                terms = self._retrieval_terms(str(row["content"] or ""))
                lexical = len(qterms & terms) / max(1, len(qterms))
                candidates[int(row["id"])] = {"row": row, "lexical": lexical, "semantic": 0.0}
        except sqlite3.DatabaseError:
            pass
    query_vec = self._embed_text(clean)
    if query_vec:
        rows = conn.execute(
            "SELECT m.id,m.content,m.created_at,m.conversation_id,c.surface,v.vector,v.dims "
            "FROM message_vectors v JOIN messages m ON m.id=v.message_id JOIN conversations c ON c.id=m.conversation_id "
            "WHERE m.conversation_id<>? AND m.role='user' ORDER BY m.id DESC LIMIT 400",
            (current,),
        ).fetchall()
        for row in rows:
            vec = self._unpack_vector(row["vector"], int(row["dims"] or 0))
            similarity = self._cosine(query_vec, vec) if vec and len(vec) == len(query_vec) else 0.0
            if similarity < .58: continue
            item = candidates.setdefault(int(row["id"]), {"row": row, "lexical": 0.0, "semantic": 0.0})
            item["semantic"] = max(float(item["semantic"]), similarity)
    ranked = []
    for item in candidates.values():
        row = item["row"]; lexical = float(item["lexical"]); semantic = float(item["semantic"])
        if lexical < .20 and semantic < .62: continue
        recency = self._age_score(float(row["created_at"] or 0), half_life_days=90.0)
        importance = _furina_117_message_importance(str(row["content"] or ""))
        score = .43 * semantic + .35 * lexical + .13 * importance + .09 * recency
        if score < .25: continue
        ranked.append((score, row))
    ranked.sort(key=lambda item: (item[0], float(item[1]["created_at"] or 0)), reverse=True)
    out=[]; seen_text=set(); session_counts={}
    for score,row in ranked:
        cid=int(row["conversation_id"]); content=" ".join(str(row["content"] or "").split())[:700]
        key=content.casefold()
        if not content or key in seen_text or session_counts.get(cid,0)>=2: continue
        seen_text.add(key); session_counts[cid]=session_counts.get(cid,0)+1
        out.append({"content":content,"created_at":float(row["created_at"] or 0),"surface":str(row["surface"] or ""),"score":round(score,4)})
        if len(out)>=limit: break
    return list(reversed(out))


def _furina_117_version(self, entity_type, old_id, new_id, old_value, new_value, reason):
    self._conn().execute(
        "INSERT INTO memory_versions(entity_type,old_id,new_id,old_value,new_value,reason,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(entity_type)[:24], old_id, new_id, str(old_value)[:600], str(new_value)[:600], str(reason)[:80], time.time()),
    )
    self._conn().commit()


def _furina_117_conflicts(old: str, new: str) -> bool:
    a=" ".join(str(old).casefold().split()); b=" ".join(str(new).casefold().split())
    change=bool(re.search(r"\b(sekarang|mulai sekarang|tidak lagi|nggak lagi|berubah|koreksi|maksudku|lebih suka)\b", b))
    if not change: return False
    ta=MemoryStore._retrieval_terms(a); tb=MemoryStore._retrieval_terms(b)
    overlap=len(ta & tb)/max(1,min(len(ta),len(tb)))
    polarity=(bool(re.search(r"\b(tidak|nggak|jangan|benci)\b",a)) != bool(re.search(r"\b(tidak|nggak|jangan|benci)\b",b)))
    return overlap >= .30 or (polarity and overlap >= .18)


_furina_117_previous_add_memory = MemoryStore.add_memory
def _furina_117_add_memory(self, text, kind="fact", importance=.5, **kwargs):
    source=str(kwargs.get("source") or "conversation")
    prior=[]
    if source in {"explicit","user_evidence"} and kind in {"identity","profile","preference","goal","fact"}:
        prior=self._conn().execute("SELECT id,text FROM memories WHERE kind=? AND source NOT LIKE 'superseded:%' ORDER BY updated_at DESC LIMIT 40",(kind,)).fetchall()
    _furina_117_previous_add_memory(self,text,kind,importance,**kwargs)
    new_row=self._conn().execute("SELECT id,text FROM memories WHERE text=?",(re.sub(r"\s+"," ",str(text).strip())[:600],)).fetchone()
    if not new_row: return
    for row in prior:
        if int(row["id"])==int(new_row["id"]) or not _furina_117_conflicts(str(row["text"]),str(text)): continue
        self._conn().execute("UPDATE memories SET source=?,updated_at=? WHERE id=?",(f"superseded:{int(new_row['id'])}",time.time(),int(row["id"])))
        _furina_117_version(self,"memory",int(row["id"]),int(new_row["id"]),str(row["text"]),str(text),"user-correction")
    self._conn().commit()


_furina_117_previous_update_relationship = MemoryStore.update_relationship
def _furina_117_update_relationship(self, user_text: str):
    """Update only from relational evidence, never generic technical feedback."""
    s=self.relationship_state(); low=" ".join(str(user_text or "").casefold().split())
    vulnerability=bool(re.search(r"\b(aku merasa|aku takut|aku sedih|aku malu|rahasia|aku percaya kamu|jujur sama kamu)\b",low))
    affection=bool(re.search(r"\b(aku sayang kamu|aku cinta kamu|kangen kamu|rindu kamu|makasih sudah menemani)\b",low))
    boundary=bool(re.search(r"\b(aku tidak nyaman|jangan panggil aku|jangan pernah|batas(?:ku)?|tolong hormati)\b",low))
    disrespect=bool(re.search(r"\b(kamu|kau)\s+(?:bodoh|payah|menyebalkan|brengsek)\b",low))
    repair=bool(re.search(r"\b(sekarang sudah pas|itu yang kumaksud|terima kasih sudah memahami|makasih sudah memahami)\b",low))
    playful=bool(re.search(r"\b(haha|hehe|wkwk|goda|ledek|bercanda)\b",low))
    if vulnerability: s["closeness"]+=.018; s["trust"]+=.014
    if affection: s["closeness"]+=.020; s["trust"]+=.010
    if boundary: s["trust"]+=.004
    if disrespect: s["friction"]+=.045; s["trust"]-=.010
    elif repair: s["friction"]-=.030; s["trust"]+=.008
    else: s["friction"]*=.985
    if playful: s["playfulness"]+=.018
    for key in s: s[key]=round(max(0.0,min(1.0,float(s[key]))),4)
    self.set_state("relationship",s); return s


MemoryStore._init_db = _furina_117_init_db
MemoryStore.search_conversation_context = _furina_117_search_conversation_context
MemoryStore.add_memory = _furina_117_add_memory
MemoryStore.update_relationship = _furina_117_update_relationship
MemoryStore.index_message_vector = _furina_117_index_message
MemoryStore.record_memory_version = _furina_117_version
''',
)

append_once(
    CORE / "chat.py",
    "FURINA_TERMUX_117_ADAPTIVE_CONSOLIDATION",
    r'''
# FURINA_TERMUX_117_ADAPTIVE_CONSOLIDATION
def _furina_117_chat_init(self, cfg, store, llm):
    # The final response path no longer consumes the legacy upstream/psyche
    # adapters. Avoid two idle upstream threads and keep only ordered memory work.
    self.cfg=cfg; self.store=store; self.llm=llm
    self._foreground_active=False; self._background_active=False
    self._last_foreground_at=0.0; self._force_memory_flush=False
    self._background_queue=queue.Queue(maxsize=64)
    self._background_thread=threading.Thread(target=self._background_worker_loop,name="furina-memory-worker",daemon=True)
    self._background_thread.start()
FurinaChat.__init__ = _furina_117_chat_init

_furina_117_original_extract = extract_explicit_memories
def _furina_117_extract(text):
    seen=set()
    for item in _furina_117_original_extract(text):
        key=(item[0].casefold(),item[1])
        if key not in seen: seen.add(key); yield item
    patterns=(
      (r"\b(?:mulai sekarang|seterusnya)\s+([^.!?]{4,180})", "preference", .90),
      (r"\b(?:aku|saya)\s+(?:lebih suka|maunya)\s+([^.!?]{4,180})", "preference", .86),
      (r"\b(?:aku|saya)\s+(?:tidak lagi|nggak lagi)\s+([^.!?]{4,180})", "preference", .88),
      (r"\b(?:jangan pernah|tolong jangan)\s+([^.!?]{4,180})", "preference", .84),
    )
    for pattern,kind,importance in patterns:
        match=re.search(pattern,str(text or ""),re.I)
        if match:
            value=match.group(0).strip(); key=(value.casefold(),kind)
            if key not in seen: seen.add(key); yield (value,kind,importance)
extract_explicit_memories = _furina_117_extract

_furina_117_previous_consolidate = FurinaChat._consolidate
def _furina_117_consolidate(self, user_text, answer):
    _furina_117_previous_consolidate(self, user_text, answer)
    try:
        row=self.store._conn().execute(
            "SELECT id,content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id DESC LIMIT 1",
            (self.store.active_conversation_id(),),
        ).fetchone()
        if row and str(row["content"] or "").strip()==str(user_text or "").strip():
            self.store.index_message_vector(int(row["id"]),str(row["content"] or ""))
    except Exception:
        pass
FurinaChat._consolidate = _furina_117_consolidate


def _furina_117_flush_memory(self, timeout: float = 6.0) -> bool:
    self._force_memory_flush=True; deadline=time.monotonic()+max(.1,min(float(timeout),12.0))
    try:
        while getattr(self._background_queue,"unfinished_tasks",0) and time.monotonic()<deadline:
            time.sleep(.04)
        return not bool(getattr(self._background_queue,"unfinished_tasks",0))
    finally:
        self._force_memory_flush=False
FurinaChat.flush_memory = _furina_117_flush_memory


def _furina_117_relationship_context(self):
    state=self.store.relationship_state()
    closeness="akrab" if state.get("closeness",0)>=.65 else "mulai dekat" if state.get("closeness",0)>=.4 else "masih membangun keakraban"
    friction="ada gesekan yang perlu dihormati" if state.get("friction",0)>=.45 else "tidak ada konflik berarti"
    play="banter kuat" if state.get("playfulness",0)>=.65 else "banter sedang" if state.get("playfulness",0)>=.4 else "banter ringan"
    return f"Relasi: pasangan; {closeness}; {friction}; {play}. Gunakan hanya sebagai kecenderungan, bukan fakta numerik untuk disebutkan."
FurinaChat._relationship_context = _furina_117_relationship_context
''',
)

# Do not create Bridge, Agent, device event threads, or direct-control objects
# for a Termux chat session. Historical modules stay on disk only so old data
# and rollback snapshots remain readable.
append_once(
    CORE / "companion.py",
    "FURINA_TERMUX_117_CHAT_SESSION_ONLY",
    r'''
# FURINA_TERMUX_117_CHAT_SESSION_ONLY
def _furina_117_chat_session_init(self, cfg, store, llm):
    self.cfg=cfg; self.store=store; self.llm=llm; self.chat=FurinaChat(cfg,store,llm)
def _furina_117_no_direct(self, text): return DirectResult(False)
def _furina_117_no_direct_intent(self, intent): return DirectResult(False)
CompanionSession.__init__ = _furina_117_chat_session_init
CompanionSession.try_direct = _furina_117_no_direct
CompanionSession.try_direct_intent = _furina_117_no_direct_intent
CompanionSession.classify = _furina_113_chat_only_intent
''',
)

append_once(
    CORE / "cli.py",
    "FURINA_TERMUX_117_PUBLIC_CLI_BOUNDARY",
    r'''
# FURINA_TERMUX_117_PUBLIC_CLI_BOUNDARY
def cmd_status(_args):
    cfg=load_config(); secrets=ProviderSecrets(); local=LocalLLM(cfg)
    print(json.dumps({"version":VERSION,"surface":"termux","home":str(HOME),"nickname":cfg.user_nickname or None,"routing_mode":cfg.routing_mode,"online_providers":secrets.configured(),"model":cfg.model_path or None,"llama_pid":_read_pid("llama"),"llama_ready":local.health()},indent=2,ensure_ascii=False))

def collect_doctor_checks():
    cfg=load_config(); checks=[("Python",sys.version.split()[0],True)]
    try: checks.append(("llama-server",find_llama_server(),True))
    except SystemExit as exc: checks.append(("llama-server",str(exc),False))
    model_exists=bool(cfg.model_path and Path(cfg.model_path).exists()); configured=ProviderSecrets().configured()
    checks.append(("model",cfg.model_path or "belum diatur",model_exists or cfg.routing_mode=="online"))
    checks.append(("AI routing",f"{cfg.routing_mode} • providers={', '.join(configured) if configured else 'none'}",model_exists if cfg.routing_mode=="local" else bool(configured)))
    checks.append(("memory DB",str(MemoryStore().path),MemoryStore().path.is_file()))
    checks.append(("nickname",cfg.user_nickname or "belum diatur",True)); return checks

def cmd_start(_args):
    cfg=load_config()
    if not cfg.model_path or not Path(cfg.model_path).exists(): raise SystemExit("Model lokal belum dikonfigurasi.")
    llama=find_llama_server(); help_text=_server_help(llama)
    argv=[llama,"-m",cfg.model_path,"-c",str(cfg.context_size),"-t",str(cfg.threads),"--host",cfg.llama_host,"--port",str(cfg.llama_port),"--parallel","1","--jinja"]
    if "--threads-batch" in help_text: argv += ["--threads-batch",str(cfg.threads)]
    if "--cache-reuse" in help_text and cfg.cache_reuse>0: argv += ["--cache-reuse",str(cfg.cache_reuse)]
    if "--keep" in help_text: argv += ["--keep","-1"]
    if "--flash-attn" in help_text: argv += ["--flash-attn","auto"]
    if "--prio" in help_text: argv += ["--prio",str(cfg.server_priority)]
    if not cfg.local_reasoning:
        if "--reasoning " in help_text or "--reasoning [" in help_text: argv += ["--reasoning","off"]
        elif "--reasoning-budget" in help_text: argv += ["--reasoning-budget","0"]
    pid=_spawn("llama",argv); print(f"llama-server PID {pid}")

def build_parser():
    p=argparse.ArgumentParser(prog="furina",description="Furina by Wynn — AI companion lokal/online untuk Termux")
    sub=p.add_subparsers(dest="cmd")
    sp=sub.add_parser("model"); sp.add_argument("path"); sp.set_defaults(func=cmd_model)
    for name,func in (("start",cmd_start),("stop",cmd_stop),("status",cmd_status),("memories",cmd_memories),("doctor",cmd_doctor),("providers",cmd_provider_status),("setup",cmd_setup),("optimize",cmd_optimize),("update",cmd_update),("recover",cmd_recover),("ui",cmd_ui)):
        sub.add_parser(name).set_defaults(func=func)
    sp=sub.add_parser("chat"); sp.add_argument("message",nargs="*"); sp.set_defaults(func=cmd_chat)
    sp=sub.add_parser("provider-test"); sp.add_argument("provider",choices=list(PROVIDER_LABELS)); sp.set_defaults(func=cmd_provider_test)
    return p
''',
)

# Flush queued adaptive memory work when the Textual surface is deliberately
# closed; this does not change the 20-trait layout.
surface = CORE / "chat_surface.py"
text = surface.read_text(encoding="utf-8")
text = text.replace(
    '''if command in {"/back", "/exit", "/quit"}:
                self.exit()''',
    '''if command in {"/back", "/exit", "/quit"}:
                self._set_status("Menyimpan konteks penting…")
                self.session.chat.flush_memory(6.0)
                self.exit()''',
    1,
)
text = text.replace(
    '''def action_back(self) -> None:
            if not self.busy:
                self.exit()''',
    '''def action_back(self) -> None:
            if not self.busy:
                self._set_status("Menyimpan konteks penting…")
                self.session.chat.flush_memory(6.0)
                self.exit()''',
    1,
)
surface.write_text(text, encoding="utf-8")

# Active local-model deletion must not silently strand chat without any engine.
tui = CORE / "tui.py"
text = tui.read_text(encoding="utf-8")
old = '''if action == "Hapus model":
            if not _confirm(f"Hapus {row['name']} ({row['size_label']}) dari penyimpanan?", default=False): continue
            if active_local:
                _private_stop_local(); cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg)
            try:
                freed = delete_model(row["id"])'''
new = '''if action == "Hapus model":
            from .providers import ProviderSecrets
            providers_ready = bool(ProviderSecrets().configured())
            if active_local and not providers_ready:
                warning = f"{row['name']} adalah satu-satunya mesin chat yang siap. Jika dihapus, chat tidak dapat dipakai sampai model lain diunduh atau API provider diatur. Tetap hapus?"
                if not _confirm(warning, default=False): continue
            elif not _confirm(f"Hapus {row['name']} ({row['size_label']}) dari penyimpanan?", default=False): continue
            if active_local:
                _private_stop_local(); cfg.routing_mode = "online"; cfg.model_path = ""; cfg.auto_start = False; save_config(cfg)
            try:
                freed = delete_model(row["id"])'''
if old not in text:
    raise SystemExit("expected 1.1.16 model deletion flow")
tui.write_text(text.replace(old, new, 1), encoding="utf-8")

print("FURINA_TERMUX_117_CORE_OK")
