#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc10"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
RUNTIME_PATCH_URL="$BASE/patches/runtime-online-agent.patch"
RUNTIME_PATCH_SHA256="bef40bd02af2eb9714f1197337a0f1a5f3ad5fa9ff1e71adfa073141c3756549"
OVERRIDE_MANIFEST_URL="$BASE/overrides/manifest.json"
OVERRIDE_MANIFEST_BLOB="16bb72c89951bd2570208672e77604876efe31be"
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

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36mFURINA\033[0m  \033[2m%s\033[0m\n' "$VERSION"
  if [[ "$MODE" == "update" ]]; then
    printf '\033[2mUpdate Core · memory dan model dipertahankan\033[0m\n\n'
  else
    printf '\033[2mLocal-first companion · setup sekali\033[0m\n\n'
  fi
}

ui_ok() { printf '\033[32m✓\033[0m %s\n' "$1"; }
ui_info() { printf '\033[36m›\033[0m %s\n' "$1"; }
ui_warn() { printf '\033[33m!\033[0m %s\n' "$1"; }

run_quiet() {
  local label="$1"; shift
  local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0 rc
  printf '\033[35m%s\033[0m %s' "${frames:0:1}" "$label"
  "$@" >>"$LOG" 2>&1 &
  local pid=$!
  while kill -0 "$pid" >/dev/null 2>&1; do
    i=$(( (i + 1) % 10 ))
    printf '\r\033[K\033[35m%s\033[0m %s' "${frames:$i:1}" "$label"
    sleep 0.11
  done
  set +e
  wait "$pid"; rc=$?
  set -e
  printf '\r\033[K'
  if [[ "$rc" -ne 0 ]]; then
    printf '\033[31m×\033[0m %s\n' "$label"
    tail -n 18 "$LOG" >&2 || true
    exit "$rc"
  fi
  ui_ok "$label"
}

ui_title

if [[ "$MODE" == "install" ]]; then
  run_quiet "Menyiapkan Termux" env DEBIAN_FRONTEND=noninteractive pkg update -y
fi
run_quiet "Menyiapkan runtime Furina" env DEBIAN_FRONTEND=noninteractive pkg install -y python python-pip git cmake ninja clang make curl ccache util-linux termux-tools patch gum
run_quiet "Menyiapkan tampilan" python -m pip install --quiet 'rich>=13.9,<15'

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
  local target="$ROOT/models/$1" url="$2" sha="$3" label="${4:-$1}"
  if [[ -s "$target" ]] && echo "$sha  $target" | sha256sum -c - >/dev/null 2>&1; then
    ui_ok "$label"
    return
  fi
  rm -f "$target.part"
  ui_info "$label"
  curl -L --fail --retry 4 --progress-bar "$url" -o "$target.part"
  echo "$sha  $target.part" | sha256sum -c - >/dev/null
  mv "$target.part" "$target"
  ui_ok "$label"
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
if manifest.get('revision')!='companion-v7':
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
    "$UI_RC10_TRANSFORM_URL|$UI_RC10_TRANSFORM_BLOB|apply-ui-rc10.py"; do
    IFS='|' read -r url blob name <<< "$spec"
    curl -fsSL --retry 3 "$url" -o "$TMP/$name"
    verify_git_blob "$TMP/$name" "$blob"
    python "$TMP/$name" "$TMP/src/termux" >/dev/null
  done

  SRC="$TMP/src/termux"
  test -f "$SRC/core/furina_agent/cli.py"
  for file in memory.py response.py vision.py embeddings.py local_vision.py events.py naturalness.py prospective.py device_context.py fastpath.py lexicon.py version.py tui.py; do
    test -f "$SRC/core/furina_agent/$file"
  done
  grep -q 'VERSION = "1.0.0-rc10"' "$SRC/core/furina_agent/version.py"
  grep -q 'config_revision: int = 9' "$SRC/core/furina_agent/config.py"
  grep -q 'fast_path_enabled: bool = True' "$SRC/core/furina_agent/config.py"
  grep -q 'lexicon_enabled: bool = True' "$SRC/core/furina_agent/config.py"
  grep -q 'CREATE TABLE IF NOT EXISTS personal_lexicon' "$SRC/core/furina_agent/lexicon.py"
  grep -q 'def _gum() -> str | None:' "$SRC/core/furina_agent/tui.py"
  grep -q '\["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"\]' "$SRC/core/furina_agent/tui.py"
  grep -q 'compile_fast_contract' "$SRC/core/furina_agent/agent.py"
  grep -q '_try_fast_skill' "$SRC/core/furina_agent/agent.py"
  grep -q 'LocalVision' "$SRC/core/furina_agent/routing.py"
  grep -q 'waitForExactText' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
  grep -q 'versionCode 10007' "$SRC/bridge/app/build.gradle"

  rm -rf "$ROOT/core.new"
  mkdir -p "$ROOT/core.new"
  cp -R "$SRC/core/furina_agent" "$ROOT/core.new/"
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

run_quiet "Memasang Furina Core RC10" prepare_core

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
    JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
    [[ "$JOBS" -gt 6 ]] && JOBS=6
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

run_quiet "Menyiapkan local engine" prepare_llama

MODEL_CURRENT="$(PYTHONPATH="$ROOT/core" python - <<'PY'
from furina_agent.config import load_config
from pathlib import Path
p=load_config().model_path
print(p if p and Path(p).is_file() else '')
PY
)"

if [[ -n "$MODEL_CURRENT" ]]; then
  ui_ok "Model chat dipertahankan"
elif [[ "$MODE" == "update" || "$NO_MODEL" -eq 1 ]]; then
  ui_info "Model chat utama tidak diubah"
else
  TARGET="$ROOT/models/$MODEL_NAME"
  if [[ ! -s "$TARGET" ]]; then
    ui_info "Model chat lokal · 2.7 GB"
    curl -L --fail --retry 4 --progress-bar "$MODEL_URL" -o "$TARGET.part"
    GOT_BYTES="$(wc -c < "$TARGET.part" | tr -d ' ')"
    GOT_SHA="$(sha256sum "$TARGET.part" | awk '{print $1}')"
    [[ "$GOT_BYTES" == "$MODEL_BYTES" ]] || { echo "Ukuran model salah" >&2; exit 1; }
    [[ "$GOT_SHA" == "$MODEL_SHA256" ]] || { echo "SHA-256 model salah" >&2; exit 1; }
    mv "$TARGET.part" "$TARGET"
  fi
  furina model "$TARGET" >>"$LOG" 2>&1
  ui_ok "Model chat lokal"
fi

if [[ "$NO_MODEL" -eq 0 ]]; then
  fetch_model_checked "$EMBED_NAME" "$EMBED_URL" "$EMBED_SHA256" "Semantic memory"
  fetch_model_checked "$VISION_NAME" "$VISION_URL" "$VISION_SHA256" "Local vision"
  fetch_model_checked "$MMPROJ_NAME" "$MMPROJ_URL" "$MMPROJ_SHA256" "Vision projector"
else
  ui_info "Cognition model dilewati (--no-model)"
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

run_quiet "Memeriksa Furina Bridge" prepare_bridge

verify_install() {
  PYTHONPATH="$ROOT/core" python -m compileall -q "$ROOT/core/furina_agent"
  furina status >/dev/null || true
  command -v gum >/dev/null
}
run_quiet "Verifikasi akhir" verify_install

printf '\n'
ui_ok "Furina siap"
if [[ "$MODE" == "install" ]]; then
  printf '\033[2mBuka dengan:\033[0m  \033[1;36mfurina\033[0m\n'
else
  printf '\033[2mRC10 sudah terpasang. Jalankan:\033[0m  \033[1;36mfurina\033[0m\n'
fi
printf '\033[2mLog setup: %s\033[0m\n\n' "$LOG"
