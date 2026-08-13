#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc13"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
RUNTIME_PATCH_URL="$BASE/patches/runtime-online-agent.patch"
RUNTIME_PATCH_SHA256="bef40bd02af2eb9714f1197337a0f1a5f3ad5fa9ff1e71adfa073141c3756549"
OVERRIDE_MANIFEST_URL="$BASE/overrides/manifest.json"
OVERRIDE_MANIFEST_BLOB="8dfb9a3c42665184c7b99a13ad60dcb95aa2851c"
PRIMITIVE_TRANSFORM_URL="$BASE/overrides/apply-bridge-primitives-rc5.py"
PRIMITIVE_TRANSFORM_BLOB="2f90a928d0808f23889750fe2a09f8d8689c5ad5"
BRIDGE_TRANSFORM_URL="$BASE/overrides/apply-bridge-rc4.py"
BRIDGE_TRANSFORM_BLOB="aa7444fdb843c6d707925e5a62d5189e2b4fbb64"
UNIVERSAL_TRANSFORM_URL="$BASE/overrides/apply-universal-agent-rc5.py"
UNIVERSAL_TRANSFORM_BLOB="0b94916eec7bb68e371b9c7cdda8e2fc503a7dbd"
CORE_RC6_TRANSFORM_URL="$BASE/overrides/apply-core-rc6.py"
CORE_RC6_TRANSFORM_BLOB="9b726e8d0816c177738932fe46a12b8c41e57db9"
CORE_RC6_POSTFIX_URL="$BASE/overrides/apply-core-rc6-postfix.py"
CORE_RC6_POSTFIX_BLOB="82202cbf9335126b985f1def28e890cf512e8353"
BRIDGE_RC6_TRANSFORM_URL="$BASE/overrides/apply-bridge-rc6.py"
BRIDGE_RC6_TRANSFORM_BLOB="f9b7a2a3cff6ab0587fec66502604d7f61be85c2"
CORE_RC7_TRANSFORM_URL="$BASE/overrides/apply-core-rc7.py"
CORE_RC7_TRANSFORM_BLOB="abbd595ad4729a74014d438db9495cecb4cfddec"
BRIDGE_RC7_TRANSFORM_URL="$BASE/overrides/apply-bridge-rc7.py"
BRIDGE_RC7_TRANSFORM_BLOB="c014e904c5a0c3f661619253ae0ce9aff5300b5c"
CORE_RC8_TRANSFORM_URL="$BASE/overrides/apply-core-rc8.py"
CORE_RC8_TRANSFORM_BLOB="07c0239bacf91c7830eee0b32544b9d456c3bd17"
CORE_RC8_POSTFIX_URL="$BASE/overrides/apply-core-rc8-postfix.py"
CORE_RC8_POSTFIX_BLOB="ab5934473bb7fb8cd1913ceda6ac426f10f6aad0"
CORE_RC9_TRANSFORM_URL="$BASE/overrides/apply-core-rc9.py"
CORE_RC9_TRANSFORM_BLOB="ca85d455ec1c24c1b48e51b7a5d87733c8940ea5"
UI_RC10_TRANSFORM_URL="$BASE/overrides/apply-ui-rc10.py"
UI_RC10_TRANSFORM_BLOB="e1908850edbb62c0696f25bd991700ee91f181ba"
UI_RC10_HOTFIX_URL="$BASE/overrides/apply-ui-rc10-hotfix.py"
UI_RC10_HOTFIX_BLOB="5b6fdbf0115f63dfc849fba479ddfd86b25f1849"
CORE_RC11_TRANSFORM_URL="$BASE/overrides/apply-core-rc11.py"
CORE_RC11_TRANSFORM_BLOB="d51cf9db71da074e7f03397ce7ae6f4b5edd7add"
UI_RC12_TRANSFORM_URL="$BASE/overrides/apply-ui-rc12.py"
UI_RC12_TRANSFORM_BLOB="07d10d060f1e0e3e7b299e57661f2967ae7986d2"
UI_RC12_POSTFIX_URL="$BASE/overrides/apply-ui-rc12-postfix.py"
UI_RC12_POSTFIX_BLOB="9d58b1594f99d39c8bb26f432ad9dad929152f33"
CORE_RC13_TRANSFORM_URL="$BASE/overrides/apply-core-rc13.py"
CORE_RC13_TRANSFORM_BLOB="596d94e75c706cf63663ad05ea390a2f8d50958a"
BRIDGE_RC8_TRANSFORM_URL="$BASE/overrides/apply-bridge-rc8.py"
BRIDGE_RC8_TRANSFORM_BLOB="a9c61ffce5ebc489b4795279900f13095a939322"
LLAMA_REV="f785fc9ea485e6cfdda129978310aa52939c3619"

