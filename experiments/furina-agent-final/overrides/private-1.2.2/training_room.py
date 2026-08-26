from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .config import DATA_DIR


TRAINING_PATH = DATA_DIR / "training_preferences.json"
SCHEMA_VERSION = 1
MAX_DECISIONS = 300


CATEGORIES = {
    "natural": {
        "label": "Respons natural",
        "dimensions": {
            "directness": ("langsung dan spontan", "lebih bertahap dan reflektif"),
            "affection": ("perhatian tersirat lewat detail", "kehangatan dinyatakan terbuka"),
            "texture": ("kasual dengan tekstur percakapan", "rapi dan tenang"),
        },
        "scenes": (
            ("Pagi yang biasa", ("Baru bangun. Masih malas bergerak.", "Kopinya terlalu pahit hari ini.", "Aku mungkin cuma akan santai sebentar.", "Eh, ternyata sudah hampir siang.", "Baiklah, aku mulai sekarang.")),
            ("Proyek kecil", ("Aku mengganti tampilannya lagi.", "Versi ini lebih sederhana, tapi rasanya kosong.", "Aku takut malah merusak yang sudah bagus.", "Mungkin satu detail kecil saja cukup.", "Oke, keputusan terakhir: yang sederhana.")),
            ("Obrolan malam", ("Hari ini rasanya cepat sekali.", "Tidak ada kejadian besar sebenarnya.", "Tapi ada satu momen kecil yang terus kuingat.", "Aneh ya, hal kecil kadang lebih melekat.", "Sudah malam. Aku ingin diam sebentar.")),
        ),
    },
    "emotional": {
        "label": "Respons emosional",
        "dimensions": {
            "support": ("validasi singkat lalu langkah konkret", "temani emosi tanpa buru-buru memperbaiki"),
            "intensity": ("hangat dan ekspresif", "tenang dan terkendali"),
            "challenge": ("menantang pikiran negatif dengan lembut", "menerima dulu sebelum menilai"),
        },
        "scenes": (
            ("Rencana gagal", ("Yang kurencanakan gagal lagi.", "Aku sudah mengulangnya beberapa kali.", "Sekarang aku mulai meragukan kemampuanku.", "Tapi aku juga tidak ingin berhenti.", "Mungkin aku perlu melihatnya dengan kepala dingin.")),
            ("Lelah tanpa sebab jelas", ("Aku capek, padahal tidak banyak melakukan apa-apa.", "Itu membuatku merasa bersalah.", "Seharusnya aku bisa lebih produktif.", "Tapi memaksa diri juga tidak membantu.", "Aku ingin malam ini tidak terasa sia-sia.")),
            ("Kabar baik", ("Ada satu hal yang akhirnya berhasil.", "Aku senang, tapi masih takut terlalu berharap.", "Biasanya setelah ini ada masalah baru.", "Walau begitu, hasilnya memang nyata.", "Kurasa aku boleh menikmatinya sebentar.")),
        ),
    },
    "partner": {
        "label": "Mode pasangan",
        "dimensions": {
            "affection": ("afeksi tersirat dan spesifik", "afeksi terbuka dan langsung"),
            "closeness": ("hangat tetapi memberi ruang", "intim dan proaktif"),
            "care": ("merawat lewat tindakan kecil", "merawat lewat kata-kata personal"),
        },
        "scenes": (
            ("Pulang terlambat", ("Aku baru selesai sekarang.", "Tadi terlalu fokus sampai lupa waktu.", "Belum makan juga, sebenarnya.", "Jangan ceramahi aku terlalu panjang.", "Aku akan makan setelah ini.")),
            ("Rindu ringan", ("Hari ini kita jarang bicara.", "Aku sempat ingin mengirim pesan lebih dulu.", "Tapi aku pikir kamu mungkin sibuk.", "Sekarang aku sudah di sini.", "Temani aku sebentar sebelum tidur.")),
            ("Salah paham kecil", ("Tadi jawabanmu terdengar agak dingin.", "Mungkin aku saja yang salah menangkapnya.", "Aku tidak marah, cuma sedikit terganggu.", "Aku lebih suka kalau kamu mengatakannya terus terang.", "Baik, sekarang aku mengerti.")),
        ),
    },
    "playful": {
        "label": "Bercanda dan menggoda",
        "dimensions": {
            "teasing": ("godaan tajam tetapi hangat", "godaan ringan dan manis"),
            "initiative": ("memimpin banter", "menunggu dan membalas momentum"),
            "repair": ("langsung berhenti saat nada serius", "melunakkan godaan menjadi perhatian"),
        },
        "scenes": (
            ("Pamer kemenangan", ("Aku menang tiga kali berturut-turut.", "Jelas ini bukan keberuntungan.", "Kamu boleh mengakui aku hebat sekarang.", "Kenapa, tidak percaya?", "Sudah, jangan terlalu memujiku juga.")),
            ("Ketahuan menunda", ("Aku belum mengerjakan yang tadi.", "Bukan malas, cuma... menunggu waktu tepat.", "Jangan menatapku seperti itu.", "Baik, alasanku memang lemah.", "Aku mulai lima menit lagi. Serius.")),
            ("Godaan berubah serius", ("Hari ini aku kelihatan keren, kan?", "Jawabanmu terlalu cepat. Mencurigakan.", "Coba goda aku kalau berani.", "Eh, cukup. Aku sedang tidak ingin digoda lagi.", "Nah, sekarang bicara biasa saja.")),
        ),
    },
    "length": {
        "label": "Panjang jawaban",
        "dimensions": {
            "casual_length": ("satu respons pendek yang selesai", "dua sampai tiga kalimat bernuansa"),
            "support_length": ("ringkas dan fokus", "cukup dalam tanpa menjadi esai"),
            "analysis_length": ("inti keputusan lebih dulu", "alasan terstruktur setelah inti"),
        },
        "scenes": (
            ("Pesan singkat", ("Hai.", "Lagi apa?", "Aku cuma mampir sebentar.", "Hari ini lumayan biasa.", "Nanti aku kembali lagi.")),
            ("Butuh pendapat", ("Menurutmu tampilan sederhana lebih bagus?", "Aku suka yang bersih, tapi fitur tetap harus terlihat.", "Kalau terlalu minimal malah membingungkan.", "Jadi prioritasnya harus jelas.", "Pilih satu arah yang paling masuk akal.")),
            ("Curhat bertahap", ("Ada hal yang menggangguku.", "Awalnya kecil, lalu terus kupikirkan.", "Aku tahu belum tentu seburuk itu.", "Aku hanya perlu melihatnya dengan jernih.", "Katakan yang penting saja, tapi jangan terlalu dingin.")),
        ),
    },
    "language": {
        "label": "Bahasa dan kosakata",
        "dimensions": {
            "register": ("Indonesia santai sehari-hari", "Indonesia rapi tetapi tidak formal"),
            "mixing": ("bahasa Indonesia konsisten", "campuran istilah asing yang sangat alami"),
            "expression": ("ungkapan ekspresif dan personal", "pilihan kata sederhana dan bersih"),
        },
        "scenes": (
            ("Obrolan kasual", ("Kayaknya hari ini bakal panjang.", "Mood-ku belum sepenuhnya ikut bangun.", "Tapi ya sudah, jalanin dulu.", "Kalau lancar mungkin sore sudah selesai.", "Semoga tidak ada drama tambahan.")),
            ("Bahas desain", ("Layout ini clean, tapi hierarchy-nya kurang terasa.", "Aku tidak masalah dengan istilah teknis.", "Asal jangan campur bahasa cuma supaya terdengar keren.", "Jelaskan seperti teman yang memang paham.", "Nah, gaya seperti itu lebih enak.")),
            ("Momen hangat", ("Makasih sudah menemaniku tadi.", "Aku tidak butuh kalimat yang terlalu puitis.", "Yang sederhana justru lebih terasa jujur.", "Tapi jangan sampai terdengar datar juga.", "Cukup katakan dengan caramu sendiri.")),
        ),
    },
}


