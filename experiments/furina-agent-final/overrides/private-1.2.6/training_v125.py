from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass

from .neutral_corpus import (
    fallback_neutral_prompt,
    load_neutral_corpus,
    parse_neutral_prompt,
    prompt_fingerprint,
    select_corpus_prompt,
)
from .training_corpus import category_contract, sanitize_external_utterance


def install_training_v125(ns: dict) -> None:
    TrainingPair = ns["TrainingPair"]
    TrainingSession = ns["TrainingSession"]
    CATEGORIES = ns["CATEGORIES"]
    TRAINING_PATH = ns["TRAINING_PATH"]
    base_load = ns["load_training_state"]
    base_save = ns["save_training_state"]
    extract_pair = ns["_extract_pair"]
    training_context = ns["_training_context_122"]
    adaptive_dimension = ns["_adaptive_dimension_123"]
    negative_contract = ns["_negative_contract_123"]

    def load_state(path=TRAINING_PATH):
        state = base_load(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            raw = {}
        retired = raw.get("retired_prompt_ids")
        state["retired_prompt_ids"] = list(dict.fromkeys(str(item) for item in retired or () if item))
        cursors = raw.get("corpus_cursors")
        state["corpus_cursors"] = cursors if isinstance(cursors, dict) else {}
        state["derived_sequence"] = raw.get("derived_sequence") if isinstance(raw.get("derived_sequence"), dict) else {}
        live = raw.get("live_training")
        state["live_training"] = live if isinstance(live, dict) else {}
        state["skipped_prompts"] = max(0, int(raw.get("skipped_prompts") or 0))

        # Migrate every previously answered Training Room utterance. Matching
        # corpus prompts retire globally even though legacy decisions were
        # stored before prompt IDs existed.
        migrated = False
        retired_set = set(state["retired_prompt_ids"])
        for row in state.get("decisions") or ():
            text = str(row.get("simulated_user") or "").strip()
            if not text:
                continue
            marker = "fp:" + prompt_fingerprint(text)
            if marker not in retired_set:
                retired_set.add(marker)
                migrated = True
        if migrated:
            state["retired_prompt_ids"] = sorted(retired_set)
            base_save(state, path)
        return state

    def retire(state: dict, record: dict, *, status: str) -> None:
        retired = set(str(item) for item in state.get("retired_prompt_ids") or ())
        retired.add(str(record["id"]))
        retired.add("fp:" + prompt_fingerprint(str(record.get("prompt") or "")))
        state["retired_prompt_ids"] = sorted(retired)
        if status == "skipped":
            state["skipped_prompts"] = int(state.get("skipped_prompts") or 0) + 1

    def dynamic_prompt(session, state: dict, dimension: str, anchor: dict | None) -> dict:
        sequence = int(state.setdefault("derived_sequence", {}).get(session.category_id, 0))
        state["derived_sequence"][session.category_id] = sequence + 1
        category = session.category["label"]
        anchor_context = str((anchor or {}).get("context") or "")[:500]
        anchor_prompt = str((anchor or {}).get("prompt") or "")[:420]
        prompt = (
            f"Buat SATU pesan user Bahasa Indonesia untuk menguji kategori {category}, dimensi {dimension}.\n"
            f"Kontrak kualitas kategori: {category_contract(session.category_id)}.\n"
            "Gunakan pasangan percakapan manusia berikut hanya sebagai pola natural, lalu buat situasi BARU yang mandiri.\n"
            f"Konteks sumber: {anchor_context or '(tidak ada)'}\nUcapan sumber: {anchor_prompt or '(tidak ada)'}\n"
            "DILARANG menerima atau menyebut nama companion, sifat companion, status hubungan aktif, memori, preferensi latihan, "
            "Furina, Genshin, lore, Training Room, atau jawaban yang seharusnya diberikan. Jangan menulis jawaban AI. "
            "Hindari nama orang, alamat, akun, nomor, politik, agama, seks, kekerasan, dan informasi pribadi. "
            "Balas JSON saja: {\"context\":\"konteks netral satu kalimat\",\"prompt\":\"pesan user\"}."
        )
        try:
            raw = session.llm.chat(
                [
                    {"role": "system", "content": "Generator prompt netral. Kamu tidak memiliki akses ke identitas, persona, hubungan, memori, atau preferensi pengguna."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=210,
                temperature=.92,
                json_mode=True,
                role="training_prompt",
            )
            parsed = parse_neutral_prompt(raw)
        except Exception:
            parsed = {}
        record = parsed or fallback_neutral_prompt(session.category_id, sequence, anchor)
        digest = prompt_fingerprint(f"{session.category_id}:{sequence}:{record.get('context','')}:{record['prompt']}")
        record.update({
            "id": "derived:" + digest,
            "categories": (session.category_id,),
            "source": "quality-contract neutral variation" if anchor else "neutral fallback",
        })
        return record

    def next_prompt(session, state: dict, dimension: str) -> dict:
        retired = set(str(item) for item in state.get("retired_prompt_ids") or ())
        cursor = int(state.setdefault("corpus_cursors", {}).get(session.category_id, 0))
        record, next_cursor = select_corpus_prompt(session.category_id, retired, session.seed, cursor)
        state["corpus_cursors"][session.category_id] = next_cursor
        if record is not None:
            return record
        corpus = load_neutral_corpus()
        anchor = dict(corpus[(next_cursor + len(retired)) % len(corpus)]) if corpus else None
        for _ in range(4):
            record = dynamic_prompt(session, state, dimension, anchor)
            if record["id"] not in retired and "fp:" + prompt_fingerprint(record["prompt"]) not in retired:
                return record
            state["derived_sequence"][session.category_id] += 1
        return fallback_neutral_prompt(session.category_id, int(state["derived_sequence"].get(session.category_id, 0)), anchor)

    def generate(self):
        state = load_state(self.state_path)
        dimension = adaptive_dimension(self.category_id, state)
        poles = self.category["dimensions"][dimension]
        flip_key = f"{self.seed}:{dimension}:{self.reroll_count}".encode()
        flip = hashlib.blake2s(flip_key, digest_size=1).digest()[0] & 1
        pole_a, pole_b = (poles[1], poles[0]) if flip else poles

        record = getattr(self, "prompt_125", None)
        if not isinstance(record, dict):
            record = next_prompt(self, state, dimension)
            self.prompt_125 = record
            base_save(state, self.state_path)

        name, identity, learned = training_context(self.state_path)
        negative = negative_contract(state, self.category_id, dimension)
        system = (
            f"Kamu membuat dua kandidat jawaban {name} untuk TRAINING SANDBOX. Pesan uji sudah dikunci dari korpus netral. "
            "Jangan mengubah, melanjutkan sebagai user, atau menganggapnya memori. Nama aktif tidak membawa lore.\n"
            f"{identity}\nKontrak kualitas materi: {category_contract(self.category_id)}. "
            "Kedua respons harus sama-sama layak dan berbeda terutama pada satu dimensi. "
            "Balas JSON valid saja: {\"a\":\"...\",\"b\":\"...\"}."
        )
        context = str(record.get("context") or "(tanpa konteks tambahan)")
        prompt = (
            f"Materi: {self.category['label']}\nDimensi: {dimension}\n{identity}\n"
            f"Preferensi lama:\n{learned or '(belum stabil)'}\nAlasan reroll: {negative}.\n"
            f"Konteks percakapan manusia: {context}\nPesan user yang harus dijawab: {record['prompt']}\n"
            f"Respons A: {pole_a}.\nRespons B: {pole_b}.\n"
            "Terapkan preferensi lama yang relevan pada keduanya, kecuali dimensi yang sedang dibandingkan. Jangan menyebut sumber data atau pilihan A/B."
        )
        a = b = ""
        for attempt in range(2):
            raw = self.llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=420,
                temperature=.84,
                json_mode=True,
                role="training",
            )
            raw_a, raw_b = extract_pair(raw)
            a = sanitize_external_utterance(raw_a) or ""
            b = sanitize_external_utterance(raw_b) or ""
            if a and b and a != b:
                break
            prompt += "\nKandidat sebelumnya gagal quality gate. Tulis ulang lebih natural, aman, spesifik, dan tetap berbeda hanya pada dimensi uji."
        if not a or not b or a == b:
            raise ValueError("Model tidak menghasilkan dua respons yang lolos quality gate.")
        pair = TrainingPair(self.category_id, 0, 0, "Percakapan nyata", record["prompt"], dimension, pole_a, pole_b, a, b, self.reroll_count)
        pair.prompt_id = record["id"]
        pair.context_text = context
        pair.corpus_source = record.get("source", "neutral corpus")
        self.current = pair
        return pair

    def choose(self, choice: str) -> dict:
        if self.current is None:
            raise RuntimeError("Belum ada pasangan respons.")
        key = str(choice).strip().lower()
        if key not in {"a", "b"}:
            raise ValueError("Pilihan harus A atau B.")
        pair = self.current
        record = self.prompt_125
        chosen_pole = pair.pole_a if key == "a" else pair.pole_b
        rejected_pole = pair.pole_b if key == "a" else pair.pole_a
        chosen_text = pair.response_a if key == "a" else pair.response_b
        rejected_text = pair.response_b if key == "a" else pair.response_a
        state = load_state(self.state_path)
        counts = state["counts"].setdefault(pair.category_id, {}).setdefault(pair.dimension, {})
        counts[chosen_pole] = int(counts.get(chosen_pole, 0)) + 1
        state["decisions"].append({
            "category": pair.category_id,
            "prompt_id": record["id"],
            "scene": "Percakapan nyata",
            "turn": 0,
            "dimension": pair.dimension,
            "chosen_pole": chosen_pole,
            "rejected_pole": rejected_pole,
            "simulated_user": pair.user_text,
            "chosen": chosen_text,
            "rejected": rejected_text,
            "source": "neutral_corpus",
            "created_at": int(time.time()),
        })
        retire(state, record, status="answered")
        base_save(state, self.state_path)
        self.session_choices.append(chosen_pole)
        self.current = None
        self.prompt_125 = None
        self.reroll_count = 0
        return {"chosen_pole": chosen_pole, "count": len(self.session_choices), "prompt_retired": True}

    def skip(self) -> dict:
        if self.current is None or not isinstance(getattr(self, "prompt_125", None), dict):
            raise RuntimeError("Belum ada prompt yang dapat dilewati.")
        state = load_state(self.state_path)
        record = self.prompt_125
        retire(state, record, status="skipped")
        base_save(state, self.state_path)
        self.current = None
        self.prompt_125 = None
        self.reroll_count = 0
        return {"prompt_retired": True, "skipped": int(state["skipped_prompts"])}

    previous_progress = ns["training_progress"]

    def progress(path=TRAINING_PATH):
        result = previous_progress(path)
        state = load_state(path)
        retired = [item for item in state.get("retired_prompt_ids") or () if not str(item).startswith("fp:")]
        result["retired_prompts"] = len(retired)
        result["skipped_prompts"] = int(state.get("skipped_prompts") or 0)
        result["corpus_size"] = len(load_neutral_corpus())
        return result

    @dataclass
    class LiveTrainingPair:
        category_id: str
        dimension: str
        pole_a: str
        pole_b: str
        response_a: str
        response_b: str
        message_hash: str

    def live_category(text: str) -> str:
        value = " ".join(str(text or "").casefold().split())
        if re.search(r"\b(tapi|namun|padahal|meski)\b", value) and re.search(r"\b(senang|sedih|takut|bangga|marah|capek|lelah|lega|kecewa)\b", value):
            return "mixed_emotion"
        if re.search(r"\b(terserah|iya deh|hebat sekali|bagus banget|serius|maksudnya|beneran)\b", value):
            return "ambiguous_tone"
        if re.search(r"\b(gimana|bagaimana|harus|mending|sebaiknya|bantu|mulai|pilih)\b", value):
            return "initiative"
        if re.search(r"\b(sedih|kecewa|kesal|marah|takut|cemas|capek|lelah|senang|bangga|malu|bingung|stres)\b", value):
            return "emotional"
        if re.search(r"wkwk|haha|hehe|bercanda|lucu|ngakak", value):
            return "playful"
        return "natural"

    def should_offer_live(text: str, *, session_offers: int = 0, path=TRAINING_PATH) -> bool:
        from .hub_settings import load_hub_settings

        if not load_hub_settings().get("training_suggestions") or session_offers >= 2:
            return False
        value = " ".join(str(text or "").split())
        folded = value.casefold()
        if len(value) < 12 or len(value) > 700 or value.startswith("/") or "http" in folded:
            return False
        if re.search(r"```|\b(error|traceback|kode|script|python|javascript|github|termux|install|update|hapus file|jalankan)\b", folded):
            return False
        if re.search(r"\b(bunuh diri|darurat|sesak napas|pendarahan|overdosis|kekerasan)\b", folded):
            return False

        state = load_state(path)
        live = state.setdefault("live_training", {})
        seen = int(live.get("eligible_seen") or 0) + 1
        live["eligible_seen"] = seen
        last = int(live.get("last_offer_seen") or 0)
        high_signal = live_category(value) != "natural"
        cooled_down = (last == 0 and seen >= 8) or (last > 0 and seen - last >= 12)
        eligible = cooled_down and (high_signal or seen % 18 == 0)
        if eligible:
            live["last_offer_seen"] = seen
        base_save(state, path)
        return eligible

    def generate_live(chat, user_text: str) -> LiveTrainingPair:
        from .response import choose_profile

        state = load_state(TRAINING_PATH)
        category_id = live_category(user_text)
        dimension = adaptive_dimension(category_id, state)
        poles = CATEGORIES[category_id]["dimensions"][dimension]
        flip = hashlib.blake2s(user_text.encode(), digest_size=1).digest()[0] & 1
        pole_a, pole_b = (poles[1], poles[0]) if flip else poles
        profile = choose_profile(user_text, chat.store)
        messages = chat._messages(user_text, profile)
        if not messages or messages[0].get("role") != "system":
            raise RuntimeError("Konteks chat tidak tersedia.")
        system = str(messages[0]["content"]) + (
            "\n\n[LIVE PREFERENCE CHOICE]\nBuat dua respons yang sama-sama layak untuk pesan user terakhir. "
            f"A terutama memakai: {pole_a}. B terutama memakai: {pole_b}. "
            "Semua aturan persona, hubungan, memory, dan preferensi aktif berlaku sama pada keduanya. "
            "Jangan menyebut pilihan atau pelatihan. Balas JSON saja: {\"a\":\"...\",\"b\":\"...\"}."
        )
        a = b = ""
        live_messages = [{"role": "system", "content": system}, {"role": "user", "content": user_text}]
        for _ in range(2):
            raw = chat.llm.chat(
                live_messages,
                max_tokens=500,
                temperature=.82,
                json_mode=True,
                role="live_training",
            )
            raw_a, raw_b = extract_pair(raw)
            a = sanitize_external_utterance(raw_a) or ""
            b = sanitize_external_utterance(raw_b) or ""
            if a and b and a != b:
                break
            live_messages = [
                live_messages[0],
                {"role": "user", "content": user_text + "\n\nKandidat sebelumnya gagal quality gate. Buat dua jawaban baru yang aman, natural, dan tetap sesuai konteks."},
            ]
        if not a or not b or a == b:
            raise ValueError("Model tidak menghasilkan dua pilihan live yang layak.")
        return LiveTrainingPair(category_id, dimension, pole_a, pole_b, a, b, prompt_fingerprint(user_text))

    def record_live_choice(pair: LiveTrainingPair, choice: str, path=TRAINING_PATH) -> str:
        key = str(choice).casefold()
        if key not in {"a", "b"}:
            raise ValueError("Pilihan live harus A atau B.")
        chosen_pole = pair.pole_a if key == "a" else pair.pole_b
        rejected_pole = pair.pole_b if key == "a" else pair.pole_a
        state = load_state(path)
        counts = state["counts"].setdefault(pair.category_id, {}).setdefault(pair.dimension, {})
        counts[chosen_pole] = int(counts.get(chosen_pole, 0)) + 1
        # Real chat content stays in the normal chat store. The Training Room
        # receives only a hash and abstract poles, never a second raw copy.
        state["decisions"].append({
            "category": pair.category_id,
            "dimension": pair.dimension,
            "chosen_pole": chosen_pole,
            "rejected_pole": rejected_pole,
            "message_hash": pair.message_hash,
            "source": "live_chat_explicit_choice",
            "created_at": int(time.time()),
        })
        base_save(state, path)
        return pair.response_a if key == "a" else pair.response_b

    def record_live_skip(path=TRAINING_PATH) -> None:
        state = load_state(path)
        live = state.setdefault("live_training", {})
        live["last_offer_seen"] = int(live.get("eligible_seen") or 0) + 8
        live["skips"] = int(live.get("skips") or 0) + 1
        base_save(state, path)

    ns.update({
        "load_training_state": load_state,
        "training_progress": progress,
        "LiveTrainingPair": LiveTrainingPair,
        "should_offer_live_training": should_offer_live,
        "generate_live_training_pair": generate_live,
        "record_live_training_choice": record_live_choice,
        "record_live_training_skip": record_live_skip,
    })
    TrainingSession.generate = generate
    TrainingSession.choose = choose
    TrainingSession.skip = skip