MODEL_REV="e9cf779"
MODEL_NAME="Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking.i1-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/mradermacher/Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking-i1-GGUF/resolve/$MODEL_REV/$MODEL_NAME?download=true"
MODEL_SHA256="dda8f686b793f189a84c854832bb8b4db59c381a60275a567513d5ebb4d92906"
MODEL_BYTES="2708805792"

EMBED_NAME="embeddinggemma-300M-qat-Q4_0.gguf"
EMBED_URL="https://huggingface.co/ggml-org/embeddinggemma-300M-qat-q4_0-GGUF/resolve/main/$EMBED_NAME?download=true"
EMBED_SHA256="50d28e22432a148f6f8a86eab3700f92add5d1f54baf7790675a2a4dadbccf26"
VISION_NAME="SmolVLM2-500M-Video-Instruct-Q8_0.gguf"
VISION_URL="https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/$VISION_NAME?download=true"
VISION_SHA256="6f67b8036b2469fcd71728702720c6b51aebd759b78137a8120733b4d66438bc"
MMPROJ_NAME="mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf"
MMPROJ_URL="https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/$MMPROJ_NAME?download=true"
MMPROJ_SHA256="921dc7e259f308e5b027111fa185efcbf33db13f6e35749ddf7f5cdb60ef520b"

MODE="install"
NO_MODEL=0
[[ -f "$ROOT/config.json" ]] && MODE="update"
[[ "${1:-}" == "--update" ]] && MODE="update"
[[ "${1:-}" == "--no-model" || "${2:-}" == "--no-model" ]] && NO_MODEL=1

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{bin,models,logs,run,data,cache}
LOG="$ROOT/logs/setup.log"
: > "$LOG"

DISPLAY_NAME="Furina"
if [[ -f "$ROOT/config.json" ]] && command -v python >/dev/null 2>&1; then
  DISPLAY_NAME="$(python - "$ROOT/config.json" <<'PY' 2>/dev/null || true
import json,sys
try:
    data=json.load(open(sys.argv[1],encoding='utf-8'))
    name=str(data.get('persona_name') or 'Furina').strip()[:48]
    print(name or 'Furina')
except Exception:
    print('Furina')
PY
)"
  [[ -n "$DISPLAY_NAME" ]] || DISPLAY_NAME="Furina"
fi

