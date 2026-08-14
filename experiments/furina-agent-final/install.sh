#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc33"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PREV_COMMIT="2f289e025b29b5525828bbe48073526a56fa17e5"
PREV_INSTALL_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final/install.sh"
PREV_MANIFEST_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final/manifest.json"
PREV_INSTALL_BLOB="198fb6b21d739388481c18fb21e3209fa3c34425"

RC33_DIR_URL="$BASE/overrides/rc33"
APPLY_BLOB="a2850609b156cd10c1b81272c8b8dac18e1f6d74"
PSYCHE_BLOB="86511776ef51929dc59aedecf7a11fc16a7823ad"
CHAT_BLOB="eca023f64be0c39e9ad2f9d518c2dfdb0c46a68d"
PERSONA_BLOB="8d16d8c9df8afd29821c415f2f6ae33f9962ba8e"
RESPONSE_BLOB="0947dcf577853f497fb6281a5d5d3e55fae76e30"
MIND_BLOB="223bd9c3663ca1974513059207c2f7a33f5c2d6c"
ROUTING_BLOB="fca98541d9fec5d777b89427d6f398f9a8dddb4f"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc33.log"
: > "$LOG"

verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path, expected = sys.argv[1:]
data = pathlib.Path(path).read_bytes()
actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas update berubah: {path} {actual} != {expected}")
PY
}

fetch_blob() {
  local url="$1" expected="$2" out="$3"
  curl -fsSL --retry 3 "$url" -o "$out"
  verify_git_blob "$out" "$expected"
}

core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try:
    s=open(sys.argv[1],encoding="utf-8").read()
except Exception:
    print("missing"); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else "unknown")
PY
}

printf '\033[2J\033[H'
printf '\033[1;36mFurina\033[0m \033[1mBy Wynn\033[0m\n'
printf '\033[2mUpdate Agent RC33 · Psyche continuity + role-aware model routing\033[0m\n\n'

CURRENT="$(core_version 2>/dev/null || true)"
if [[ "$CURRENT" == "1.0.0-rc33" ]]; then
  echo "✓ Core RC33 sudah aktif."
  exit 0
fi

fetch_blob "$PREV_INSTALL_URL" "$PREV_INSTALL_BLOB" "$TMP/install-rc32.sh"
python - "$TMP/install-rc32.sh" "$PREV_MANIFEST_URL" <<'PY'
import pathlib,sys
path=pathlib.Path(sys.argv[1])
manifest=sys.argv[2]
text=path.read_text(encoding="utf-8")
old='MANIFEST_URL="$BASE/manifest.json"'
new=f'MANIFEST_URL="{manifest}"'
if text.count(old) != 1:
    raise SystemExit("RC32 installer manifest marker berubah")
path.write_text(text.replace(old,new,1),encoding="utf-8")
PY
bash "$TMP/install-rc32.sh" "$@" >>"$LOG" 2>&1

CURRENT="$(core_version)"
[[ "$CURRENT" == "1.0.0-rc32" ]] || {
  echo "Gagal menyiapkan fondasi RC32: $CURRENT" >&2
  tail -n 30 "$LOG" >&2 || true
  exit 1
}

curl -fsSL --retry 3 "$BASE/manifest.json" -o "$TMP/manifest.json"
EXPECTED="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["version"])')"
[[ "$EXPECTED" == "1.0.0-rc33" ]] || {
  echo "Manifest eksperimen belum menunjuk RC33: $EXPECTED" >&2
  exit 1
}

mkdir -p "$TMP/rc33" "$TMP/stage"
fetch_blob "$RC33_DIR_URL/apply.py" "$APPLY_BLOB" "$TMP/rc33/apply.py"
fetch_blob "$RC33_DIR_URL/psyche.py" "$PSYCHE_BLOB" "$TMP/rc33/psyche.py"
fetch_blob "$RC33_DIR_URL/chat.py" "$CHAT_BLOB" "$TMP/rc33/chat.py"
fetch_blob "$RC33_DIR_URL/persona.py" "$PERSONA_BLOB" "$TMP/rc33/persona.py"
fetch_blob "$RC33_DIR_URL/response.py" "$RESPONSE_BLOB" "$TMP/rc33/response.py"
fetch_blob "$RC33_DIR_URL/mind_v2.py" "$MIND_BLOB" "$TMP/rc33/mind_v2.py"
fetch_blob "$RC33_DIR_URL/routing.py" "$ROUTING_BLOB" "$TMP/rc33/routing.py"

cp -R "$ROOT/core" "$TMP/stage/core"
python "$TMP/rc33/apply.py" "$TMP/stage" "$TMP/rc33" >>"$LOG" 2>&1

PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.psyche import PsycheEngine, STATE_KEY
from furina_agent.routing import RoutingLLM

assert VERSION == "1.0.0-rc33"
assert STATE_KEY == "furina_psyche_v1"
assert hasattr(RoutingLLM, "_infer_role")
src=open(__import__("furina_agent.chat").chat.__file__,encoding="utf-8").read()
for marker in ("MIND PACKET", "Experience Integrator", 'role="conversation"', 'role="memory"'):
    assert marker in src, marker
PY

furina stop >/dev/null 2>&1 || true
rm -rf "$ROOT/core.prev"
mv "$ROOT/core" "$ROOT/core.prev"
mv "$TMP/stage/core" "$ROOT/core"

printf '\n\033[32m✓\033[0m Core RC33 aktif.\n'
printf '  Memory/model/data tetap dipertahankan. Bridge tetap RC18.\n'
