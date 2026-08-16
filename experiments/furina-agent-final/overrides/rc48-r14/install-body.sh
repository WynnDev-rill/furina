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

if [[ ! -d /data/data/com.termux/files/usr ]]; then
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

python - "$TMP/rc48-install-body.sh" <<'PY'
from pathlib import Path
import sys

path=Path(sys.argv[1])
text=path.read_text(encoding='utf-8')

old_revision='DEPENDENCY_REVISION="2026.08.16-r12"'
new_revision='DEPENDENCY_REVISION="2026.08.16-r14"'
if text.count(old_revision) != 1:
    raise SystemExit('Marker dependency RC48/r12 tidak ditemukan')
text=text.replace(old_revision,new_revision,1)

# Match only the stable prefix. Do not place the shell line-continuation backslash
# inside a Python single-quoted string; that was the r13 SyntaxError on-device.
old_launcher='exec env NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 '
new_launcher='exec env NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 '
if text.count(old_launcher) != 1:
    raise SystemExit('Marker launcher OpenConnector RC48 tidak ditemukan')
text=text.replace(old_launcher,new_launcher,1)

required=(
    'DEPENDENCY_REVISION="2026.08.16-r14"',
    'NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000',
    'npm install --omit=dev --workspaces=false --no-audit --no-fund',
    'URL="http://127.0.0.1:3000/v1/health"',
)
missing=[item for item in required if item not in text]
if missing:
    raise SystemExit(f'Binding runtime r14 tidak lengkap: {missing}')
path.write_text(text,encoding='utf-8')
PY

# Validate the transformed installer itself. This is intentionally executed in CI
# as well so Python-transform syntax errors cannot pass with only `bash -n`.
bash -n "$TMP/rc48-install-body.sh"
python - "$TMP/rc48-install-body.sh" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(encoding='utf-8')
assert 'DEPENDENCY_REVISION="2026.08.16-r14"' in text
assert 'NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000' in text
print('FURINAHUB_OPENCONNECTOR_R14_TRANSFORM_OK')
PY

bash "$TMP/rc48-install-body.sh" "$@"
