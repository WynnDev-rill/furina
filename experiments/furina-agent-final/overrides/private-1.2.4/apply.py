#!/usr/bin/env python3
"""Build Core 1.1.23: persistent adaptive curriculum and branching stories."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"


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


replace_once(CORE / "version.py", 'VERSION = "1.1.22"', 'VERSION = "1.1.23"', "Core 1.1.22")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r72"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r73"', "dependency r72")
replace_once(CORE / "hub.py", "furina-2026.08.26-termux-1.1.22", "furina-2026.08.26-termux-1.1.23", "bundle 1.1.22")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.26-r72"', 'expected_revision = "2026.08.26-r73"', "expected revision r72")


append_once(CORE / "training_room.py", "FURINA_TERMUX_123_DIRECTED_STORY_CURRICULUM", r'''
# FURINA_TERMUX_123_DIRECTED_STORY_CURRICULUM
TOPIC_TURNS_123 = 5
MAX_COMPLETED_TOPICS_123 = 240
MAX_RECENT_TOPICS_123 = 36
REROLL_REASONS_123 = {
    "generic": "Terlalu generik",
    "sweet": "Terlalu manis atau romantis",
    "cold": "Terlalu dingin",
    "long": "Terlalu panjang",
    "unnatural": "Tidak natural",
    "similar": "Keduanya terlalu mirip",
    "context": "Tidak sesuai konteks",
}


_load_training_state_122 = load_training_state


def _load_training_state_123(path: Path = TRAINING_PATH) -> dict:
    state = _load_training_state_122(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    for key, default in (
        ("topic_progress", {}), ("active_topics", {}), ("recent_topics", []),
        ("negative_feedback", {}), ("generated_sequence", {}),
    ):
        value = raw.get(key)
        state[key] = value if isinstance(value, type(default)) else default.copy()
    state["recent_topics"] = list(state["recent_topics"])[-MAX_RECENT_TOPICS_123:]
    return state


load_training_state = _load_training_state_123


def _slug_123(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
    return clean[:48] or "topic"


def _seed_id_123(category_id: str, title: str) -> str:
    return f"seed:{category_id}:{_slug_123(title)}"


def _migrate_completed_topics_123(state: dict) -> bool:
    progress = state.setdefault("topic_progress", {})
    changed = False
    observed: dict[tuple[str, str], set[int]] = {}
    for row in state.get("decisions") or []:
        category_id = str(row.get("category") or "")
        title = str(row.get("scene") or "")
        if category_id not in CATEGORIES or not title:
            continue
        try:
            turn = int(row.get("turn", -1))
        except (TypeError, ValueError):
            continue
        observed.setdefault((category_id, title), set()).add(turn)
    for (category_id, title), turns in observed.items():
        if len(turns & set(range(TOPIC_TURNS_123))) < TOPIC_TURNS_123:
            continue
        topic_id = _seed_id_123(category_id, title)
        if topic_id not in progress:
            progress[topic_id] = {"category": category_id, "title": title, "status": "completed", "migrated": True}
            changed = True
    return changed


def _adaptive_dimension_123(category_id: str, state: dict) -> str:
    dimensions = CATEGORIES[category_id]["dimensions"]
    counts = state.get("counts", {}).get(category_id, {})
    ranked = []
    for index, dimension in enumerate(dimensions):
        poles = counts.get(dimension) if isinstance(counts, dict) else {}
        values = [max(0, int(v)) for v in (poles or {}).values()]
        total = sum(values)
        margin = abs(values[0] - values[1]) if len(values) >= 2 else (values[0] if values else 0)
        certainty = margin / total if total else 0.0
        # Least evidence first; when evidence ties, conflicted dimensions win.
        ranked.append((total, certainty, index, dimension))
    return min(ranked)[-1]


def _negative_contract_123(state: dict, category_id: str, dimension: str) -> str:
    rows = state.get("negative_feedback", {}).get(category_id, {}).get(dimension, {})
    if not isinstance(rows, dict) or not rows:
        return "(belum ada alasan penolakan untuk dimensi ini)"
    ordered = sorted(((int(count), key) for key, count in rows.items()), reverse=True)[:4]
    return "; ".join(f"hindari {REROLL_REASONS_123.get(key, key).casefold()} ({count}x)" for count, key in ordered)


def _fallback_topic_123(category_id: str, sequence: int, dimension: str) -> dict:
    settings = (
        "perjalanan singkat", "rumah saat listrik padam", "warung yang sepi", "ruang tunggu",
        "hujan mendadak", "akhir pekan tanpa rencana", "pesan suara larut malam", "setelah permainan",
    )
    shifts = (
        "candaan berubah serius", "rencana kecil terganggu", "kabar baik terasa meragukan",
        "salah paham perlu diperbaiki", "user meminta kejujuran", "suasana tegang mulai mencair",
    )
    setting = settings[sequence % len(settings)]
    shift = shifts[(sequence // len(settings)) % len(shifts)]
    title = f"{setting.title()} · {sequence + 1}"
    opening = f"Kita sedang dalam situasi {setting}, lalu {shift}. Aku ingin melihat bagaimana kamu menanggapinya."
    return {"title": title, "opening": opening, "arc": shift, "source": "combinatorial", "dimension": dimension}


def _parse_object_123(raw: str) -> dict:
    clean = str(raw or "").strip()
    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        clean = match.group(0)
    try:
        value = json.loads(clean)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _create_dynamic_topic_123(session, state: dict, dimension: str) -> dict:
    sequence = int(state.setdefault("generated_sequence", {}).get(session.category_id, 0))
    state["generated_sequence"][session.category_id] = sequence + 1
    recent = [row for row in state.get("recent_topics", []) if row.get("category") == session.category_id][-12:]
    recent_text = ", ".join(str(row.get("title") or "") for row in recent) or "(belum ada)"
    name, identity, learned = _training_context_122(session.state_path)
    prompt = (
        f"Buat SATU topik baru untuk Training Room kategori {session.category['label']}. Fokus kurikulum: {dimension}.\n"
        f"{identity}\nPreferensi yang dipelajari:\n{learned or '(belum stabil)'}\n"
        f"Topik terbaru yang DILARANG diulang atau diparafrasekan: {recent_text}.\n"
        "Gunakan situasi sehari-hari yang konkret dan berbeda dalam lokasi, tujuan user, tingkat emosi, konflik, serta perubahan suasana. "
        "Ini simulasi tanpa lore dan tanpa fakta user nyata. Balas JSON saja: "
        '{"title":"judul singkat","opening":"ucapan pertama user simulasi","arc":"arah konflik/perubahan"}.'
    )
    try:
        raw = session.llm.chat(
            [{"role": "system", "content": "Kamu merancang skenario latihan percakapan yang baru, aman, realistis, dan tidak repetitif."},
             {"role": "user", "content": prompt}],
            max_tokens=220, temperature=.95, json_mode=True, role="training",
        )
        data = _parse_object_123(raw)
        title = str(data.get("title") or "").strip()[:96]
        opening = str(data.get("opening") or "").strip()[:600]
        arc = str(data.get("arc") or "").strip()[:240]
        if not title or not opening:
            raise ValueError("blueprint tidak lengkap")
        topic = {"title": title, "opening": opening, "arc": arc or "berkembang mengikuti pilihan", "source": "generated", "dimension": dimension}
    except Exception:
        topic = _fallback_topic_123(session.category_id, sequence, dimension)
    salt = f"{session.category_id}:{sequence}:{topic['title']}:{time.time_ns()}".encode()
    topic["id"] = "gen:" + hashlib.blake2s(salt, digest_size=10).hexdigest()
    topic.update({"category": session.category_id, "next_turn": 0, "created_at": int(time.time())})
    return topic


def _ensure_topic_123(session) -> dict:
    if getattr(session, "topic_123", None):
        return session.topic_123
    state = load_training_state(session.state_path)
    changed = _migrate_completed_topics_123(state)
    active = state.setdefault("active_topics", {}).get(session.category_id)
    if isinstance(active, dict) and active.get("id") and active.get("next_turn", 0) < TOPIC_TURNS_123:
        topic = active
    else:
        topic = None
        completed = state.setdefault("topic_progress", {})
        for title, turns in session.category["scenes"]:
            topic_id = _seed_id_123(session.category_id, title)
            if completed.get(topic_id, {}).get("status") == "completed":
                continue
            topic = {
                "id": topic_id, "category": session.category_id, "title": title, "opening": turns[0],
                "seed_turns": list(turns), "arc": "alur seed bercabang", "source": "seed",
                "dimension": _adaptive_dimension_123(session.category_id, state), "next_turn": 0,
                "created_at": int(time.time()),
            }
            break
        if topic is None:
            topic = _create_dynamic_topic_123(session, state, _adaptive_dimension_123(session.category_id, state))
        state["active_topics"][session.category_id] = topic
        changed = True
    if changed:
        save_training_state(state, session.state_path)
    session.topic_123 = topic
    session.turn_index = int(topic.get("next_turn", 0))
    return topic


def _branch_user_123(session, topic: dict, turn_index: int, identity: str, learned: str) -> str:
    if turn_index <= 0:
        return str(topic.get("opening") or "Mari mulai dari sini.")
    previous_user, previous_answer = session.transcript[-1]
    fallback_turns = topic.get("seed_turns") or []
    fallback = str(fallback_turns[turn_index]) if turn_index < len(fallback_turns) else f"Jawabanmu mengubah arah percakapan. Lanjutkan dengan jujur pada bagian {turn_index + 1}."
    history = "\n".join(f"User simulasi: {u}\nJawaban terpilih: {a}" for u, a in session.transcript[-3:])
    prompt = (
        f"Topik: {topic['title']}\nArah alur: {topic.get('arc','')}\nGiliran: {turn_index + 1}/{TOPIC_TURNS_123}\n"
        f"{identity}\nPreferensi: {learned or '(belum stabil)'}\nRiwayat:\n{history}\n"
        "Buat SATU ucapan user simulasi berikutnya yang merupakan konsekuensi nyata dari jawaban terpilih terakhir. "
        "Cabangkan emosi, informasi, atau tujuan percakapan; jangan mengulang ucapan sebelumnya. Balas JSON saja: {\"user\":\"...\"}."
    )
    try:
        raw = session.llm.chat(
            [{"role": "system", "content": "Lanjutkan sandbox story bercabang. Jangan menulis jawaban companion dan jangan membuat memori nyata."},
             {"role": "user", "content": prompt}],
            max_tokens=150, temperature=.9, json_mode=True, role="training",
        )
        user_text = str(_parse_object_123(raw).get("user") or "").strip()
        return user_text[:600] if user_text else fallback
    except Exception:
        return fallback


def _training_generate_123(self) -> TrainingPair:
    topic = _ensure_topic_123(self)
    state = load_training_state(self.state_path)
    self.turn_index = int(topic.get("next_turn", 0))
    dimension = _adaptive_dimension_123(self.category_id, state)
    poles = self.category["dimensions"][dimension]
    flip_key = f"{self.seed}:{topic['id']}:{self.turn_index}:{self.reroll_count}".encode()
    flip = hashlib.blake2s(flip_key, digest_size=1).digest()[0] & 1
    pole_a, pole_b = (poles[1], poles[0]) if flip else poles
    name, identity, learned = _training_context_122(self.state_path)
    user_text = _branch_user_123(self, topic, self.turn_index, identity, learned)
    prior = "\n".join(f"User simulasi: {u}\n{name} terpilih: {a}" for u, a in self.transcript[-3:]) or "(awal alur)"
    negative = _negative_contract_123(state, self.category_id, dimension)
    system = (
        f"Kamu membuat dua kandidat jawaban {name} untuk TRAINING SANDBOX bercabang. User fiktif: jangan ekstrak fakta atau memory.\n"
        f"{identity}\nKedua jawaban harus natural, sama-sama layak, dan berbeda terutama pada satu preferensi. "
        "Balas JSON valid saja: {\"a\":\"...\",\"b\":\"...\"}."
    )
    prompt = (
        f"Materi: {self.category['label']}\nTopik unik: {topic['title']}\nArah alur: {topic.get('arc','')}\n"
        f"Giliran {self.turn_index + 1}/{TOPIC_TURNS_123}\n{identity}\nPreferensi lama:\n{learned or '(belum stabil)'}\n"
        f"Alasan reroll yang relevan: {negative}. Hindari pola tersebut pada KEDUA kandidat.\n"
        f"Riwayat cabang:\n{prior}\n\nPesan user simulasi sekarang: {user_text}\n"
        f"Respons A: {pole_a}.\nRespons B: {pole_b}.\n"
        "Terapkan preferensi lama pada keduanya kecuali dimensi yang diuji. Jangan menyebut pelatihan, topik, atau pilihan A/B."
    )
    raw = self.llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=380, temperature=.86, json_mode=True, role="training",
    )
    a, b = _extract_pair(raw)
    self.current = TrainingPair(self.category_id, 0, self.turn_index, topic["title"], user_text, dimension, pole_a, pole_b, a, b, self.reroll_count)
    return self.current


def _training_choose_123(self, choice: str) -> dict:
    if self.current is None:
        raise RuntimeError("Belum ada pasangan respons.")
    key = str(choice).strip().lower()
    if key not in {"a", "b"}:
        raise ValueError("Pilihan harus A atau B.")
    pair = self.current
    topic = _ensure_topic_123(self)
    chosen_pole = pair.pole_a if key == "a" else pair.pole_b
    rejected_pole = pair.pole_b if key == "a" else pair.pole_a
    chosen_text = pair.response_a if key == "a" else pair.response_b
    rejected_text = pair.response_b if key == "a" else pair.response_a
    state = load_training_state(self.state_path)
    category_counts = state["counts"].setdefault(pair.category_id, {})
    dimension_counts = category_counts.setdefault(pair.dimension, {})
    dimension_counts[chosen_pole] = int(dimension_counts.get(chosen_pole, 0)) + 1
    state["decisions"].append({
        "category": pair.category_id, "topic_id": topic["id"], "scene": topic["title"], "turn": pair.turn_index,
        "dimension": pair.dimension, "chosen_pole": chosen_pole, "rejected_pole": rejected_pole,
        "simulated_user": pair.user_text, "chosen": chosen_text, "rejected": rejected_text,
        "created_at": int(time.time()),
    })
    self.session_choices.append(chosen_pole)
    self.transcript.append((pair.user_text, chosen_text))
    next_turn = int(topic.get("next_turn", 0)) + 1
    completed = next_turn >= TOPIC_TURNS_123
    if completed:
        state.setdefault("topic_progress", {})[topic["id"]] = {
            "category": self.category_id, "title": topic["title"], "status": "completed",
            "completed_at": int(time.time()), "source": topic.get("source", "unknown"),
        }
        state.setdefault("active_topics", {}).pop(self.category_id, None)
        state.setdefault("recent_topics", []).append({
            "id": topic["id"], "category": self.category_id, "title": topic["title"],
            "arc": topic.get("arc", ""), "completed_at": int(time.time()),
        })
        state["recent_topics"] = state["recent_topics"][-MAX_RECENT_TOPICS_123:]
        if len(state["topic_progress"]) > MAX_COMPLETED_TOPICS_123:
            generated = [k for k in state["topic_progress"] if k.startswith("gen:")]
            for old in generated[:len(state["topic_progress"]) - MAX_COMPLETED_TOPICS_123]:
                state["topic_progress"].pop(old, None)
        self.topic_123 = None
        self.transcript = []
        self.turn_index = 0
    else:
        topic["next_turn"] = next_turn
        state.setdefault("active_topics", {})[self.category_id] = topic
        self.turn_index = next_turn
    save_training_state(state, self.state_path)
    self.reroll_count = 0
    self.current = None
    return {"chosen_pole": chosen_pole, "count": len(self.session_choices), "topic_completed": completed, "topic_title": topic["title"]}


def _training_reject_pair_123(self, reason: str) -> dict:
    if self.current is None:
        raise RuntimeError("Belum ada pasangan respons.")
    key = str(reason or "").strip().lower()
    if key not in REROLL_REASONS_123:
        raise ValueError("Alasan buat ulang tidak dikenal.")
    pair = self.current
    state = load_training_state(self.state_path)
    bucket = state.setdefault("negative_feedback", {}).setdefault(pair.category_id, {}).setdefault(pair.dimension, {})
    bucket[key] = int(bucket.get(key, 0)) + 1
    save_training_state(state, self.state_path)
    self.reroll_count += 1
    self.current = None
    return {"reason": key, "label": REROLL_REASONS_123[key], "count": bucket[key]}


def _training_progress_123(path: Path = TRAINING_PATH) -> dict:
    state = load_training_state(path)
    by_category = {
        category_id: sum(sum(int(value) for value in poles.values()) for poles in dimensions.values() if isinstance(poles, dict))
        for category_id, dimensions in state["counts"].items() if isinstance(dimensions, dict)
    }
    completed = {}
    for row in state.get("topic_progress", {}).values():
        if row.get("status") == "completed":
            category_id = str(row.get("category") or "")
            completed[category_id] = completed.get(category_id, 0) + 1
    return {"total": sum(by_category.values()), "by_category": by_category, "completed_topics": completed, "updated_at": state["updated_at"]}


TrainingSession.generate = _training_generate_123
TrainingSession.choose = _training_choose_123
TrainingSession.reject_pair = _training_reject_pair_123
training_progress = _training_progress_123
''')


append_once(CORE / "tui.py", "FURINA_TERMUX_123_REASONED_REROLL_STORIES", r'''
# FURINA_TERMUX_123_REASONED_REROLL_STORIES
def _training_room_123(console):
    from .routing import RoutingLLM
    from .training_room import CATEGORIES, REROLL_REASONS_123, TrainingSession, training_progress
    from .hub_settings import load_hub_settings
    labels = [item["label"] for item in CATEGORIES.values()]
    by_label = {item["label"]: key for key, item in CATEGORIES.items()}
    reason_labels = list(REROLL_REASONS_123.values())
    reason_by_label = {label: key for key, label in REROLL_REASONS_123.items()}
    while True:
        progress = training_progress()
        _clear(); _header(console, "Training Room")
        completed = sum(progress.get("completed_topics", {}).values())
        console.print(f"[dim]Preferensi tersimpan[/]  {progress['total']} pilihan  ·  {completed} topik selesai")
        console.print("[dim]Topik selesai tidak diulang. Skenario baru dibuat adaptif dan tetap terpisah dari memori nyata.[/]\n")
        choice = _choose("", labels + ["Kembali"], height=9)
        if choice in {"", "Kembali"}:
            return
        category_id = by_label.get(choice)
        if not category_id:
            continue
        cfg = load_config(); llm = RoutingLLM(cfg); session = TrainingSession(category_id, llm)
        pair = None; notice = ""
        while True:
            if pair is None:
                try:
                    _clear(); _header(console, "Training Room")
                    console.print(f"[#5de4c7]{choice}[/]  [dim]Menyusun alur adaptif dari model aktif…[/]")
                    pair = session.generate()
                except Exception as exc:
                    console.print(f"\n[red]Tidak dapat membuat respons[/]  {str(exc)[:220]}")
                    console.print("[dim]Periksa Provider & Model, lalu coba lagi.[/]"); _pause(); break
            _clear(); _header(console, "Training Room")
            partner = bool(load_hub_settings().get("partner_mode"))
            console.print(f"[#5de4c7]{choice}[/]  [dim]{pair.scene_title} · giliran {pair.turn_index + 1}/5 · Mode pasangan {'aktif' if partner else 'nonaktif'}[/]")
            console.print(f"\n[bold]User simulasi[/]\n{pair.user_text}")
            console.print(f"\n[bold cyan]Respons A[/]\n{pair.response_a}")
            console.print(f"\n[bold cyan]Respons B[/]\n{pair.response_b}")
            if notice:
                console.print(f"\n[green]{notice}[/]")
            action = _choose("Pilih respons", ["Respons A", "Respons B", "R · Buat ulang", "Selesai"], height=6)
            if action in {"", "Selesai"}:
                summary = session.summary()
                _clear(); _header(console, "Training Room")
                console.print(f"[green]Sesi selesai.[/] {summary['choices']} pilihan baru tersimpan.")
                if summary["recent"]:
                    console.print("[dim]Pola terakhir: " + " · ".join(summary["recent"]) + "[/]")
                _pause(); break
            if action == "R · Buat ulang":
                reason_label = _choose("Kenapa keduanya tidak cocok?", reason_labels + ["Batal"], height=10)
                if reason_label in {"", "Batal"}:
                    continue
                result = session.reject_pair(reason_by_label[reason_label])
                pair = None
                notice = f"Alasan dipelajari: {result['label']}. Topik dan giliran tetap sama."
                continue
            if action in {"Respons A", "Respons B"}:
                key = "a" if action == "Respons A" else "b"
                result = session.choose(key); pair = None
                if result.get("topic_completed"):
                    notice = f"Topik ‘{result['topic_title']}’ selesai dan tidak akan diulang. Menyiapkan topik baru."
                else:
                    notice = f"{action} tersimpan · alur berikutnya bercabang dari pilihan ini."


_training_room_121 = _training_room_123
''')


print("FURINA_TERMUX_123_DIRECTED_STORY_CURRICULUM_OK")
