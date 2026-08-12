#!/usr/bin/env python3
"""Deterministic invariants for Wynn-approved FUR-ENG-031..036."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"FUR-ENG-031-036 GATE FAILED: {message}")


def main() -> None:
    server_client = read("src/integrations/supabase/client.server.ts")
    migration = read("supabase/migrations/20260812000100_secure_match_memories.sql")
    root = read("src/routes/__root.tsx")
    unified = read("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")
    cloud = read("src/hooks/use-furina-cloud-backup.ts")
    backup = read("android-wrapper/app/src/main/java/com/wynndev/furina/BackupManager.kt")
    manifest = read("android-wrapper/app/src/main/AndroidManifest.xml")
    callback = read("android-wrapper/app/src/main/java/com/wynndev/furina/AuthCallbackActivity.kt")
    auth_page = read("src/routes/backup-auth.tsx")
    assetlinks = read("public/.well-known/assetlinks.json")

    # 031: user-scoped server data must remain under bearer auth + RLS, never service role.
    require("SUPABASE_SERVICE_ROLE_KEY" not in server_client,
            "user-scoped server client must not use service-role credentials")
    require("SUPABASE_PUBLISHABLE_KEY" in server_client and "Authorization" in server_client,
            "server client must forward the authenticated bearer token")
    require("auth.uid() = match_user_id" in migration and "m.user_id = auth.uid()" in migration,
            "match_memories must bind supplied user id to authenticated uid")
    require("REVOKE ALL" in migration and "FROM PUBLIC, anon" in migration,
            "anonymous callers must not execute the security-definer memory matcher")

    # 032: local text mode and optional cloud voice must have an explicit privacy boundary.
    for marker in ("furina:privacy:cloud-voice-v1", "Chat dengan model lokal tetap diproses di perangkat", "VOICEVOX", "sampel suara"):
        require(marker in root, f"cloud voice disclosure missing: {marker}")

    # 033: only CompanionIntelligence continues evolving relationship state.
    generate = unified.split("suspend fun generate", 1)[1].split("suspend fun unload", 1)[0]
    require("contextEngine.observeUserTurn(" not in generate,
            "legacy MemoryStore emotional state must not evolve in parallel on hot path")
    require("contextEngine.runMaintenance(sessionId, userText)" in unified and "CompanionIntelligence.observeUserTurn" in unified,
            "serialized companion maintenance must own evolving relationship/reflection state")

    # 034: keep rolling encrypted cloud snapshots in addition to latest.
    require("SNAPSHOT_RETENTION = 5" in cloud and "SNAPSHOT_PREFIX" in cloud,
            "cloud backup must retain versioned history")
    require("upsert: false" in cloud and "upsert: true" in cloud and ".remove(" in cloud,
            "cloud backup must write immutable snapshots, refresh latest, and prune retention")

    # 035: incomplete local writes never become valid .furina backups.
    require('val tempName = "Furina-${now}.partial"' in backup,
            "local backup must write a temporary file first")
    require("promoteBackup(root, temp, fileName)" in backup and "temp.delete()" in backup,
            "local backup must promote only completed output and clean temporary files")

    # 036: OAuth callback is an owned verified HTTPS App Link, not an exported custom scheme.
    require('android:autoVerify="true"' in manifest and 'android:scheme="https"' in manifest and
            'android:host="furina-pi.vercel.app"' in manifest and 'android:pathPrefix="/backup-auth"' in manifest,
            "Android OAuth callback must use the verified Furina HTTPS route")
    require('android:scheme="com.wynndev.furina"' not in manifest,
            "custom callback scheme must not remain exported")
    require('uri.scheme != "https"' in callback and 'TRUSTED_HOST = "furina-pi.vercel.app"' in callback and
            'TRUSTED_PATH = "/backup-auth"' in callback,
            "callback activity must validate exact HTTPS host/path")
    require("scheme=https;package=com.wynndev.furina" in auth_page and "com.wynndev.furina://auth/callback" not in auth_page,
            "browser fallback must target the owned HTTPS app link")
    require('"package_name": "com.wynndev.furina"' in assetlinks and
            "69:B1:1E:C4:74:D5:57:C9:2D:E2:BC:32:9C:CC:BA:AA:C4:88:D0:DC:B9:9C:9B:1B:A7:8F:6C:5E:1D:9C:D1:A7" in assetlinks,
            "assetlinks must bind the stable Furina signing certificate")

    print("FUR-ENG-031..036 gate passed")


if __name__ == "__main__":
    main()
