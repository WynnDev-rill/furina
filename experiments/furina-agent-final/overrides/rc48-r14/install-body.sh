#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc48"
DEPENDENCY_REVISION="2026.08.16-r14"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
RC48_BODY_URL="$BASE/overrides/rc48/install-body.sh"
RC48_BODY_BLOB="13cc5b168052ed07fe09e78d6ecc2f5a758318be"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr && "${FURINAHUB_VALIDATE_ONLY:-0}" != "1" ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

fetch() {
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 4 "$url" -o "$out"
  else
    python - "$url" "$out" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
  fi
}

verify_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas fondasi RC48 berubah: {actual} != {expected}")
PY
}

fetch "$RC48_BODY_URL" "$TMP/rc48-install-body.sh"
verify_blob "$TMP/rc48-install-body.sh" "$RC48_BODY_BLOB"

# Keep the hotfix transform intentionally simple. r13 used an embedded Python
# string containing a shell line-continuation backslash and failed on-device
# before the updater could run. Fixed-string checks + sed avoid that class of bug.
if [[ "$(grep -Fc 'DEPENDENCY_REVISION="2026.08.16-r12"' "$TMP/rc48-install-body.sh")" != "1" ]]; then
  echo "Marker dependency RC48/r12 tidak ditemukan atau ambigu." >&2
  exit 3
fi
if [[ "$(grep -Fc 'exec env NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000' "$TMP/rc48-install-body.sh")" != "1" ]]; then
  echo "Marker launcher OpenConnector RC48 tidak ditemukan atau ambigu." >&2
  exit 3
fi

sed -i 's/^DEPENDENCY_REVISION="2026\.08\.16-r12"$/DEPENDENCY_REVISION="2026.08.16-r14"/' "$TMP/rc48-install-body.sh"
sed -i 's/exec env NODE_NO_WARNINGS=1 HOST=127\.0\.0\.1 PORT=3000/exec env NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000/' "$TMP/rc48-install-body.sh"

grep -Fq 'DEPENDENCY_REVISION="2026.08.16-r14"' "$TMP/rc48-install-body.sh"
grep -Fq 'NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000' "$TMP/rc48-install-body.sh"
grep -Fq 'npm install --omit=dev --workspaces=false --no-audit --no-fund' "$TMP/rc48-install-body.sh"
grep -Fq 'URL="http://127.0.0.1:3000/v1/health"' "$TMP/rc48-install-body.sh"
bash -n "$TMP/rc48-install-body.sh"

if [[ "${FURINAHUB_VALIDATE_ONLY:-0}" == "1" ]]; then
  echo "FURINAHUB_OPENCONNECTOR_R14_TRANSFORM_OK"
  exit 0
fi

bash "$TMP/rc48-install-body.sh" "$@"