PROGRESS=0
ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36m%s\033[0m \033[1mBy Wynn\033[0m\n' "$DISPLAY_NAME"
  if [[ "$MODE" == "update" ]]; then
    printf '\033[2mUpdate Core · memory dan model dipertahankan\033[0m\n\n'
  else
    printf '\033[2mLocal-first companion · setup sekali\033[0m\n\n'
  fi
}

ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=22 filled empty bar="" i
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  filled=$(( pct * width / 100 )); empty=$(( width - filled ))
  for ((i=0; i<filled; i++)); do bar+="█"; done
  for ((i=0; i<empty; i++)); do bar+="░"; done
  printf '\r\033[K\033[35m%s\033[0m \033[2m[%s]\033[0m \033[1m%3d%%\033[0m %s' "$glyph" "$bar" "$pct" "$label"
}

ui_ok() { printf '\033[32m✓\033[0m %s\n' "$1"; }
ui_info() { printf '\033[36m›\033[0m %s\n' "$1"; }
ui_warn() { printf '\033[33m!\033[0m %s\n' "$1"; }

progress_mark() {
  local target="$1" label="$2"
  PROGRESS="$target"
  ui_progress "$PROGRESS" "$label" "✓"
  printf '\n'
}

run_quiet() {
  local label="$1" target="$2"; shift 2
  local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0 rc next
  next="$PROGRESS"
  ui_progress "$next" "$label" "${frames:0:1}"
  "$@" >>"$LOG" 2>&1 &
  local pid=$!
  while kill -0 "$pid" >/dev/null 2>&1; do
    if (( next < target - 1 )); then next=$((next + 1)); fi
    i=$(( (i + 1) % 10 ))
    ui_progress "$next" "$label" "${frames:$i:1}"
    sleep 0.25
  done
  set +e
  wait "$pid"; rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    printf '\r\033[K\033[31m×\033[0m %s\n' "$label"
    tail -n 18 "$LOG" >&2 || true
    exit "$rc"
  fi
  progress_mark "$target" "$label"
}

ui_title

# Install/update is intentionally self-contained. Every required Termux and
# Python dependency is reconciled automatically so a beginner does not need to
# diagnose missing packages manually.
run_quiet "Menyinkronkan Termux" 8 env DEBIAN_FRONTEND=noninteractive pkg update -y
run_quiet "Memasang dependency Furina" 18 env DEBIAN_FRONTEND=noninteractive pkg install -y python python-pip git cmake ninja clang make curl ccache coreutils tar gzip util-linux termux-tools patch gum
run_quiet "Menyiapkan dependency Python" 22 python -m pip install --quiet --upgrade 'rich>=13.9,<15' 'textual==8.2.8'

verify_dependencies() {
  local cmd
  for cmd in python git cmake ninja clang make curl sha256sum tar gzip patch gum; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Dependency wajib tidak ditemukan: $cmd" >&2; return 1; }
  done
  python -c 'import rich, textual; assert textual.__version__ == "8.2.8"'
}
run_quiet "Memeriksa dependency" 24 verify_dependencies

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f'Integritas file berubah; update dibatalkan: {path} {actual}')
PY
}

fetch_model_checked() {
  local target="$ROOT/models/$1" url="$2" sha="$3" label="${4:-$1}" target_progress="${5:-90}"
  if [[ -s "$target" ]] && echo "$sha  $target" | sha256sum -c - >/dev/null 2>&1; then
    progress_mark "$target_progress" "$label"
    return
  fi
  rm -f "$target.part"
  printf '\n'
  ui_info "$label · download"
  curl -L --fail --retry 4 --progress-bar "$url" -o "$target.part"
  echo "$sha  $target.part" | sha256sum -c - >/dev/null
  mv "$target.part" "$target"
  progress_mark "$target_progress" "$label"
}

