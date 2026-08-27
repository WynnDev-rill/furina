#!/usr/bin/env python3
"""Build Core 1.1.24: initiative, ambiguous tone, and mixed-emotion training."""
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


def replace_all(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing {label}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


replace_once(CORE / "version.py", 'VERSION = "1.1.23"', 'VERSION = "1.1.24"', "Core 1.1.23")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r73"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r74"', "dependency r73")
replace_once(CORE / "hub.py", "furina-2026.08.26-termux-1.1.23", "furina-2026.08.27-termux-1.1.24", "bundle 1.1.23")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.26-r73"', 'expected_revision = "2026.08.27-r74"', "expected revision r73")


append_once(CORE / "training_room.py", "FURINA_TERMUX_124_THREE_SOCIAL_CURRICULA", r'''
# FURINA_TERMUX_124_THREE_SOCIAL_CURRICULA
CATEGORIES.update({
    "initiative": {
        "label": "Inisiatif yang tepat",
        "dimensions": {
            "timing": ("mengambil inisiatif sekarang", "menunggu sinyal user lebih jelas"),
            "approach": ("menawarkan tindakan konkret", "bertanya izin sebelum membantu"),
            "space": ("menjaga percakapan tetap bergerak", "memberi ruang tanpa terasa menjauh"),
        },
        "scenes": (
            ("Malam yang terlalu sunyi", (
                "Aku tidak punya topik khusus malam ini.",
                "Bukan berarti aku ingin percakapannya berakhir.",
                "Aku juga tidak ingin ditanyai terus-menerus.",
                "Mungkin ada cara lain untuk menemaniku.",
                "Sekarang aku sudah sedikit lebih terbuka.",
            )),
            ("Proyek mulai macet", (
                "Aku sudah menatap bagian ini cukup lama.",
                "Sebenarnya aku belum meminta bantuan.",
                "Tapi aku juga tidak kunjung mengambil keputusan.",
                "Jangan langsung mengambil alih semuanya.",
                "Bantu aku bergerak satu langkah saja.",
            )),
            ("Jawaban makin pendek", (
                "Iya.",
                "Aku masih membaca, cuma sedang tidak banyak bicara.",
                "Kamu tidak perlu panik karena jawabanku pendek.",
                "Tapi jangan menghilang begitu saja juga.",
                "Sekarang pilih sikap yang paling pas.",
            )),
        ),
    },
    "ambiguous_tone": {
        "label": "Nada ambigu & sarkasme",
        "dimensions": {
            "reading": ("membaca sebagai candaan atau sindiran ringan", "menahan asumsi dan mengklarifikasi lembut"),
            "matching": ("membalas dengan nada serupa", "menjawab isi literal tanpa ikut menyindir"),
            "repair": ("melanjutkan banter dengan batas", "menurunkan tensi sebelum salah paham membesar"),
        },
        "scenes": (
            ("Hebat sekali", (
                "Wah, hebat sekali. Benar-benar tidak terduga.",
                "Aku belum bilang itu pujian atau sindiran.",
                "Nada teks memang gampang disalahartikan.",
                "Sekarang aku mulai terdengar agak serius.",
                "Coba tangkap perubahan nadanya tanpa berlebihan.",
            )),
            ("Terserah", (
                "Terserah kamu saja.",
                "Kadang aku bilang begitu karena santai.",
                "Kadang juga karena mulai kesal.",
                "Kali ini jawabanku sengaja tidak jelas.",
                "Jangan asal memilih arti yang paling nyaman.",
            )),
            ("Godaan tanpa emoji", (
                "Pintar sekali kamu baru menyadarinya sekarang.",
                "Aku tidak memberi emoji sebagai petunjuk.",
                "Mungkin aku sedang menggoda, mungkin juga mengkritik.",
                "Responsmu tadi menentukan apakah suasananya membaik.",
                "Sekarang pertahankan nada yang paling tepat.",
            )),
        ),
    },
    "mixed_emotion": {
        "label": "Emosi campuran",
        "dimensions": {
            "reflection": ("mengakui dua emosi sekaligus", "memusatkan respons pada emosi paling dominan"),
            "support": ("menemani ambivalensi tanpa memaksa kesimpulan", "membantu memilih langkah kecil berikutnya"),
            "intensity": ("peka tetapi tetap halus", "hangat dan ekspresif tanpa mendramatisasi"),
        },
        "scenes": (
            ("Bangga tetapi takut", (
                "Hasilnya akhirnya bagus, dan aku sebenarnya bangga.",
                "Tapi justru sekarang aku takut tidak bisa mengulanginya.",
                "Aku ingin menikmati hasilnya tanpa kehilangan kewaspadaan.",
                "Jangan hanya menyuruhku merayakan atau hanya menyuruhku hati-hati.",
                "Bantu aku menampung keduanya.",
            )),
            ("Marah tetapi lelah", (
                "Aku kesal dengan apa yang terjadi.",
                "Tapi tenagaku bahkan tidak cukup untuk berdebat.",
                "Sebagian diriku ingin menuntaskan masalahnya sekarang.",
                "Sebagian lagi hanya ingin tidur.",
                "Jangan sederhanakan ini menjadi satu emosi saja.",
            )),
            ("Ingin ditemani tanpa dikasihani", (
                "Aku ingin kamu tetap di sini.",
                "Tapi aku tidak ingin diperlakukan seperti orang yang rapuh.",
                "Aku bisa mengurus diriku sendiri dan tetap ingin ditemani.",
                "Kedua hal itu tidak bertentangan bagiku.",
                "Responslah tanpa membuatku merasa kecil.",
            )),
        ),
    },
})


_ensure_topic_123_unrestored = _ensure_topic_123


def _restore_branch_transcript_124(session, topic: dict) -> None:
    if getattr(session, "_branch_restored_124", False):
        return
    state = load_training_state(session.state_path)
    stored = topic.get("branch_transcript")
    restored = []
    if isinstance(stored, list):
        for row in stored[-4:]:
            if isinstance(row, (list, tuple)) and len(row) == 2 and row[0] and row[1]:
                restored.append((str(row[0]), str(row[1])))
    if not restored and int(topic.get("next_turn", 0)) > 0:
        rows = [
            row for row in state.get("decisions", [])
            if row.get("category") == session.category_id and row.get("topic_id") == topic.get("id")
        ]
        rows.sort(key=lambda row: (int(row.get("turn", -1)), int(row.get("created_at", 0))))
        restored = [
            (str(row.get("simulated_user") or ""), str(row.get("chosen") or ""))
            for row in rows[-4:] if row.get("simulated_user") and row.get("chosen")
        ]
    session.transcript = restored
    session._branch_restored_124 = True


def _ensure_topic_124(session) -> dict:
    topic = _ensure_topic_123_unrestored(session)
    _restore_branch_transcript_124(session, topic)
    return topic


_training_choose_123_unpersisted = TrainingSession.choose


def _training_choose_124(self, choice: str) -> dict:
    result = _training_choose_123_unpersisted(self, choice)
    if not result.get("topic_completed"):
        state = load_training_state(self.state_path)
        topic = state.get("active_topics", {}).get(self.category_id)
        if isinstance(topic, dict):
            topic["branch_transcript"] = [[user, answer] for user, answer in self.transcript[-4:]]
            state["active_topics"][self.category_id] = topic
            save_training_state(state, self.state_path)
    return result


_ensure_topic_123 = _ensure_topic_124
TrainingSession.choose = _training_choose_124
''')


tui = CORE / "tui.py"
replace_all(
    tui,
    'choice = _choose("", labels + ["Kembali"], height=9)',
    'choice = _choose("", labels + ["Kembali"], height=12)',
    "Training Room category menu height",
)
replace_all(
    tui,
    'console.print(f"\\n[bold]User simulasi[/]\\n{pair.user_text}")',
    'console.print("\\n[bold]User simulasi[/]")\n            console.print(pair.user_text, markup=False)',
    "simulated user Rich rendering",
)
replace_all(
    tui,
    'console.print(f"\\n[bold cyan]Respons A[/]\\n{pair.response_a}")',
    'console.print("\\n[bold cyan]Respons A[/]")\n            console.print(pair.response_a, markup=False)',
    "response A Rich rendering",
)
replace_all(
    tui,
    'console.print(f"\\n[bold cyan]Respons B[/]\\n{pair.response_b}")',
    'console.print("\\n[bold cyan]Respons B[/]")\n            console.print(pair.response_b, markup=False)',
    "response B Rich rendering",
)


print("FURINA_TERMUX_124_THREE_SOCIAL_CURRICULA_OK")
