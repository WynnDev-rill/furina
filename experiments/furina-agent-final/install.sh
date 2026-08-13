#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# RC17 recovery bootstrap.
# The full RC17 installer is pinned to the known-good merge commit and patched
# in-memory to use the marker-tolerant RC17 transform. This keeps the public
# install/update entry point stable while avoiding another fragile source rewrite.
PINNED_INSTALLER_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/c48681102177c9f1deee5153e9667ca39dbae9ed/experiments/furina-agent-final/install.sh"
PINNED_INSTALLER_BLOB="b40fb20c74e0aafe20006c79581a0ed1bad00562"
RC17_HOTFIX_URL='$BASE/overrides/apply-core-rc17-hotfix.py'
RC17_HOTFIX_BLOB="4ec514a512758ded6e9d263ef4e8bbbd12bcf2dc"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TARGET="$TMP/install-rc17.sh"

curl -fsSL --retry 3 "$PINNED_INSTALLER_URL" -o "$TARGET"

python - "$TARGET" "$PINNED_INSTALLER_BLOB" "$RC17_HOTFIX_URL" "$RC17_HOTFIX_BLOB" <<'PY'
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected_blob, hotfix_url, hotfix_blob = sys.argv[2:]
data = path.read_bytes()
actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
if actual != expected_blob:
    raise SystemExit(f"Integritas installer RC17 berubah; update dibatalkan: {actual}")

text = data.decode("utf-8")
old_url = 'CORE_RC17_TRANSFORM_URL="$BASE/overrides/apply-core-rc17.py"'
old_blob = 'CORE_RC17_TRANSFORM_BLOB="ffadcffc83df3786b670894b8307bd760a5c0b4d"'
new_url = f'CORE_RC17_TRANSFORM_URL="{hotfix_url}"'
new_blob = f'CORE_RC17_TRANSFORM_BLOB="{hotfix_blob}"'

if text.count(old_url) != 1 or text.count(old_blob) != 1:
    raise SystemExit("Kontrak installer RC17 tidak dikenali; update dibatalkan.")

text = text.replace(old_url, new_url, 1).replace(old_blob, new_blob, 1)
if 'VERSION="1.0.0-rc17"' not in text:
    raise SystemExit("Versi installer dasar bukan RC17.")
path.write_text(text, encoding="utf-8")
PY

exec bash "$TARGET" "$@"