def _blank_state() -> dict:
    return {"schema": SCHEMA_VERSION, "counts": {}, "decisions": [], "updated_at": 0.0}


def load_training_state(path: Path = TRAINING_PATH) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _blank_state()
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_VERSION:
        return _blank_state()
    counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    decisions = raw.get("decisions") if isinstance(raw.get("decisions"), list) else []
    return {"schema": SCHEMA_VERSION, "counts": counts, "decisions": decisions[-MAX_DECISIONS:], "updated_at": float(raw.get("updated_at") or 0.0)}


def save_training_state(state: dict, path: Path = TRAINING_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["schema"] = SCHEMA_VERSION
    payload["decisions"] = list(payload.get("decisions") or [])[-MAX_DECISIONS:]
    payload["updated_at"] = time.time()
    fd, temp_name = tempfile.mkstemp(prefix=".training-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass


def _extract_pair(text: str) -> tuple[str, str]:
    clean = str(text or "").strip()
    candidates = [clean]
    match = re.search(r"\{[\s\S]*\}", clean)
    if match: candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            a, b = str(data.get("a") or "").strip(), str(data.get("b") or "").strip()
            if a and b and a != b: return a[:1200], b[:1200]
        except (ValueError, TypeError, AttributeError):
            pass
    match = re.search(r"(?:^|\n)\s*A[.) :]\s*(.+?)(?:\n\s*B[.) :]\s*)(.+)$", clean, re.I | re.S)
    if match:
        a, b = match.group(1).strip(), match.group(2).strip()
        if a and b and a != b: return a[:1200], b[:1200]
    raise ValueError("Model tidak menghasilkan dua respons yang dapat dibandingkan.")


def _identity_context() -> str:
    try:
        from .hub_settings import load_hub_settings
        from .personality import synthesize_trait_profile_120
        settings = load_hub_settings()
        profile = synthesize_trait_profile_120(settings.get("personality_traits") or [])
        labels = ", ".join(profile.get("labels") or []) or "tanpa sifat tambahan"
        partner = "aktif" if settings.get("partner_mode") else "nonaktif"
        return f"Sifat gabungan: {labels}. Mode pasangan: {partner}."
    except Exception:
        return "Pertahankan identitas dan kepribadian Furina yang sedang aktif."


@dataclass
class TrainingPair:
    category_id: str
    scene_index: int
    turn_index: int
    scene_title: str
    user_text: str
    dimension: str
    pole_a: str
    pole_b: str
    response_a: str
    response_b: str
    reroll: int


class TrainingSession:
    """Preference sandbox. It intentionally has no MemoryStore dependency."""

    def __init__(self, category_id: str, llm, *, state_path: Path = TRAINING_PATH, seed: str | None = None):
        if category_id not in CATEGORIES: raise ValueError("Kategori Training Room tidak dikenal.")
        self.category_id = category_id
        self.category = CATEGORIES[category_id]
        self.llm = llm
        self.state_path = state_path
        self.seed = seed or secrets.token_hex(8)
        self.scene_index = 0
        self.turn_index = 0
        self.reroll_count = 0
        self.session_choices = []
        self.transcript = []
        self.current: TrainingPair | None = None

    def _turn(self):
        title, turns = self.category["scenes"][self.scene_index % len(self.category["scenes"])]
        text = turns[self.turn_index % len(turns)]
        dimensions = tuple(self.category["dimensions"])
        dimension = dimensions[(self.turn_index + self.scene_index) % len(dimensions)]
        poles = self.category["dimensions"][dimension]
        flip_key = f"{self.seed}:{self.scene_index}:{self.turn_index}:{self.reroll_count}".encode()
        flip = hashlib.blake2s(flip_key, digest_size=1).digest()[0] & 1
        pole_a, pole_b = (poles[1], poles[0]) if flip else poles
        return title, turns, text, dimension, pole_a, pole_b

    def generate(self) -> TrainingPair:
        title, turns, user_text, dimension, pole_a, pole_b = self._turn()
        prior = "\n".join(f"User simulasi: {u}\nFurina terpilih: {a}" for u, a in self.transcript[-3:]) or "(awal alur)"
        system = (
            "Kamu membuat dua kandidat jawaban Furina untuk TRAINING SANDBOX. User di bawah fiktif: jangan anggap sebagai user nyata, "
            "jangan ekstrak fakta/memori, dan jangan menyebut sistem latihan. Kedua jawaban harus sama-sama masuk akal, natural, "
            "sesuai identitas aktif, dan hanya berbeda terutama pada satu preferensi. Jangan buat satu opsi sengaja buruk atau generik. "
            "Balas JSON valid saja: {\"a\":\"...\",\"b\":\"...\"}."
        )
        prompt = (
            f"Materi: {self.category['label']}\nSkenario: {title}\n{_identity_context()}\n"
            f"Riwayat simulasi:\n{prior}\n\nPesan user simulasi sekarang: {user_text}\n"
            f"Respons A memakai kecenderungan: {pole_a}.\nRespons B memakai kecenderungan: {pole_b}.\n"
            "Pertahankan isi pokok dan kualitas keduanya agar pilihan benar-benar mencerminkan selera gaya."
        )
        raw = self.llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=360, temperature=.82, json_mode=True, role="training",
        )
        a, b = _extract_pair(raw)
        self.current = TrainingPair(self.category_id, self.scene_index, self.turn_index, title, user_text, dimension, pole_a, pole_b, a, b, self.reroll_count)
        return self.current

    def reroll(self) -> None:
        self.reroll_count += 1
        self.current = None

    def choose(self, choice: str) -> dict:
        if self.current is None: raise RuntimeError("Belum ada pasangan respons.")
        key = str(choice).strip().lower()
        if key not in {"a", "b"}: raise ValueError("Pilihan harus A atau B.")
        pair = self.current
        chosen_pole = pair.pole_a if key == "a" else pair.pole_b
        rejected_pole = pair.pole_b if key == "a" else pair.pole_a
        chosen_text = pair.response_a if key == "a" else pair.response_b
        rejected_text = pair.response_b if key == "a" else pair.response_a
        state = load_training_state(self.state_path)
        category_counts = state["counts"].setdefault(pair.category_id, {})
        dimension_counts = category_counts.setdefault(pair.dimension, {})
        dimension_counts[chosen_pole] = int(dimension_counts.get(chosen_pole, 0)) + 1
        state["decisions"].append({
            "category": pair.category_id, "scene": pair.scene_title, "turn": pair.turn_index,
            "dimension": pair.dimension, "chosen_pole": chosen_pole, "rejected_pole": rejected_pole,
            "simulated_user": pair.user_text, "chosen": chosen_text, "rejected": rejected_text,
            "created_at": int(time.time()),
        })
        save_training_state(state, self.state_path)
        self.session_choices.append(chosen_pole)
        self.transcript.append((pair.user_text, chosen_text))
        _, turns = self.category["scenes"][self.scene_index % len(self.category["scenes"])]
        self.turn_index += 1
        if self.turn_index >= len(turns):
            self.scene_index = (self.scene_index + 1) % len(self.category["scenes"])
            self.turn_index = 0
            self.transcript = []
        self.reroll_count = 0
        self.current = None
        return {"chosen_pole": chosen_pole, "count": len(self.session_choices)}

    def summary(self) -> dict:
        return {"category": self.category["label"], "choices": len(self.session_choices), "recent": self.session_choices[-3:]}


def training_progress(path: Path = TRAINING_PATH) -> dict:
    state = load_training_state(path)
    total = len(state["decisions"])
    by_category = {category_id: sum(sum(int(v) for v in poles.values()) for poles in dims.values()) for category_id, dims in state["counts"].items() if isinstance(dims, dict)}
    return {"total": total, "by_category": by_category, "updated_at": state["updated_at"]}


def runtime_preference_contract(path: Path = TRAINING_PATH, *, max_rules: int = 6) -> str:
    state = load_training_state(path)
    ranked = []
    for category_id, dimensions in state["counts"].items():
        category = CATEGORIES.get(category_id)
        if not category or not isinstance(dimensions, dict): continue
        for dimension, poles in dimensions.items():
            if not isinstance(poles, dict) or not poles: continue
            ordered = sorted(((int(count), str(pole)) for pole, count in poles.items()), reverse=True)
            best_count, best_pole = ordered[0]
            other = sum(count for count, _ in ordered[1:])
            total = best_count + other
            margin = best_count - (ordered[1][0] if len(ordered) > 1 else 0)
            if total and margin > 0:
                ranked.append((min(total, 8) + margin, category["label"], dimension, best_pole, total, best_count / total))
    if not ranked: return ""
    lines = ["[PREFERENSI TRAINING ROOM — POLA ABSTRAK, BUKAN MEMORI/PENGALAMAN USER]"]
    for _, label, dimension, pole, total, ratio in sorted(ranked, reverse=True)[:max_rules]:
        confidence = "stabil" if total >= 5 and ratio >= .67 else "berkembang" if total >= 2 else "awal"
        lines.append(f"- {label}/{dimension}: condong ke {pole} ({confidence}; {total} pilihan). Terapkan bila konteks cocok, bukan sebagai aturan mutlak.")
    lines.append("Jangan menyebut Training Room, skor, skenario, atau pilihan A/B kepada user.")
    return "\n".join(lines)


def read_training_key() -> str:
    try:
        import sys, termios, tty
        if not sys.stdin.isatty(): return input("A/B/R/ESC › ").strip().lower()
        fd = sys.stdin.fileno(); previous = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char == "\x1b": return "esc"
            return char.casefold()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)
    except (OSError, EOFError):
        return "esc"
