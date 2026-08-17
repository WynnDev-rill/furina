#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC51 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    hub_path = root / "core/furina_agent/hub.py"
    version_path = root / "core/furina_agent/version.py"
    for path in (hub_path, version_path):
        if not path.is_file():
            raise SystemExit(f"RC51 source missing: {path}")

    hub = hub_path.read_text(encoding="utf-8")

    old_vision_prompt = '''                vision_prompt = (
                    "Buat CATATAN VISUAL faktual untuk model companion, bukan jawaban final kepada pengguna. "
                    "Identifikasi objek, teks yang benar-benar terbaca, hubungan spasial, suasana, dan detail yang relevan dengan pertanyaan. "
                    "Tandai ketidakpastian secara eksplisit. Jangan mengarang nama orang, tempat, aplikasi, gim, atau tulisan. "
                    "Tulis ringkas dalam bahasa Indonesia.\\n\\n"
                    f"Pertanyaan pengguna: {prompt}"
                )
'''
    new_vision_prompt = '''                vision_prompt = (
                    "Buat CATATAN VISUAL INTERNAL yang ringkas untuk model companion. Ini BUKAN jawaban untuk pengguna. "
                    "Catat hanya fakta visual yang diperlukan untuk menjawab pertanyaan: objek utama, teks yang benar-benar terbaca, "
                    "hubungan penting, serta ketidakpastian. Jangan membuat paragraf deskriptif panjang dan jangan mengarang identitas, "
                    "tempat, aplikasi, gim, atau tulisan. Maksimal 6 butir singkat dalam bahasa Indonesia.\\n\\n"
                    f"Pertanyaan pengguna: {prompt}"
                )
'''
    hub = replace_once(hub, old_vision_prompt, new_vision_prompt, "compact internal vision notes")

    old_companion = '''                companion_input = (
                    f"{prompt}\\n\\n"
                    "[Konteks visual internal — gunakan sebagai pengamatanmu sendiri, jangan menyebut bahwa ini laporan model vision]\\n"
                    f"{visual_facts}\\n"
                    "[Akhir konteks visual]\\n\\n"
                    "Jawab pertanyaan pengguna secara natural sebagai dirimu sendiri. Pertahankan persona, hubungan, memori, "
                    "gaya bahasa, dan personalisasi yang biasa dipakai dalam percakapan. Jangan berubah menjadi laporan deskripsi gambar "
                    "kecuali pengguna memang meminta deskripsi rinci."
                )
'''
    new_companion = '''                companion_input = (
                    f"{prompt}\\n\\n"
                    "[PENGAMATAN VISUAL INTERNAL — jangan pernah tampilkan, kutip, rangkum, atau jelaskan bagian ini kepada pengguna]\\n"
                    f"{visual_facts}\\n"
                    "[AKHIR PENGAMATAN INTERNAL]\\n\\n"
                    "Berikan SATU jawaban final sebagai companion, bukan dua lapis jawaban. Jawab hanya yang ditanyakan pengguna dengan "
                    "gaya Furina/personalisasi normal. Catatan visual di atas hanya bukti internal. Jangan mengawali dengan laporan teknis, "
                    "inventaris objek, atau deskripsi panjang. Untuk pertanyaan identifikasi sederhana seperti 'gambar apa ini?', jawab "
                    "langsung dan singkat (umumnya 1-3 kalimat) kecuali pengguna meminta detail."
                )
'''
    hub = replace_once(hub, old_companion, new_companion, "single natural image answer")
    hub = replace_once(
        hub,
        '"bridge_target": "1.0.0-rc34"',
        '"bridge_target": "1.0.0-rc35"',
        "bridge target",
    )
    hub_path.write_text(hub, encoding="utf-8")

    version = version_path.read_text(encoding="utf-8")
    version = replace_once(version, 'VERSION = "1.0.0-rc50"', 'VERSION = "1.0.0-rc51"', "Core version")
    version_path.write_text(version, encoding="utf-8")

    combined = hub + "\\n" + version
    checks = (
        'VERSION = "1.0.0-rc51"',
        '"bridge_target": "1.0.0-rc35"',
        "CATATAN VISUAL INTERNAL",
        "Maksimal 6 butir singkat",
        "Berikan SATU jawaban final sebagai companion",
        "jangan pernah tampilkan, kutip, rangkum, atau jelaskan",
        "umumnya 1-3 kalimat",
        "self.session.chat.respond(companion_input)",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC51 marker hilang: {missing}")
    print("FURINAHUB_CORE_RC51_IMAGE_ANSWER_OK")


if __name__ == "__main__":
    main()
