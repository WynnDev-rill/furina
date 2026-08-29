from __future__ import annotations


def install_tui_v127(ns: dict) -> None:
    # Restore the exact proven two-column selector for the original 20 traits.
    # Keep the 1.1.26 Advanced screen because RolePlay remains a supported
    # default-off setting; only the unintended custom-trait surface is removed.
    original_personality = ns.get("_private_personalization_116")
    if original_personality is None:
        raise RuntimeError("UI Personalisasi 20 sifat sebelumnya tidak ditemukan")

    clear, header, choose = (ns[x] for x in ("_clear", "_header", "_choose"))

    def settings(console):
        from .hub_settings import load_hub_settings

        while True:
            cfg = ns["load_config"](); state = load_hub_settings()
            active_count = len(state.get("personality_traits") or [])
            clear(); header(console, "Pengaturan")
            console.print(f"[dim]Identitas[/]      {cfg.persona_name} · {cfg.user_nickname or 'belum diatur'}")
            console.print(f"[dim]Personalisasi[/] {active_count}/20 sifat aktif")
            console.print(
                f"[dim]Lanjutan[/]      Pasangan {'aktif' if state.get('partner_mode') else 'nonaktif'} · "
                f"RolePlay {'aktif' if state.get('roleplay_mode') else 'nonaktif'} · Memori penuh {'aktif' if state.get('full_local_memory') else 'nonaktif'}\n"
            )
            choice = choose("", ["Identitas", "Sistem", "Lanjutan", "Backup", "Update & Recovery", "Kembali"], height=8)
            if choice in {"", "Kembali"}: return
            if choice == "Identitas": ns["_private_identity"](console)
            elif choice == "Sistem": ns["_system"](console)
            elif choice == "Lanjutan": ns["_advanced_settings_125"](console)
            elif choice == "Backup": ns["_lite_backup"](console)
            elif choice == "Update & Recovery": ns["_update_repair"](console)

    ns["_private_personalization_117"] = original_personality
    ns["_private_personalization_110"] = original_personality
    ns["_settings"] = settings