prepare_core() {
  curl -fsSL --retry 3 "$MANIFEST_URL" -o "$TMP/manifest.json"
  python - "$TMP/manifest.json" "$BASE" "$TMP" <<'PY'
import base64,hashlib,json,pathlib,sys,urllib.request
manifest_path,base,tmp=sys.argv[1:]
m=json.load(open(manifest_path,encoding='utf-8'))
out=pathlib.Path(tmp)/'source.tar.gz'; h=hashlib.sha256()
with out.open('wb') as dst:
    for name in m['source_chunks']:
        raw=base64.b64decode(urllib.request.urlopen(base+'/'+name,timeout=30).read())
        dst.write(raw); h.update(raw)
if h.hexdigest()!=m['source_sha256']:
    raise SystemExit('Checksum Furina Core tidak cocok; update dibatalkan.')
PY
  mkdir -p "$TMP/src"
  tar -xzf "$TMP/source.tar.gz" -C "$TMP/src"

  curl -fsSL --retry 3 "$RUNTIME_PATCH_URL" -o "$TMP/runtime-online-agent.patch"
  echo "$RUNTIME_PATCH_SHA256  $TMP/runtime-online-agent.patch" | sha256sum -c - >/dev/null
  patch -s -p0 -d "$TMP/src" < "$TMP/runtime-online-agent.patch"

  curl -fsSL --retry 3 "$PRIMITIVE_TRANSFORM_URL" -o "$TMP/apply-bridge-primitives-rc5.py"
  verify_git_blob "$TMP/apply-bridge-primitives-rc5.py" "$PRIMITIVE_TRANSFORM_BLOB"
  python "$TMP/apply-bridge-primitives-rc5.py" "$TMP/src/termux" >/dev/null

  curl -fsSL --retry 3 "$OVERRIDE_MANIFEST_URL" -o "$TMP/override-manifest.json"
  python - "$TMP/override-manifest.json" "$OVERRIDE_MANIFEST_BLOB" "$BASE" "$TMP/src/termux" <<'PY'
import hashlib,json,pathlib,sys,urllib.request
manifest_path,expected_manifest_blob,base,termux_root=sys.argv[1:]
manifest_raw=pathlib.Path(manifest_path).read_bytes()
def git_blob_sha(data): return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if git_blob_sha(manifest_raw)!=expected_manifest_blob:
    raise SystemExit('Manifest override Furina berubah; update dibatalkan.')
manifest=json.loads(manifest_raw.decode('utf-8'))
if manifest.get('revision')!='companion-v8':
    raise SystemExit('Revision override Furina tidak dikenali.')
root=pathlib.Path(termux_root).resolve()
for item in manifest.get('files',[]):
    rel=str(item['path']); target_rel=str(item['target'])
    if '..' in pathlib.PurePosixPath(rel).parts or '..' in pathlib.PurePosixPath(target_rel).parts:
        raise SystemExit('Path override tidak aman.')
    if not (target_rel.startswith('core/furina_agent/') or target_rel.startswith('bridge/app/')):
        raise SystemExit('Target override di luar area yang diizinkan ditolak.')
    data=urllib.request.urlopen(base+'/overrides/'+rel,timeout=30).read()
    if git_blob_sha(data)!=str(item['git_blob_sha']):
        raise SystemExit('Integritas override gagal: '+rel)
    target=(root/target_rel).resolve()
    if root not in target.parents: raise SystemExit('Target override keluar dari root.')
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
PY

  for spec in \
    "$BRIDGE_TRANSFORM_URL|$BRIDGE_TRANSFORM_BLOB|apply-bridge-rc4.py" \
    "$UNIVERSAL_TRANSFORM_URL|$UNIVERSAL_TRANSFORM_BLOB|apply-universal-agent-rc5.py" \
    "$CORE_RC6_TRANSFORM_URL|$CORE_RC6_TRANSFORM_BLOB|apply-core-rc6.py" \
    "$CORE_RC6_POSTFIX_URL|$CORE_RC6_POSTFIX_BLOB|apply-core-rc6-postfix.py" \
    "$BRIDGE_RC6_TRANSFORM_URL|$BRIDGE_RC6_TRANSFORM_BLOB|apply-bridge-rc6.py" \
    "$CORE_RC7_TRANSFORM_URL|$CORE_RC7_TRANSFORM_BLOB|apply-core-rc7.py" \
    "$BRIDGE_RC7_TRANSFORM_URL|$BRIDGE_RC7_TRANSFORM_BLOB|apply-bridge-rc7.py" \
    "$CORE_RC8_TRANSFORM_URL|$CORE_RC8_TRANSFORM_BLOB|apply-core-rc8.py" \
    "$CORE_RC8_POSTFIX_URL|$CORE_RC8_POSTFIX_BLOB|apply-core-rc8-postfix.py" \
    "$CORE_RC9_TRANSFORM_URL|$CORE_RC9_TRANSFORM_BLOB|apply-core-rc9.py" \
    "$UI_RC10_TRANSFORM_URL|$UI_RC10_TRANSFORM_BLOB|apply-ui-rc10.py" \
    "$UI_RC10_HOTFIX_URL|$UI_RC10_HOTFIX_BLOB|apply-ui-rc10-hotfix.py" \
    "$CORE_RC11_TRANSFORM_URL|$CORE_RC11_TRANSFORM_BLOB|apply-core-rc11.py" \
    "$UI_RC12_TRANSFORM_URL|$UI_RC12_TRANSFORM_BLOB|apply-ui-rc12.py" \
    "$UI_RC12_POSTFIX_URL|$UI_RC12_POSTFIX_BLOB|apply-ui-rc12-postfix.py" \
    "$CORE_RC13_TRANSFORM_URL|$CORE_RC13_TRANSFORM_BLOB|apply-core-rc13.py" \
    "$BRIDGE_RC8_TRANSFORM_URL|$BRIDGE_RC8_TRANSFORM_BLOB|apply-bridge-rc8.py"; do
    IFS='|' read -r url blob name <<< "$spec"
    curl -fsSL --retry 3 "$url" -o "$TMP/$name"
    verify_git_blob "$TMP/$name" "$blob"
    python "$TMP/$name" "$TMP/src/termux" >/dev/null
  done

  SRC="$TMP/src/termux"
  test -f "$SRC/core/furina_agent/cli.py"
  for file in memory.py response.py vision.py embeddings.py local_vision.py events.py naturalness.py prospective.py device_context.py fastpath.py lexicon.py chat_surface.py tool_runtime.py direct_control.py version.py tui.py; do
    test -f "$SRC/core/furina_agent/$file"
  done
  grep -q 'VERSION = "1.0.0-rc13"' "$SRC/core/furina_agent/version.py"
  grep -q 'config_revision: int = 10' "$SRC/core/furina_agent/config.py"
  grep -q 'fast_path_enabled: bool = True' "$SRC/core/furina_agent/config.py"
  grep -q 'lexicon_enabled: bool = True' "$SRC/core/furina_agent/config.py"
  grep -q 'CREATE TABLE IF NOT EXISTS personal_lexicon' "$SRC/core/furina_agent/lexicon.py"
  grep -q 'def _gum() -> str | None:' "$SRC/core/furina_agent/tui.py"
  grep -q '\["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"\]' "$SRC/core/furina_agent/tui.py"
  grep -q 'stdout=subprocess.PIPE' "$SRC/core/furina_agent/tui.py"
  grep -q 'stderr=None' "$SRC/core/furina_agent/tui.py"
  ! grep -q 'capture_output=True' "$SRC/core/furina_agent/tui.py"
  grep -q 'By Wynn' "$SRC/core/furina_agent/tui.py"
  grep -q 'run_chat_surface' "$SRC/core/furina_agent/tui.py"
  grep -q '\[.*\] :' "$SRC/core/furina_agent/chat_surface.py"
  grep -q 'AgentToolRuntime' "$SRC/core/furina_agent/agent.py"
  grep -q 'self.tools.execute(payload)' "$SRC/core/furina_agent/agent.py"
  grep -q 'RC11: relevance-ranked compact screen' "$SRC/core/furina_agent/agent.py"
  grep -q 'compile_fast_contract' "$SRC/core/furina_agent/agent.py"
  grep -q '_try_fast_skill' "$SRC/core/furina_agent/agent.py"
  grep -q 'LocalVision' "$SRC/core/furina_agent/routing.py"
  grep -q 'waitForExactText' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
  grep -q 'versionCode 10007' "$SRC/bridge/app/build.gradle"

  # Validate the entire staged Core before replacing the active installation.
  # Syntax/import failures therefore leave the previous Core untouched.
  PYTHONPATH="$SRC/core" python -m compileall -q "$SRC/core/furina_agent"
  PYTHONPATH="$SRC/core" python -c 'import rich, textual, furina_agent.tui; from furina_agent.chat_surface import run_chat_surface; from furina_agent.tool_runtime import AgentToolRuntime'

  rm -rf "$ROOT/core.new"
  mkdir -p "$ROOT/core.new"
  cp -R "$SRC/core/furina_agent" "$ROOT/core.new/"
  PYTHONPATH="$ROOT/core.new" python -m compileall -q "$ROOT/core.new/furina_agent"
  if [[ -d "$ROOT/core" ]]; then
    rm -rf "$ROOT/core.prev"
    mv "$ROOT/core" "$ROOT/core.prev"
  fi
  mv "$ROOT/core.new" "$ROOT/core"

  cat > "$ROOT/bin/furina" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PYTHONPATH="$ROOT/core\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$(command -v python)" -m furina_agent.cli "\$@"
EOF
  chmod +x "$ROOT/bin/furina"
  ln -sf "$ROOT/bin/furina" /data/data/com.termux/files/usr/bin/furina
  export PATH="$ROOT/bin:$PATH"
  LINE='export PATH="$HOME/.furina-agent/bin:$PATH"'
  grep -Fqx "$LINE" "$HOME/.bashrc" 2>/dev/null || echo "$LINE" >> "$HOME/.bashrc"
}

