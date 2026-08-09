---
name: furina-backup
description: Protect portable Furina history and relationship state across resets, reinstalls, and device migration.
---

# Furina Backup

Use this skill for database changes, backup/restore, encryption, cloud-folder integration, or device migration.

## Requirements

1. Backup canonical user state: all sessions/messages, extracted memories, relationship state, persona-related settings, and schema metadata when applicable.
2. Do not back up multi-gigabyte model weights. Models are reproducible downloads.
3. Backups must be portable to a new device and must not depend solely on the old Android Keystore.
4. Current format uses AES-256-GCM with a portable recovery key. Never silently rotate that key.
5. Before copying SQLite, checkpoint WAL. After restore, run integrity checks before accepting the database.
6. Keep multiple rolling backups so one corrupt latest snapshot cannot erase years of history.
7. Cloud storage is optional transport. Local chat and inference must continue when the network is unavailable.
8. Schema migrations must remain backward-aware; never discard unknown historical fields merely to simplify a release.

## Google Drive approach

Prefer Android Storage Access Framework for the first implementation: the user chooses a Drive/cloud folder through the system file picker and Furina persists permission to that folder. This keeps app login separate from backup transport.
