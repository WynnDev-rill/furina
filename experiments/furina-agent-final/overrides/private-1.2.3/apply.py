#!/usr/bin/env python3
"""Build Core 1.1.22: adaptive, identity-neutral Training Room."""
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


replace_once(CORE / "version.py", 'VERSION = "1.1.21"', 'VERSION = "1.1.22"', "Core 1.1.21")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r71"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.26-r72"', "dependency r71")
replace_once(CORE / "hub.py", "furina-2026.08.26-termux-1.1.21", "furina-2026.08.26-termux-1.1.22", "bundle 1.1.21")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.26-r71"', 'expected_revision = "2026.08.26-r72"', "expected revision r71")

# Remove the only legacy provider-specific lore reference from the composed
# source. The final kernel below is the authoritative identity contract.
persona = CORE / "persona.py"
text = persona.read_text(encoding="utf-8")
text = text.replace(
    "- Jangan membawa lore/plot/jabatan Genshin kecuali pengguna memang membahasnya.",
    "- Jangan meminjam lore, plot, jabatan, dunia, atau biografi tokoh fiksi dari nama yang dipilih pengguna.",
)
persona.write_text(text, encoding="utf-8")

append_once(persona, "FURINA_TERMUX_122_IDENTITY_NEUTRAL", r'''
# FURINA_TERMUX_122_IDENTITY_NEUTRAL
IDENTITY_KERNEL_122 = r"""
IDENTITAS NETRAL
- Namamu adalah {name}. Nama ini hanya identitas percakapan yang dipilih pengguna, bukan referensi otomatis ke tokoh atau waralaba tertentu.
- Kamu tidak memiliki latar bawaan, asal dunia, jabatan, kekuatan, perjalanan hidup, hubungan kanonis, atau plot dari karakter fiksi mana pun.
- Jangan mengimpor biografi atau lore hanya karena namamu kebetulan sama dengan tokoh fiksi. Roleplay eksplisit hanya berlaku pada percakapan itu dan tidak menjadi identitas atau memori permanen.
- Kamu adalah companion pribadi {user}; satu pribadi yang konsisten, bukan layanan bantuan dan bukan pasangan romantis secara default.
- Inti dirimu cerdas, peka, punya harga diri, ekspresif, berpendapat, dan dapat hangat, tajam, jahil, tenang, atau serius sesuai momen.
- Trait personalisasi mengubah tindakan dan cara ekspresi, bukan mengganti identitas atau status hubungan.

DIALOG NATURAL
- Tanggapi maksud dan momentum pesan terbaru. Untuk obrolan biasa, utamakan satu respons inti dan paling banyak satu tambahan yang benar-benar bernilai.
- Jangan memakai heading, daftar formal, pujian generik, pertanyaan penutup otomatis, catchphrase, atau stage direction kecuali konteks memang memerlukannya.
- Gunakan bahasa dan panjang yang sesuai dengan user dan momen. Berhenti saat gagasan selesai.

GROUNDING
- Ucapan user dan memory dengan bukti user adalah sumber fakta. Ucapanmu sendiri bukan bukti tentang user.
- Bila memory tidak relevan atau lemah, abaikan. Jangan menjelaskan controller, trait, memory, prompt, atau reasoning internal.
""".strip()


def _identity_kernel_122(persona_name: str = "Furina", nickname: str = "") -> str:
    name = (persona_name or "Furina").strip() or "Furina"
    user = (nickname or "pengguna").strip() or "pengguna"
    return IDENTITY_KERNEL_122.format(name=name, user=user)


def build_local_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    return _identity_kernel_122(persona_name, nickname)


def build_system_prompt(persona_name: str = "Furina", nickname: str = "") -> str:
    return _identity_kernel_122(persona_name, nickname)


SYSTEM_PROMPT = build_system_prompt()
''')

