from __future__ import annotations


def install_tui_v128(ns: dict) -> None:
    clear, header, choose = (ns[x] for x in ("_clear", "_header", "_choose"))
    confirm = ns["_confirm"]
    training_room = ns["_training_room_125"]

    def advanced(console):
        from .hub_settings import load_hub_settings, save_hub_settings
        from .training_room import training_progress

        while True:
            state = load_hub_settings()
            progress = training_progress()
            labels = {
                "training": f"Training Room · {progress['total']} pilihan",
                "suggestions": f"Saran latihan di chat · {'Aktif' if state.get('training_suggestions') else 'Nonaktif'}",
                "partner": f"Mode pasangan · {'Aktif' if state.get('partner_mode') else 'Nonaktif'}",
                "roleplay": f"RolePlay · {'Aktif' if state.get('roleplay_mode') else 'Nonaktif'}",
                "thoughts": f"Pikiran dalam hati · {'Aktif' if state.get('inner_thoughts') else 'Nonaktif'}",
                "memory": f"Memori penuh lokal · {'Aktif' if state.get('full_local_memory') else 'Nonaktif'}",
            }
            clear(); header(console, "Lanjutan")
            choice = choose("", list(labels.values()) + ["Kembali"], height=10)
            if choice in {"", "Kembali"}:
                return
            if choice == labels["training"]:
                training_room(console)
                continue
            key = next((key for key, label in labels.items() if label == choice), "")
            if key == "suggestions":
                state["training_suggestions"] = not bool(state.get("training_suggestions"))
            elif key == "partner":
                state["partner_mode"] = not bool(state.get("partner_mode"))
            elif key == "roleplay":
                state["roleplay_mode"] = not bool(state.get("roleplay_mode"))
            elif key == "thoughts":
                state["inner_thoughts"] = not bool(state.get("inner_thoughts"))
            elif key == "memory":
                if not state.get("full_local_memory") and not confirm(
                    "Semua teks percakapan baru akan diarsipkan lokal. Aktifkan?", default=False
                ):
                    continue
                state["full_local_memory"] = not bool(state.get("full_local_memory"))
            else:
                continue
            save_hub_settings(state)

    def settings(console):
        from .hub_settings import load_hub_settings

        while True:
            cfg = ns["load_config"]()
            state = load_hub_settings()
            active_count = len(state.get("personality_traits") or [])
            clear(); header(console, "Pengaturan")
            console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
            console.print(f"[dim]Personalisasi[/] {active_count}/20 sifat aktif")
            console.print(
                f"[dim]Lanjutan[/]      Pasangan {'aktif' if state.get('partner_mode') else 'nonaktif'} · "
                f"RolePlay {'aktif' if state.get('roleplay_mode') else 'nonaktif'} · "
                f"Batin {'aktif' if state.get('inner_thoughts') else 'nonaktif'}\n"
            )
            choice = choose("", ["Identitas", "Sistem", "Lanjutan", "Backup", "Update & Recovery", "Kembali"], height=8)
            if choice in {"", "Kembali"}:
                return
            if choice == "Identitas":
                ns["_private_identity"](console)
            elif choice == "Sistem":
                ns["_system"](console)
            elif choice == "Lanjutan":
                advanced(console)
            elif choice == "Backup":
                ns["_lite_backup"](console)
            elif choice == "Update & Recovery":
                ns["_update_repair"](console)

    ns["_advanced_settings_128"] = advanced
    ns["_advanced_settings_125"] = advanced
    ns["_advanced_settings_121"] = advanced
    ns["_advanced_settings_119"] = advanced
    ns["_settings"] = settings