run_quiet "Memasang Furina Core RC13" 44 prepare_core

prepare_llama() {
  LLAMA="$ROOT/llama.cpp"
  if [[ ! -d "$LLAMA/.git" ]]; then
    git clone --quiet --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$LLAMA"
  fi
  CURRENT="$(git -C "$LLAMA" rev-parse HEAD 2>/dev/null || true)"
  if [[ "$CURRENT" != "$LLAMA_REV" ]]; then
    git -C "$LLAMA" fetch --quiet --depth 1 origin "$LLAMA_REV"
    git -C "$LLAMA" checkout --quiet --detach "$LLAMA_REV"
  fi
  BUILD_MARKER="$ROOT/data/llama-build-$LLAMA_REV-kleidiai-rc7"
  if [[ ! -x "$LLAMA/build/bin/llama-server" || ! -x "$LLAMA/build/bin/llama-embedding" || ! -f "$BUILD_MARKER" ]]; then
    rm -rf "$LLAMA/build"
    JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"; [[ "$JOBS" -gt 6 ]] && JOBS=6
    if cmake -S "$LLAMA" -B "$LLAMA/build" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=OFF \
        -DGGML_CPU_KLEIDIAI=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_OPENSSL=OFF \
        && cmake --build "$LLAMA/build" --target llama-server llama-cli llama-bench llama-embedding -j "$JOBS"; then
      :
    else
      rm -rf "$LLAMA/build"
      cmake -S "$LLAMA" -B "$LLAMA/build" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=OFF \
        -DLLAMA_BUILD_UI=OFF -DLLAMA_OPENSSL=OFF
      cmake --build "$LLAMA/build" --target llama-server llama-cli llama-bench llama-embedding -j "$JOBS"
    fi
    touch "$BUILD_MARKER"
  fi
}

