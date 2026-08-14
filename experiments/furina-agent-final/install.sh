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
APPLY_BLOB="8d3f94bcac059242f6d00a3bb6e4bc48d0983b4f"
PSYCHE_BLOB="f94cbe1b0226a1d26d68c67e55a524a84fa999eb"
CHAT_BLOB="284cb76fc9afcc12b8e2d8b590597eab0addf57e"
PERSONA_BLOB="40ebd81d3a98e00747a0ec5d48230a5edada8fb5"
RESPONSE_BLOB="e69b27483b13dc38d8fb33719e70d45d50fa265a"
MIND_BLOB="7eeaf824add40123f1dc9a6943d34041cbf2fbed"
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
PROGRESS=0

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36mFurina\033[0m \033[1mBy Wynn\033[0m\n'
  printf '\033[2mUpdate Agent RC33 · pemeriksaan menyeluruh + Psyche continuity\033[0m\n\n'
}

ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=16 filled empty bar="" i
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  filled=$(( pct * width / 100 ))
  empty=$(( width - filled ))
  for ((i=0;i<filled;i++)); do bar+="█"; done
  for ((i=0;i<empty;i++)); do bar+="░"; done
  printf '\r\033[K\033[35m%s\033[0m \033[2m[%s]\033[0m \033[1m%3d%%\033[0m %s' "$glyph" "$bar" "$pct" "$label"
}

mark() {
  PROGRESS="$1"
  ui_progress "$1" "$2" "✓"
  printf '\n'
}

run_quiet() {
  local label="$1" target="$2"; shift 2
  local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0 rc next="$PROGRESS"
  ui_progress "$next" "$label" "${frames:0:1}"
  "$@" >>"$LOG" 2>&1 & local pid=$!
  while kill -0 "$pid" >/dev/null 2>&1; do
    (( next < target - 1 )) && next=$((next+1))
    i=$(((i+1)%10))
    ui_progress "$next" "$label" "${frames:$i:1}"
    sleep 0.16
  done
  set +e
  wait "$pid"
  rc=$?
  set -e
  if (( rc != 0 )); then
    printf '\r\033[K\033[31m×\033[0m %s\n' "$label"
    printf '\033[2mLog: %s\033[0m\n' "$LOG" >&2
    tail -n 30 "$LOG" >&2 || true
    exit "$rc"
  fi
  mark "$target" "$label"
}

ensure_python() {
  if command -v python >/dev/null 2>&1; then
    return 0
  fi
  pkg install -y python
}

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
    print("missing")
    raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else "unknown")
PY
}

fetch_manifest() {
  curl -fsSL --retry 3 "$BASE/manifest.json" -o "$TMP/manifest.json"
  python - "$TMP/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m.get('version') == '1.0.0-rc33', m.get('version')
assert m.get('bridge_version') == '1.0.0-rc18', m.get('bridge_version')
assert int(m.get('bridge_version_code')) == 10018, m.get('bridge_version_code')
assert len(m.get('source_sha256','')) == 64
PY
}

fetch_rc33_bundle() {
  mkdir -p "$TMP/rc33"
  fetch_blob "$RC33_DIR_URL/apply.py" "$APPLY_BLOB" "$TMP/rc33/apply.py"
  fetch_blob "$RC33_DIR_URL/psyche.py" "$PSYCHE_BLOB" "$TMP/rc33/psyche.py"
  fetch_blob "$RC33_DIR_URL/chat.py" "$CHAT_BLOB" "$TMP/rc33/chat.py"
  fetch_blob "$RC33_DIR_URL/persona.py" "$PERSONA_BLOB" "$TMP/rc33/persona.py"
  fetch_blob "$RC33_DIR_URL/response.py" "$RESPONSE_BLOB" "$TMP/rc33/response.py"
  fetch_blob "$RC33_DIR_URL/mind_v2.py" "$MIND_BLOB" "$TMP/rc33/mind_v2.py"
  fetch_blob "$RC33_DIR_URL/routing.py" "$ROUTING_BLOB" "$TMP/rc33/routing.py"
  python -m py_compile "$TMP/rc33/"*.py
}

prepare_rc32() {
  fetch_blob "$PREV_INSTALL_URL" "$PREV_INSTALL_BLOB" "$TMP/install-rc32.sh"
  python - "$TMP/install-rc32.sh" "$PREV_MANIFEST_URL" <<'PY'
import pathlib,sys
path=pathlib.Path(sys.argv[1])
manifest=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='MANIFEST_URL="$BASE/manifest.json"'
new=f'MANIFEST_URL="{manifest}"'
if text.count(old) != 1:
    raise SystemExit('RC32 installer manifest marker berubah')
path.write_text(text.replace(old,new,1),encoding='utf-8')
PY
  bash "$TMP/install-rc32.sh" "$@"
  [[ "$(core_version)" == "1.0.0-rc32" ]]
}

stage_core() {
  rm -rf "$TMP/stage"
  mkdir -p "$TMP/stage"
  cp -R "$ROOT/core" "$TMP/stage/core"
}

apply_rc33() {
  python "$TMP/rc33/apply.py" "$TMP/stage" "$TMP/rc33"
}

validate_compile() {
  PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.psyche import STATE_KEY
assert VERSION == '1.0.0-rc33'
assert STATE_KEY == 'furina_psyche_v1'
PY
}