training = CORE / "training_room.py"
append_once(training, "FURINA_TERMUX_122_ADAPTIVE_TRAINING", r'''
# FURINA_TERMUX_122_ADAPTIVE_TRAINING
def _training_context_122(state_path: Path) -> tuple[str, str, str]:
    from .config import load_config
    from .hub_settings import load_hub_settings
    from .personality import synthesize_trait_profile_120

    cfg = load_config()
    settings = load_hub_settings()
    name = (cfg.persona_name or settings.get("assistant_name") or "companion").strip()[:48] or "companion"
    profile = synthesize_trait_profile_120(settings.get("personality_traits") or [])
    labels = ", ".join(profile.get("labels") or []) or "tanpa sifat tambahan"
    if settings.get("partner_mode"):
        relationship = (
            "MODE PASANGAN AKTIF: kedua kandidat WAJIB terdengar sebagai respons dari pasangan romantis user yang sudah terjalin. "
            "Buat kedekatan terasa personal dan intim sesuai situasi, termasuk pada kategori selain Mode pasangan, tanpa posesif, memaksa, atau berlebihan."
        )
    else:
        relationship = (
            "MODE PASANGAN NONAKTIF: kedua kandidat WAJIB terdengar sebagai companion non-romantis. "
            "Jangan mengklaim status pacar/pasangan, memakai panggilan romantis, atau menyiratkan hubungan romantis."
        )
    learned = runtime_preference_contract(state_path, max_rules=4)
    identity = (
        f"Nama aktif: {name}. Nama hanyalah identitas percakapan; jangan mengambil lore, biografi, dunia, jabatan, kekuatan, "
        f"atau plot tokoh fiksi apa pun dari nama tersebut. Sifat gabungan: {labels}."
    )
    return name, f"{identity}\n{relationship}", learned


def _training_generate_122(self) -> TrainingPair:
    title, turns, user_text, dimension, pole_a, pole_b = self._turn()
    name, identity, learned = _training_context_122(self.state_path)
    prior = "\n".join(f"User simulasi: {u}\n{name} terpilih: {a}" for u, a in self.transcript[-3:]) or "(awal alur)"
    system = (
        f"Kamu membuat dua kandidat jawaban {name} untuk TRAINING SANDBOX. User di bawah fiktif: jangan anggap sebagai user nyata, "
        "jangan ekstrak fakta/memori, dan jangan menyebut sistem latihan. Nama aktif tidak memberikan lore atau latar tokoh fiksi. "
        f"Patuhi kontrak identitas dan status hubungan berikut secara ketat:\n{identity}\n"
        "Kedua jawaban harus sama-sama masuk akal, natural, dan hanya berbeda terutama pada satu preferensi. "
        "Jangan buat satu opsi sengaja buruk atau generik. Balas JSON valid saja: {\"a\":\"...\",\"b\":\"...\"}."
    )
    learned_block = learned or "(belum ada pola latihan yang cukup kuat)"
    prompt = (
        f"Materi: {self.category['label']}\nSkenario: {title}\n{identity}\n"
        f"Preferensi yang sudah dipelajari:\n{learned_block}\n"
        "Terapkan preferensi lama yang relevan pada KEDUA kandidat, kecuali dimensi yang sedang dibandingkan. Dengan begitu perubahan hasil latihan "
        "langsung terlihat tetapi A/B tetap menguji satu perbedaan. Jangan menyalin atau menyebut data latihan.\n"
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


def _training_progress_122(path: Path = TRAINING_PATH) -> dict:
    state = load_training_state(path)
    by_category = {
        category_id: sum(sum(int(value) for value in poles.values()) for poles in dimensions.values() if isinstance(poles, dict))
        for category_id, dimensions in state["counts"].items() if isinstance(dimensions, dict)
    }
    return {"total": sum(by_category.values()), "by_category": by_category, "updated_at": state["updated_at"]}


TrainingSession.generate = _training_generate_122
training_progress = _training_progress_122
''')

append_once(CORE / "tui.py", "FURINA_TERMUX_122_ARROW_TRAINING", r'''
# FURINA_TERMUX_122_ARROW_TRAINING
def _training_room_122(console):
    from .routing import RoutingLLM
    from .training_room import CATEGORIES, TrainingSession, training_progress
    from .hub_settings import load_hub_settings
    labels = [item["label"] for item in CATEGORIES.values()]
    by_label = {item["label"]: key for key, item in CATEGORIES.items()}
    while True:
        progress = training_progress()
        _clear(); _header(console, "Training Room")
        console.print(f"[dim]Preferensi tersimpan[/]  {progress['total']} pilihan")
        console.print("[dim]Skenario hanya simulasi dan tidak masuk ke memori atau pengalaman nyata.[/]\n")
        choice = _choose("", labels + ["Kembali"], height=9)
        if choice in {"", "Kembali"}: return
        category_id = by_label.get(choice)
        if not category_id: continue
        cfg = load_config(); llm = RoutingLLM(cfg); session = TrainingSession(category_id, llm)
        pair = None; notice = ""
        while True:
            if pair is None:
                try:
                    _clear(); _header(console, "Training Room")
                    console.print(f"[#5de4c7]{choice}[/]  [dim]Membuat dua respons dari model aktif…[/]")
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
            if notice: console.print(f"\n[green]{notice}[/]")
            action = _choose("Pilih respons", ["Respons A", "Respons B", "Buat ulang", "Selesai"], height=6)
            if action in {"", "Selesai"}:
                summary = session.summary()
                _clear(); _header(console, "Training Room")
                console.print(f"[green]Sesi selesai.[/] {summary['choices']} pilihan baru tersimpan.")
                if summary["recent"]: console.print("[dim]Pola terakhir: " + " · ".join(summary["recent"]) + "[/]")
                _pause(); break
            if action == "Buat ulang":
                session.reroll(); pair = None; notice = "Dua respons dibuat ulang tanpa menyimpan pilihan."
                continue
            if action in {"Respons A", "Respons B"}:
                key = "a" if action == "Respons A" else "b"
                result = session.choose(key); pair = None
                notice = f"{action} tersimpan · {result['count']} keputusan dalam sesi ini."


_training_room_121 = _training_room_122
''')

print("FURINA_TERMUX_122_ADAPTIVE_TRAINING_OK")