run_quiet "Menyiapkan local engine" 62 prepare_llama

MODEL_CURRENT="$(PYTHONPATH="$ROOT/core" python - <<'PY'
from furina_agent.config import load_config
from pathlib import Path
p=load_config().model_path
print(p if p and Path(p).is_file() else '')
PY
)"

if [[ -n "$MODEL_CURRENT" ]]; then
  progress_mark 70 "Model chat dipertahankan"
elif [[ "$MODE" == "update" || "$NO_MODEL" -eq 1 ]]; then
  progress_mark 70 "Model chat utama tidak diubah"
else
  TARGET="$ROOT/models/$MODEL_NAME"
  if [[ ! -s "$TARGET" ]]; then
    printf '\n'; ui_info "Model chat lokal · 2.7 GB"
    curl -L --fail --retry 4 --progress-bar "$MODEL_URL" -o "$TARGET.part"
    GOT_BYTES="$(wc -c < "$TARGET.part" | tr -d ' ')"; GOT_SHA="$(sha256sum "$TARGET.part" | awk '{print $1}')"
    [[ "$GOT_BYTES" == "$MODEL_BYTES" ]] || { echo "Ukuran model salah" >&2; exit 1; }
    [[ "$GOT_SHA" == "$MODEL_SHA256" ]] || { echo "SHA-256 model salah" >&2; exit 1; }
    mv "$TARGET.part" "$TARGET"
  fi
  furina model "$TARGET" >>"$LOG" 2>&1
  progress_mark 70 "Model chat lokal"