validate_behavior() {
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
import tempfile
from pathlib import Path

from furina_agent.psyche import PsycheEngine
from furina_agent.providers import ProviderState
from furina_agent.routing import RoutingLLM
from furina_agent.policy import build_goal_lock, classify_action
from furina_agent.tool_runtime import AgentToolRuntime

class Store:
    def __init__(self): self.state={}
    def get_state(self,k,d=None): return self.state.get(k,d)
    def set_state(self,k,v): self.state[k]=v
    def relationship_state(self):
        return {'trust':0.4,'closeness':0.3,'friction':0.05,'playfulness':0.3}

# Satu kritik hanya boleh memengaruhi affect cepat, bukan personality jangka panjang.
p=PsycheEngine(Store())
before=dict(p.state['long']['traits'])
p.observe_user('jawabanmu salah lagi')
assert p.state['short']['valence'] < 0
assert p.state['long']['traits'] == before

# Routing model internal tidak boleh menggeser role percakapan.
assert RoutingLLM._infer_role([{'role':'system','content':'Kamu Experience Integrator internal'}], True) == 'memory'
assert RoutingLLM._infer_role([{'role':'system','content':'Android agent planner output JSON'}], True) == 'agent_planner'
assert RoutingLLM._infer_role([{'role':'system','content':'Kamu Furina'}], False) == 'conversation'
with tempfile.TemporaryDirectory() as td:
    state=ProviderState(Path(td)/'provider.json')
    state.mark_success('groq','chat-model','conversation')
    state.mark_success('groq','json-model','memory')
    assert state.last_good('groq','conversation') == 'chat-model'
    assert state.last_good('groq','memory') == 'json-model'

# Persona lama dan duplicate state writer tidak boleh kembali.
import furina_agent.response as response
import furina_agent.persona as persona
import furina_agent.chat as chat
response_src=open(response.__file__,encoding='utf-8').read()
persona_src=open(persona.__file__,encoding='utf-8').read()
chat_src=open(chat.__file__,encoding='utf-8').read()
assert 'companion_state' not in response_src
assert 'Bangga, teatrikal' not in persona_src
assert 'DIALOGUE_ANCHORS' not in persona_src
for marker in ('MIND PACKET','Experience Integrator','role="conversation"','role="memory"'):
    assert marker in chat_src, marker

# RC32 security boundary harus tetap aktif setelah RC33.
apps=[{'label':'WhatsApp','package':'com.whatsapp'},{'label':'Notes','package':'com.notes'}]
lock=build_goal_lock('buka WhatsApp cari Ariel',apps,[{'type':'open_app','package':'com.whatsapp'}])
assert classify_action(
    {'package':'com.whatsapp','nodes':[{'id':7,'text':'Send'}]},
    {'type':'tap_node','node':7},lock
)[0] == 'blocked'
agent_src=open(__import__('furina_agent.agent').agent.__file__,encoding='utf-8').read()
assert 'RC32_POLICY_BOUNDARY' in agent_src
assert 'agent_action_firewall' in agent_src

runtime=AgentToolRuntime.__new__(AgentToolRuntime)
runtime._handlers={}
try:
    runtime._handler_for('arbitrary_shell')
except ValueError:
    pass
else:
    raise AssertionError('unknown capability failed open')
PY
}

install_stage() {
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
}

ui_title
run_quiet "Memeriksa lingkungan Termux" 6 ensure_python
CURRENT="$(core_version 2>/dev/null || true)"
mark 12 "Versi Core saat ini: ${CURRENT:-missing}"
run_quiet "Memeriksa manifest dan versi target" 22 fetch_manifest
run_quiet "Memverifikasi integritas paket RC33" 36 fetch_rc33_bundle

UPGRADED=0
if [[ "$CURRENT" != "1.0.0-rc33" ]]; then
  run_quiet "Merekonstruksi fondasi Core RC32" 52 prepare_rc32 "$@"
  CURRENT="$(core_version)"
  mark 56 "Fondasi Core RC32 terverifikasi"
else
  mark 52 "Core RC33 ditemukan; lanjut health-check penuh"
fi

run_quiet "Membuat salinan aman Core" 62 stage_core
if [[ "$CURRENT" == "1.0.0-rc32" ]]; then
  run_quiet "Menerapkan Psyche continuity RC33" 74 apply_rc33
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc33" ]]; then
  mark 74 "Tidak perlu menulis ulang Core RC33"
else
  echo "Versi Core tidak dapat divalidasi otomatis: $CURRENT" >&2
  exit 1
fi

run_quiet "Memeriksa syntax dan import seluruh Core" 84 validate_compile
run_quiet "Menjalankan regression lokal Psyche, routing, dan policy" 94 validate_behavior

if (( UPGRADED == 1 )); then
  run_quiet "Memasang Core secara atomik" 99 install_stage
  mark 100 "Update Agent RC33 selesai dan terverifikasi"
else
  mark 100 "Core RC33 terverifikasi sehat; tidak ada file yang diubah"
fi

printf '\n\033[32m✓\033[0m Pemeriksaan menyeluruh selesai.\n'
printf '  Memory/model/data tetap dipertahankan. Bridge tetap RC18.\n'
printf '\033[2m  Log lengkap: %s\033[0m\n' "$LOG"
