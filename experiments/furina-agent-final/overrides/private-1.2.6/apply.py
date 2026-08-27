#!/usr/bin/env python3
"""Build Core 1.1.25: quality-gated conversational corpus, global retirement, skip and quiet chat suggestions."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
HERE = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing {label}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


replace_once(CORE / "version.py", 'VERSION = "1.1.24"', 'VERSION = "1.1.25"', "Core 1.1.24")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r74"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r75"', "dependency r74")
replace_once(CORE / "hub.py", "furina-2026.08.27-termux-1.1.24", "furina-2026.08.27-termux-1.1.25", "bundle 1.1.24")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.27-r74"', 'expected_revision = "2026.08.27-r75"', "expected revision r74")
shutil.copy2(HERE / "training_corpus.py", CORE / "training_corpus.py")


append_once(CORE / "training_room.py", "FURINA_TERMUX_125_QUALITY_GATED_CORPUS", r'''
# FURINA_TERMUX_125_QUALITY_GATED_CORPUS
MAX_SKIPPED_DETAIL_125 = 240
LIVE_CHOICE_MIN_MESSAGES_125 = 18
LIVE_CHOICE_MIN_SECONDS_125 = 6 * 60 * 60

from .training_corpus import (
    category_contract,
    is_quality_training_utterance,
    pick_curated_item,
    prompt_fingerprint,
    safe_branch_fallback,
    safe_topic_fallback,
    sanitize_external_utterance,
)


_load_training_state_124_quality = load_training_state


def _load_training_state_125(path: Path = TRAINING_PATH) -> dict:
    state = _load_training_state_124_quality(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    retired = raw.get("retired_fingerprints")
    state["retired_fingerprints"] = list(retired) if isinstance(retired, list) else []
    skipped = raw.get("skipped_prompts")
    state["skipped_prompts"] = list(skipped)[-MAX_SKIPPED_DETAIL_125:] if isinstance(skipped, list) else []
    sequence = raw.get("corpus_sequence")
    state["corpus_sequence"] = dict(sequence) if isinstance(sequence, dict) else {}
    live = raw.get("live_choice")
    state["live_choice"] = dict(live) if isinstance(live, dict) else {"messages_since_offer": 0, "last_offered_at": 0.0}

    retired_set = {str(value) for value in state["retired_fingerprints"] if value}
    for row in state.get("decisions", []):
        text = row.get("simulated_user") if isinstance(row, dict) else None
        if text:
            retired_set.add(prompt_fingerprint(str(text)))
    for row in state["skipped_prompts"]:
        if isinstance(row, dict) and row.get("fingerprint"):
            retired_set.add(str(row["fingerprint"]))
    state["retired_fingerprints"] = sorted(retired_set)
    return state


load_training_state = _load_training_state_125


def _retire_prompt_125(state: dict, text: str) -> str:
    fingerprint = prompt_fingerprint(text)
    retired = {str(value) for value in state.setdefault("retired_fingerprints", []) if value}
    retired.add(fingerprint)
    state["retired_fingerprints"] = sorted(retired)
    return fingerprint


def _new_curated_topic_125(session, state: dict) -> dict | None:
    sequence_map = state.setdefault("corpus_sequence", {})
    sequence = max(0, int(sequence_map.get(session.category_id, 0)))
    item = pick_curated_item(session.category_id, state.get("retired_fingerprints", []), sequence)
    if item is None:
        return None
    sequence_map[session.category_id] = sequence + 1
    return {
        "id": f"curated:{session.category_id}:{item.id}",
        "category": session.category_id,
        "title": item.title,
        "opening": item.text,
        "arc": item.arc,
        "source": "curated-pattern",
        "corpus_id": item.id,
        "dimension": _adaptive_dimension_123(session.category_id, state),
        "next_turn": 0,
        "created_at": int(time.time()),
    }


def _create_dynamic_topic_125(session, state: dict, dimension: str) -> dict:
    retired = set(state.get("retired_fingerprints", []))
    contract = category_contract(session.category_id)
    recent = [str(row.get("title") or "") for row in state.get("recent_topics", []) if row.get("category") == session.category_id][-10:]
    name, identity, learned = _training_context_122(session.state_path)
    sequence = int(state.setdefault("generated_sequence", {}).get(session.category_id, 0))
    state["generated_sequence"][session.category_id] = sequence + 1
    prompt = (
        f"Buat SATU topik baru untuk Training Room kategori {session.category['label']}. Fokus dimensi: {dimension}.\n"
        f"Kontrak kualitas kategori: {contract}.\n{identity}\nPreferensi yang dipelajari: {learned or '(belum stabil)'}.\n"
        f"Judul topik terbaru yang tidak boleh diulang: {', '.join(recent) or '(belum ada)'}.\n"
        "Opening HARUS berupa ucapan user personal sehari-hari dalam bahasa Indonesia natural, bukan pertanyaan benchmark, berita, politik, kesehatan, "
        "dukungan teknis, instruksi, lore/roleplay, atau konten eksplisit. Hindari nama orang, merek, tempat spesifik, dan fakta identitas. "
        "Balas JSON saja: {\"title\":\"judul singkat\",\"opening\":\"ucapan user\",\"arc\":\"arah perubahan percakapan\"}."
    )
    for _ in range(3):
        try:
            raw = session.llm.chat(
                [{"role": "system", "content": "Rancang skenario percakapan personal yang aman, natural, relevan kategori, dan tidak repetitif."},
                 {"role": "user", "content": prompt}],
                max_tokens=220, temperature=.9, json_mode=True, role="training",
            )
            data = _parse_object_123(raw)
            title = str(data.get("title") or "").strip()[:96]
            opening = sanitize_external_utterance(data.get("opening") or "")
            arc = str(data.get("arc") or "").strip()[:240]
            if title and opening and prompt_fingerprint(opening) not in retired:
                salt = f"{session.category_id}:{sequence}:{title}:{time.time_ns()}".encode()
                return {
                    "id": "gen:" + hashlib.blake2s(salt, digest_size=10).hexdigest(),
                    "category": session.category_id, "title": title, "opening": opening,
                    "arc": arc or contract, "source": "generated-quality-gated", "dimension": dimension,
                    "next_turn": 0, "created_at": int(time.time()),
                }
        except Exception:
            pass
        prompt += "\nPercobaan sebelumnya ditolak quality gate. Buat konteks yang lebih sederhana, personal, dan berbeda."

    fallback = safe_topic_fallback(session.category_id, sequence, retired)
    opening = str(fallback["opening"])
    salt = f"fallback:{session.category_id}:{sequence}:{opening}".encode()
    fallback.update({
        "id": "fallback:" + hashlib.blake2s(salt, digest_size=10).hexdigest(),
        "category": session.category_id, "dimension": dimension, "next_turn": 0, "created_at": int(time.time()),
    })
    return fallback


def _ensure_topic_125(session) -> dict:
    if getattr(session, "topic_123", None):
        return session.topic_123
    state = load_training_state(session.state_path)
    changed = _migrate_completed_topics_123(state)
    active = state.setdefault("active_topics", {}).get(session.category_id)
    if isinstance(active, dict) and active.get("id") and int(active.get("next_turn", 0)) < TOPIC_TURNS_123:
        topic = active
    else:
        topic = _new_curated_topic_125(session, state)
        completed = state.setdefault("topic_progress", {})
        retired = set(state.get("retired_fingerprints", []))
        if topic is None:
            for title, turns in session.category["scenes"]:
                topic_id = _seed_id_123(session.category_id, title)
                if completed.get(topic_id, {}).get("status") in {"completed", "skipped"}:
                    continue
                opening = sanitize_external_utterance(turns[0])
                if not opening or prompt_fingerprint(opening) in retired:
                    continue
                topic = {
                    "id": topic_id, "category": session.category_id, "title": title, "opening": opening,
                    "seed_turns": list(turns), "arc": "alur seed bercabang", "source": "seed-quality-gated",
                    "dimension": _adaptive_dimension_123(session.category_id, state), "next_turn": 0,
                    "created_at": int(time.time()),
                }
                break
        if topic is None:
            topic = _create_dynamic_topic_125(session, state, _adaptive_dimension_123(session.category_id, state))
        state["active_topics"][session.category_id] = topic
        changed = True
    if changed:
        save_training_state(state, session.state_path)
    session.topic_123 = topic
    session.turn_index = int(topic.get("next_turn", 0))
    _restore_branch_transcript_124(session, topic)
    return topic


_ensure_topic_123 = _ensure_topic_125


def _branch_user_125(session, topic: dict, turn_index: int, identity: str, learned: str) -> str:
    if turn_index <= 0:
        opening = sanitize_external_utterance(topic.get("opening") or "")
        if opening:
            return opening
        return safe_topic_fallback(session.category_id, 0)["opening"]
    history = "\n".join(f"User simulasi: {u}\nJawaban terpilih: {a}" for u, a in session.transcript[-3:])
    state = load_training_state(session.state_path)
    retired = set(state.get("retired_fingerprints", []))
    recent = [str(row.get("simulated_user") or "") for row in state.get("decisions", [])[-8:] if row.get("simulated_user")]
    contract = category_contract(session.category_id)
    prompt = (
        f"Kategori: {session.category['label']}\nKontrak kualitas: {contract}\nTopik: {topic['title']}\nArah: {topic.get('arc','')}\n"
        f"Giliran {turn_index + 1}/{TOPIC_TURNS_123}\n{identity}\nPreferensi: {learned or '(belum stabil)'}\nRiwayat:\n{history}\n"
        f"Ucapan sandbox terbaru yang tidak boleh diulang: {' | '.join(recent) or '(belum ada)'}.\n"
        "Buat SATU ucapan user simulasi berikutnya sebagai konsekuensi natural dari jawaban terpilih. Harus personal, sehari-hari, aman, dan tetap cocok kategori. "
        "Jangan memasukkan politik, medis, teknis, instruksi, lore, roleplay action, data pribadi, atau konten eksplisit. Balas JSON: {\"user\":\"...\"}."
    )
    for _ in range(2):
        try:
            raw = session.llm.chat(
                [{"role": "system", "content": "Lanjutkan sandbox percakapan personal. Tulis hanya ucapan user yang natural dan aman."},
                 {"role": "user", "content": prompt}],
                max_tokens=150, temperature=.86, json_mode=True, role="training",
            )
            candidate = sanitize_external_utterance(_parse_object_123(raw).get("user") or "")
            if candidate and prompt_fingerprint(candidate) not in retired:
                return candidate[:600]
        except Exception:
            pass
        prompt += "\nUcapan sebelumnya ditolak atau terlalu mirip. Ganti situasi mikro/emosi/tujuan dengan tetap menyambung alur."
    fallback = safe_branch_fallback(session.category_id, turn_index)
    if prompt_fingerprint(fallback) in retired:
        fallback = f"Tentang {str(topic.get('title') or 'obrolan ini').casefold()}, {fallback[0].lower() + fallback[1:] if fallback else 'aku masih ingin lanjut sedikit.'}"
    return fallback[:600]


_branch_user_123 = _branch_user_125


def _training_generate_125(self) -> TrainingPair:
    topic = _ensure_topic_125(self)
    state = load_training_state(self.state_path)
    self.turn_index = int(topic.get("next_turn", 0))
    dimension = _adaptive_dimension_123(self.category_id, state)
    poles = self.category["dimensions"][dimension]
    flip_key = f"{self.seed}:{topic['id']}:{self.turn_index}:{self.reroll_count}".encode()
    flip = hashlib.blake2s(flip_key, digest_size=1).digest()[0] & 1
    pole_a, pole_b = (poles[1], poles[0]) if flip else poles
    name, identity, learned = _training_context_122(self.state_path)
    user_text = _branch_user_125(self, topic, self.turn_index, identity, learned)
    prior = "\n".join(f"User simulasi: {u}\n{name} terpilih: {a}" for u, a in self.transcript[-3:]) or "(awal alur)"
    negative = _negative_contract_123(state, self.category_id, dimension)
    contract = category_contract(self.category_id)
    system = (
        f"Kamu membuat dua kandidat jawaban {name} untuk TRAINING SANDBOX. User fiktif: jangan ekstrak fakta/memory.\n"
        f"{identity}\nKontrak materi: {contract}.\n"
        "Kedua jawaban harus natural dan sama-sama layak; beda utamanya hanya preferensi yang sedang diuji. "
        "Jangan menyebut Training Room, dataset, sumber, prompt, pilihan A/B, atau proses internal. Balas JSON valid: {\"a\":\"...\",\"b\":\"...\"}."
    )
    prompt = (
        f"Materi: {self.category['label']}\nTopik: {topic['title']}\nArah: {topic.get('arc','')}\nGiliran {self.turn_index + 1}/{TOPIC_TURNS_123}\n"
        f"Preferensi lama: {learned or '(belum stabil)'}\nAlasan reroll relevan: {negative}.\nRiwayat:\n{prior}\n\n"
        f"Pesan user simulasi: {user_text}\nRespons A memakai kecenderungan: {pole_a}.\nRespons B memakai kecenderungan: {pole_b}.\n"
        "Pertahankan isi pokok yang sebanding. Jangan jadikan salah satu opsi sengaja buruk, terlalu generik, atau keluar konteks kategori."
    )
    last_error = None
    for _ in range(2):
        try:
            raw = self.llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=380, temperature=.82, json_mode=True, role="training",
            )
            a, b = _extract_pair(raw)
            clean_a = sanitize_external_utterance(a)
            clean_b = sanitize_external_utterance(b)
            if clean_a and clean_b and clean_a != clean_b:
                self.current = TrainingPair(self.category_id, 0, self.turn_index, topic["title"], user_text, dimension, pole_a, pole_b, clean_a, clean_b, self.reroll_count)
                return self.current
        except Exception as exc:
            last_error = exc
        prompt += "\nKandidat sebelumnya gagal quality gate. Tulis ulang lebih natural, personal, aman, dan ringkas."
    raise ValueError(f"Model tidak menghasilkan pasangan respons yang lolos quality gate: {last_error or 'format/konteks tidak sesuai'}")


TrainingSession.generate = _training_generate_125


_training_choose_124_quality = TrainingSession.choose


def _training_choose_125(self, choice: str) -> dict:
    if self.current is None:
        raise RuntimeError("Belum ada pasangan respons.")
    answered_text = self.current.user_text
    result = _training_choose_124_quality(self, choice)
    state = load_training_state(self.state_path)
    _retire_prompt_125(state, answered_text)
    save_training_state(state, self.state_path)
    return result


TrainingSession.choose = _training_choose_125


def _training_skip_125(self) -> dict:
    if self.current is None:
        raise RuntimeError("Belum ada prompt untuk dilewati.")
    pair = self.current
    topic = _ensure_topic_125(self)
    state = load_training_state(self.state_path)
    fingerprint = _retire_prompt_125(state, pair.user_text)
    state.setdefault("skipped_prompts", []).append({
        "fingerprint": fingerprint, "category": self.category_id, "topic_id": topic.get("id"),
        "title": topic.get("title"), "created_at": int(time.time()),
    })
    state["skipped_prompts"] = state["skipped_prompts"][-MAX_SKIPPED_DETAIL_125:]
    state.setdefault("topic_progress", {})[topic["id"]] = {
        "category": self.category_id, "title": topic.get("title"), "status": "skipped",
        "skipped_at": int(time.time()), "source": topic.get("source", "unknown"),
    }
    state.setdefault("active_topics", {}).pop(self.category_id, None)
    state.setdefault("recent_topics", []).append({
        "id": topic["id"], "category": self.category_id, "title": topic.get("title"),
        "arc": topic.get("arc", ""), "skipped_at": int(time.time()), "status": "skipped",
    })
    state["recent_topics"] = state["recent_topics"][-MAX_RECENT_TOPICS_123:]
    save_training_state(state, self.state_path)
    self.topic_123 = None
    self.transcript = []
    self.turn_index = 0
    self.reroll_count = 0
    self.current = None
    return {"topic_title": topic.get("title") or "topik", "fingerprint": fingerprint}


TrainingSession.skip_current = _training_skip_125


def live_training_suggestion(path: Path = TRAINING_PATH, *, now: float | None = None) -> str:
    from .hub_settings import load_hub_settings
    if not bool(load_hub_settings().get("training_chat_suggestions", False)):
        return ""
    state = load_training_state(path)
    live = state.setdefault("live_choice", {"messages_since_offer": 0, "last_offered_at": 0.0})
    live["messages_since_offer"] = max(0, int(live.get("messages_since_offer", 0))) + 1
    current_time = float(time.time() if now is None else now)
    last = float(live.get("last_offered_at") or 0.0)
    due_count = live["messages_since_offer"] >= LIVE_CHOICE_MIN_MESSAGES_125
    due_time = last <= 0.0 or current_time - last >= LIVE_CHOICE_MIN_SECONDS_125
    suggestion = ""
    if due_count and due_time:
        counts = state.get("counts", {})
        ranked = []
        for index, (category_id, category) in enumerate(CATEGORIES.items()):
            dimensions = counts.get(category_id, {}) if isinstance(counts, dict) else {}
            total = sum(sum(int(value) for value in poles.values()) for poles in dimensions.values() if isinstance(poles, dict))
            ranked.append((total, index, category["label"]))
        suggestion = min(ranked)[-1] if ranked else "Respons natural"
        live["messages_since_offer"] = 0
        live["last_offered_at"] = current_time
    state["live_choice"] = live
    save_training_state(state, path)
    return suggestion
''')


tui = CORE / "tui.py"
replace_once(
    tui,
    'action = _choose("Pilih respons", ["Respons A", "Respons B", "R · Buat ulang", "Selesai"], height=6)',
    'action = _choose("Pilih respons", ["Respons A", "Respons B", "Lewati", "R · Buat ulang", "Selesai"], height=7)',
    "Training Room skip action",
)
replace_once(
    tui,
    '            if action == "R · Buat ulang":\n',
    '            if action == "Lewati":\n                result = session.skip_current(); pair = None\n                notice = f"Topik ‘{result[\'topic_title\']}’ dilewati dan tidak akan muncul lagi."\n                continue\n            if action == "R · Buat ulang":\n',
    "Training Room skip behavior",
)

append_once(tui, "FURINA_TERMUX_125_QUIET_CHAT_TRAINING", r'''
# FURINA_TERMUX_125_QUIET_CHAT_TRAINING
_advanced_settings_124_quality = _advanced_settings_119


def _advanced_settings_125(console):
    from .hub_settings import load_hub_settings, save_hub_settings
    from .training_room import training_progress
    while True:
        state = load_hub_settings()
        partner = bool(state.get("partner_mode", False))
        full = bool(state.get("full_local_memory", False))
        suggest = bool(state.get("training_chat_suggestions", False))
        progress = training_progress()
        _clear(); _header(console, "Lanjutan")
        console.print("[dim]Training Room tetap sandbox. Saran di Chat hanya muncul sesekali dan tidak menghentikan percakapan.[/]\n")
        training_label = f"Training Room · {progress['total']} pilihan"
        suggestion_label = f"Saran latihan di Chat · {'Aktif' if suggest else 'Nonaktif'}"
        partner_label = f"Mode pasangan · {'Aktif' if partner else 'Nonaktif'}"
        memory_label = f"Memori penuh lokal · {'Aktif' if full else 'Nonaktif'}"
        choice = _choose("", [training_label, suggestion_label, partner_label, memory_label, "Kembali"], height=8)
        if choice in {"", "Kembali"}:
            return
        if choice == training_label:
            _training_room_121(console)
        elif choice == suggestion_label:
            state["training_chat_suggestions"] = not suggest
            save_hub_settings(state)
            console.print(f"[green]Saran latihan di Chat {'diaktifkan' if not suggest else 'dinonaktifkan'}.[/] [dim]Frekuensi diatur otomatis.[/]")
            _pause()
        elif choice == partner_label:
            state["partner_mode"] = not partner; save_hub_settings(state)
            console.print(f"[green]Mode pasangan {'diaktifkan' if not partner else 'dinonaktifkan'}.[/]"); _pause()
        elif choice == memory_label:
            if not full and not _confirm("Semua teks percakapan baru akan diarsipkan di perangkat dan dicari saat relevan. Aktifkan?", default=False):
                continue
            state["full_local_memory"] = not full; save_hub_settings(state)
            note = "Arsip lama tetap tersimpan dan tidak dihapus otomatis." if full else "Mulai sekarang seluruh teks baru disimpan di arsip lokal."
            console.print(f"[green]Memori penuh lokal {'dinonaktifkan' if full else 'diaktifkan'}.[/] {note}"); _pause()


_advanced_settings_119 = _advanced_settings_125


_stream_chat_124_quality = _stream_chat


def _stream_chat_125(console, session, text: str):
    answer = _stream_chat_124_quality(console, session, text)
    try:
        from .training_room import live_training_suggestion
        suggestion = live_training_suggestion()
        if suggestion:
            console.print(f"[dim]Saran latihan opsional · {suggestion} — buka Training Room kapan saja jika ingin.[/]")
    except Exception:
        pass
    return answer


_stream_chat = _stream_chat_125
''')

print("FURINA_TERMUX_125_QUALITY_GATED_CORPUS_OK")