fi

if [[ "$NO_MODEL" -eq 0 ]]; then
  fetch_model_checked "$EMBED_NAME" "$EMBED_URL" "$EMBED_SHA256" "Semantic memory" 78
  fetch_model_checked "$VISION_NAME" "$VISION_URL" "$VISION_SHA256" "Local vision" 85
  fetch_model_checked "$MMPROJ_NAME" "$MMPROJ_URL" "$MMPROJ_SHA256" "Vision projector" 90
else
  progress_mark 90 "Cognition model dilewati (--no-model)"
fi

prepare_bridge() {
  BRIDGE_VERSION="$(curl -fsS --max-time 2 http://127.0.0.1:8765/health 2>/dev/null | python -c 'import json,sys; print(json.load(sys.stdin).get("version", ""))' 2>/dev/null || true)"
  EXPECTED_BRIDGE="$(python -c 'import json; print(json.load(open("'"$TMP"'/manifest.json"))["bridge_version"])')"
  if [[ "$BRIDGE_VERSION" == "$EXPECTED_BRIDGE" ]]; then
    furina connect >/dev/null 2>&1 || true
    return
  fi
  RELEASE_BASE="$(python -c 'import json; print(json.load(open("'"$TMP"'/manifest.json"))["bridge_release_base"])')"
  curl -fsSL --retry 3 "$RELEASE_BASE/bridge.json" -o "$TMP/bridge.json"
  APK_URL="$(python -c 'import json; print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  APK_SHA="$(python -c 'import json; print(json.load(open("'"$TMP"'/bridge.json"))["sha256"])')"
  curl -fsSL --retry 3 "$APK_URL" -o "$ROOT/cache/Furina-Agent-Bridge.apk"
  echo "$APK_SHA  $ROOT/cache/Furina-Agent-Bridge.apk" | sha256sum -c - >/dev/null
  termux-open-url "$APK_URL" >/dev/null 2>&1 || true
}

run_quiet "Memeriksa Furina Bridge" 96 prepare_bridge

verify_install() {
  PYTHONPATH="$ROOT/core" python -m compileall -q "$ROOT/core/furina_agent"
  PYTHONPATH="$ROOT/core" python -c 'import textual; from furina_agent.chat_surface import run_chat_surface; from furina_agent.tool_runtime import AgentToolRuntime'
  furina status >/dev/null || true
  command -v gum >/dev/null
}
run_quiet "Verifikasi akhir" 100 verify_install

printf '\n'
ui_ok "Furina siap"
if [[ "$MODE" == "install" ]]; then
  printf '\033[2mBuka dengan:\033[0m  \033[1;36mfurina\033[0m\n'
else
  printf '\033[2mRC13 sudah terpasang. Jalankan:\033[0m  \033[1;36mfurina\033[0m\n'
fi
printf '\033[2mLog setup: %s\033[0m\n\n' "$LOG"