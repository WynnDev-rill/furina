from __future__ import annotations

import re


def install_tui_v126(ns: dict) -> None:
    clear, header, choose, pause = (ns[x] for x in ("_clear", "_header", "_choose", "_pause"))
    input_text = ns["_input"]

    def builtins(console):
        from .hub_settings import PERSONALITY_TRAITS, load_hub_settings, save_hub_settings
        while True:
            state = load_hub_settings(); active = set(state.get("personality_traits") or [])
            labels = [("✓ " if row["id"] in active else "  ") + row["label"] for row in PERSONALITY_TRAITS]
            lookup = {label: row for label, row in zip(labels, PERSONALITY_TRAITS)}
            clear(); header(console, "Sifat bawaan")
            choice = choose(f"{len(active)} sifat aktif", labels + ["Kembali"], height=12)
            if choice in {"", "Kembali"}: return
            row = lookup.get(choice)
            if not row: continue
            if row["id"] in active: active.remove(row["id"])
            else: active.add(row["id"])
            state["personality_traits"] = [x["id"] for x in PERSONALITY_TRAITS if x["id"] in active]
            save_hub_settings(state)

    def custom(console):
        from .hub_settings import load_hub_settings, save_hub_settings
        while True:
            state = load_hub_settings(); rows = list(state.get("custom_personality_traits") or [])
            labels = [("✓ " if row.get("active", True) else "  ") + row["label"] for row in rows]
            lookup = {label: index for index, label in enumerate(labels)}
            clear(); header(console, "Sifat kustom")
            choice = choose("Tambahkan sebanyak yang diperlukan", ["Tambah sifat"] + labels + ["Kembali"], height=12)
            if choice in {"", "Kembali"}: return
            if choice == "Tambah sifat":
                label = re.sub(r"\s+", " ", input_text("Nama sifat › ").strip())[:48]
                description = re.sub(r"[\r\n\[\]{}]+", " ", input_text("Cara sifat ini terlihat › ").strip())
                description = re.sub(r"\s+", " ", description)[:240]
                if len(label) >= 2 and len(description) >= 3:
                    rows.append({"id": re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or f"custom-{len(rows)+1}", "label": label, "description": description, "active": True})
                    state["custom_personality_traits"] = rows; save_hub_settings(state)
                continue
            index = lookup.get(choice)
            if index is None: continue
            row = rows[index]
            clear(); header(console, row["label"]); console.print(row["description"], markup=False); console.print()
            action = choose("", ["Nonaktifkan" if row.get("active", True) else "Aktifkan", "Ubah deskripsi", "Hapus", "Kembali"], height=7)
            if action == "Hapus": rows.pop(index)
            elif action in {"Aktifkan", "Nonaktifkan"}: row["active"] = action == "Aktifkan"
            elif action == "Ubah deskripsi":
                value = re.sub(r"[\r\n\[\]{}]+", " ", input_text("Deskripsi › ", value=row["description"]).strip())
                row["description"] = re.sub(r"\s+", " ", value)[:240] or row["description"]
            else: continue
            state["custom_personality_traits"] = rows; save_hub_settings(state)

    def personalization(console):
        from .hub_settings import load_hub_settings
        while True:
            state = load_hub_settings(); built = len(state.get("personality_traits") or []); custom_count = len(state.get("custom_personality_traits") or [])
            clear(); header(console, "Personalisasi")
            choice = choose("Semua sifat aktif hidup bersama sebagai satu watak", [f"Sifat bawaan · {built} aktif", f"Sifat kustom · {custom_count}", "Kembali"], height=7)
            if choice in {"", "Kembali"}: return
            if choice.startswith("Sifat bawaan"): builtins(console)
            elif choice.startswith("Sifat kustom"): custom(console)

    def advanced(console):
        from .hub_settings import load_hub_settings, save_hub_settings
        from .training_room import training_progress
        training_room = ns["_training_room_125"]
        confirm = ns["_confirm"]
        while True:
            state = load_hub_settings(); progress = training_progress()
            labels = {
                "training": f"Training Room · {progress['total']} pilihan",
                "suggestions": f"Saran latihan di chat · {'Aktif' if state.get('training_suggestions') else 'Nonaktif'}",
                "partner": f"Mode pasangan · {'Aktif' if state.get('partner_mode') else 'Nonaktif'}",
                "roleplay": f"RolePlay · {'Aktif' if state.get('roleplay_mode') else 'Nonaktif'}",
                "memory": f"Memori penuh lokal · {'Aktif' if state.get('full_local_memory') else 'Nonaktif'}",
            }
            clear(); header(console, "Lanjutan")
            choice = choose("", list(labels.values()) + ["Kembali"], height=9)
            if choice in {"", "Kembali"}: return
            if choice == labels["training"]: training_room(console); continue
            key = next((key for key, label in labels.items() if label == choice), "")
            if key == "suggestions": state["training_suggestions"] = not bool(state.get("training_suggestions"))
            elif key == "partner": state["partner_mode"] = not bool(state.get("partner_mode"))
            elif key == "roleplay": state["roleplay_mode"] = not bool(state.get("roleplay_mode"))
            elif key == "memory":
                if not state.get("full_local_memory") and not confirm("Semua teks percakapan baru akan diarsipkan lokal. Aktifkan?", default=False): continue
                state["full_local_memory"] = not bool(state.get("full_local_memory"))
            else: continue
            save_hub_settings(state)

    def settings(console):
        from .hub_settings import load_hub_settings
        load_config = ns["load_config"]
        while True:
            cfg = load_config(); state = load_hub_settings()
            built_count = len(state.get("personality_traits") or [])
            custom_count = sum(1 for row in state.get("custom_personality_traits") or [] if row.get("active", True))
            clear(); header(console, "Pengaturan")
            console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
            console.print(f"[dim]Personalisasi[/] {built_count + custom_count} sifat aktif · {custom_count} kustom")
            console.print(
                f"[dim]Lanjutan[/]      Pasangan {'aktif' if state.get('partner_mode') else 'nonaktif'} · "
                f"RolePlay {'aktif' if state.get('roleplay_mode') else 'nonaktif'} · Memori penuh {'aktif' if state.get('full_local_memory') else 'nonaktif'}\n"
            )
            choice = choose("", ["Identitas", "Sistem", "Lanjutan", "Backup", "Update & Recovery", "Kembali"], height=8)
            if choice in {"", "Kembali"}: return
            if choice == "Identitas": ns["_private_identity"](console)
            elif choice == "Sistem": ns["_system"](console)
            elif choice == "Lanjutan": advanced(console)
            elif choice == "Backup": ns["_lite_backup"](console)
            elif choice == "Update & Recovery": ns["_update_repair"](console)

    ns["_private_personalization_117"] = personalization
    ns["_private_personalization_110"] = personalization
    ns["_advanced_settings_125"] = advanced
    ns["_advanced_settings_121"] = advanced
    ns["_advanced_settings_119"] = advanced
    ns["_settings"] = settings
