#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc4"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
RUNTIME_PATCH_URL="$BASE/patches/runtime-online-agent.patch"
RUNTIME_PATCH_SHA256="bef40bd02af2eb9714f1197337a0f1a5f3ad5fa9ff1e71adfa073141c3756549"
OVERRIDE_MANIFEST_URL="$BASE/overrides/manifest.json"
OVERRIDE_MANIFEST_BLOB="9bd5616020dd3f7755c7f168d8e8658c26d9228a"
TRANSFORM_URL="$BASE/overrides/apply-companion-v2.py"
TRANSFORM_BLOB="cfd65bcfdfd930518ae75e8d44e34559a0f33914"
BRIDGE_TRANSFORM_URL="$BASE/overrides/apply-bridge-rc4.py"
BRIDGE_TRANSFORM_BLOB="aa7444fdb843c6d707925e5a62d5189e2b4fbb64"
LLAMA_REV="f785fc9ea485e6cfdda129978310aa52939c3619"
MODEL_REV="e9cf779"
MODEL_NAME="Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking.i1-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/mradermacher/Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking-i1-GGUF/resolve/$MODEL_REV/$MODEL_NAME?download=true"
MODEL_SHA256="dda8f686b793f189a84c854832bb8b4db59c381a60275a567513d5ebb4d92906"
MODEL_BYTES="2708805792"
MODE="install"
NO_MODEL=0
[[ -f "$ROOT/config.json" ]] && MODE="update"
[[ "${1:-}" == "--update" ]] && MODE="update"
[[ "${1:-}" == "--no-model" || "${2:-}" == "--no-model" ]] && NO_MODEL=1

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

printf '\nFurina Agent %s by Wynn\n' "$VERSION"
printf 'Mode: %s\n\n' "$MODE"

printf '[1/7] Menyiapkan Termux...\n'
pkg update -y
pkg install -y python python-pip git cmake ninja clang make curl ccache util-linux termux-tools patch
python -m pip install --quiet 'rich>=13.9,<15'
mkdir -p "$ROOT"/{bin,models,logs,run,data,cache}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

printf '[2/7] Mengambil Furina Core final...\n'
curl -fsSL --retry 3 "$MANIFEST_URL" -o "$TMP/manifest.json"
python - "$TMP/manifest.json" "$BASE" "$TMP" <<'PY'
import base64, hashlib, json, pathlib, sys, urllib.request
manifest_path, base, tmp = sys.argv[1:]
m = json.load(open(manifest_path, encoding='utf-8'))
out = pathlib.Path(tmp) / 'source.tar.gz'
h = hashlib.sha256()
with out.open('wb') as dst:
    for name in m['source_chunks']:
        encoded = urllib.request.urlopen(base + '/' + name, timeout=30).read()
        raw = base64.b64decode(encoded)
        dst.write(raw)
        h.update(raw)
if h.hexdigest() != m['source_sha256']:
    raise SystemExit('Checksum Furina Core tidak cocok; update dibatalkan.')
PY
mkdir -p "$TMP/src"
tar -xzf "$TMP/source.tar.gz" -C "$TMP/src"

curl -fsSL --retry 3 "$RUNTIME_PATCH_URL" -o "$TMP/runtime-online-agent.patch"
echo "$RUNTIME_PATCH_SHA256  $TMP/runtime-online-agent.patch" | sha256sum -c -
patch -p0 -d "$TMP/src" < "$TMP/runtime-online-agent.patch"

curl -fsSL --retry 3 "$OVERRIDE_MANIFEST_URL" -o "$TMP/override-manifest.json"
python - "$TMP/override-manifest.json" "$OVERRIDE_MANIFEST_BLOB" "$BASE" "$TMP/src/termux" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
manifest_path, expected_manifest_blob, base, termux_root = sys.argv[1:]
manifest_raw = pathlib.Path(manifest_path).read_bytes()

def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()

if git_blob_sha(manifest_raw) != expected_manifest_blob:
    raise SystemExit('Manifest override Furina berubah; update dibatalkan.')
manifest = json.loads(manifest_raw.decode('utf-8'))
if manifest.get('revision') != 'companion-v2':
    raise SystemExit('Revision override Furina tidak dikenali.')
root = pathlib.Path(termux_root).resolve()
for item in manifest.get('files', []):
    rel = str(item['path'])
    target_rel = str(item['target'])
    if '..' in pathlib.PurePosixPath(rel).parts or '..' in pathlib.PurePosixPath(target_rel).parts:
        raise SystemExit('Path override tidak aman.')
    allowed = target_rel.startswith('core/furina_agent/') or target_rel.startswith('bridge/app/')
    if not allowed:
        raise SystemExit('Target override di luar area yang diizinkan ditolak.')
    data = urllib.request.urlopen(base + '/overrides/' + rel, timeout=30).read()
    if git_blob_sha(data) != str(item['git_blob_sha']):
        raise SystemExit('Integritas override gagal: ' + rel)
    target = (root / target_rel).resolve()
    if root not in target.parents:
        raise SystemExit('Target override keluar dari root.')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
print('Unified companion + Bridge overrides: OK')
PY

# Transformasi Core + Bridge RC3 lama tetap dipakai untuk selector UI stabil,
# verifikasi hasil aksi, dan ACTION_IME_ENTER.
curl -fsSL --retry 3 "$TRANSFORM_URL" -o "$TMP/apply-companion-v2.py"
python - "$TMP/apply-companion-v2.py" "$TRANSFORM_BLOB" <<'PY'
import hashlib, pathlib, sys
path, expected = sys.argv[1:]
data = pathlib.Path(path).read_bytes()
actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
if actual != expected:
    raise SystemExit(f'Transform companion-v2 berubah; update dibatalkan: {actual}')
PY
python "$TMP/apply-companion-v2.py" "$TMP/src/termux"

# RC4 menambahkan updater native Bridge dan menaikkan identitas APK.
curl -fsSL --retry 3 "$BRIDGE_TRANSFORM_URL" -o "$TMP/apply-bridge-rc4.py"
python - "$TMP/apply-bridge-rc4.py" "$BRIDGE_TRANSFORM_BLOB" <<'PY'
import hashlib, pathlib, sys
path, expected = sys.argv[1:]
data = pathlib.Path(path).read_bytes()
actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
if actual != expected:
    raise SystemExit(f'Transform Bridge RC4 berubah; update dibatalkan: {actual}')
PY
python "$TMP/apply-bridge-rc4.py" "$TMP/src/termux"

SRC="$TMP/src/termux"
test -f "$SRC/core/furina_agent/cli.py"
grep -q 'free = low.endswith(":free") or bool(' "$SRC/core/furina_agent/providers.py"
grep -q 'reasoning_effort.*none' "$SRC/core/furina_agent/providers.py"
grep -q 'Percakapan + tindakan Android' "$SRC/core/furina_agent/tui.py"
grep -q '_obvious_device_intent' "$SRC/core/furina_agent/companion.py"
grep -q 'json_mode=True' "$SRC/core/furina_agent/agent.py"
grep -q 'ime_action' "$SRC/core/furina_agent/agent.py"
grep -q 'payload\["target"\] = selector' "$SRC/core/furina_agent/agent.py"
grep -q 'needs_approval = (not task_authorized)' "$SRC/core/furina_agent/agent.py"
grep -q 'selectorScore' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
grep -q 'ACTION_IME_ENTER' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java"
grep -q 'BridgeUpdater' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -q 'verifyArchive' "$SRC/bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
grep -q 'REQUEST_INSTALL_PACKAGES' "$SRC/bridge/app/src/main/AndroidManifest.xml"
grep -q 'UpdateFileProvider' "$SRC/bridge/app/src/main/AndroidManifest.xml"
grep -q 'versionCode 10004' "$SRC/bridge/app/build.gradle"

printf '[3/7] Memasang Core secara atomik...\n'
rm -rf "$ROOT/core.new"
mkdir -p "$ROOT/core.new"
cp -R "$SRC/core/furina_agent" "$ROOT/core.new/"
if [[ -d "$ROOT/core" ]]; then rm -rf "$ROOT/core.prev"; mv "$ROOT/core" "$ROOT/core.prev"; fi
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

printf '[4/7] Menyiapkan llama.cpp yang dipin + optimasi ARM...\n'
LLAMA="$ROOT/llama.cpp"
if [[ ! -d "$LLAMA/.git" ]]; then
  git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$LLAMA"
fi
CURRENT="$(git -C "$LLAMA" rev-parse HEAD 2>/dev/null || true)"
if [[ "$CURRENT" != "$LLAMA_REV" ]]; then
  git -C "$LLAMA" fetch --depth 1 origin "$LLAMA_REV"
  git -C "$LLAMA" checkout --detach "$LLAMA_REV"
fi
BUILD_MARKER="$ROOT/data/llama-build-$LLAMA_REV-kleidiai"
if [[ ! -x "$LLAMA/build/bin/llama-server" || ! -x "$LLAMA/build/bin/llama-bench" || ! -f "$BUILD_MARKER" ]]; then
  rm -rf "$LLAMA/build"
  JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"; [[ "$JOBS" -gt 6 ]] && JOBS=6
  if cmake -S "$LLAMA" -B "$LLAMA/build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=OFF \
      -DGGML_CPU_KLEIDIAI=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_OPENSSL=OFF \
      && cmake --build "$LLAMA/build" --target llama-server llama-cli llama-bench -j "$JOBS"; then
    echo "KleidiAI ARM runtime siap."
  else
    echo "KleidiAI build tidak kompatibel di environment ini; fallback ke CPU native stabil."
    rm -rf "$LLAMA/build"
    cmake -S "$LLAMA" -B "$LLAMA/build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=OFF \
      -DLLAMA_BUILD_UI=OFF -DLLAMA_OPENSSL=OFF
    cmake --build "$LLAMA/build" --target llama-server llama-cli llama-bench -j "$JOBS"
  fi
  touch "$BUILD_MARKER"
fi

printf '[5/7] Memeriksa model lokal...\n'
MODEL_CURRENT="$(PYTHONPATH="$ROOT/core" python - <<'PY'
from furina_agent.config import load_config
from pathlib import Path
p=load_config().model_path
print(p if p and Path(p).is_file() else '')
PY
)"
if [[ -n "$MODEL_CURRENT" ]]; then
  echo "Model yang sudah ada dipertahankan: $MODEL_CURRENT"
elif [[ "$MODE" == "update" || "$NO_MODEL" -eq 1 ]]; then
  echo "Model tidak diubah."
else
  TARGET="$ROOT/models/$MODEL_NAME"
  if [[ ! -s "$TARGET" ]]; then
    echo "Mengunduh model lokal terverifikasi (~2.7 GB)..."
    curl -L --fail --retry 4 --progress-bar "$MODEL_URL" -o "$TARGET.part"
    GOT_BYTES="$(wc -c < "$TARGET.part" | tr -d ' ')"
    GOT_SHA="$(sha256sum "$TARGET.part" | awk '{print $1}')"
    [[ "$GOT_BYTES" == "$MODEL_BYTES" ]] || { echo "Ukuran model salah" >&2; exit 1; }
    [[ "$GOT_SHA" == "$MODEL_SHA256" ]] || { echo "SHA-256 model salah" >&2; exit 1; }
    mv "$TARGET.part" "$TARGET"
  fi
  furina model "$TARGET"
fi

printf '[6/7] Memeriksa Furina Bridge...\n'
BRIDGE_VERSION="$(curl -fsS --max-time 2 http://127.0.0.1:8765/health 2>/dev/null | python -c 'import json,sys; print(json.load(sys.stdin).get("version", ""))' 2>/dev/null || true)"
EXPECTED_BRIDGE="$(python -c 'import json; print(json.load(open("'"$TMP"'/manifest.json"))["bridge_version"])')"
if [[ "$BRIDGE_VERSION" == "$EXPECTED_BRIDGE" ]]; then
  echo "Bridge final sudah terpasang."
  furina connect >/dev/null 2>&1 || true
else
  echo "Bridge final perlu dipasang/update: $EXPECTED_BRIDGE"
  RELEASE_BASE="$(python -c 'import json; print(json.load(open("'"$TMP"'/manifest.json"))["bridge_release_base"])')"
  curl -fsSL --retry 3 "$RELEASE_BASE/bridge.json" -o "$TMP/bridge.json"
  APK_URL="$(python -c 'import json; print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  APK_SHA="$(python -c 'import json; print(json.load(open("'"$TMP"'/bridge.json"))["sha256"])')"
  curl -fL --retry 3 "$APK_URL" -o "$ROOT/cache/Furina-Agent-Bridge.apk"
  echo "$APK_SHA  $ROOT/cache/Furina-Agent-Bridge.apk" | sha256sum -c -
  echo
  echo "APK rilis sudah diverifikasi. Karena HyperOS gagal membaca APK dari direktori privat Termux, unduhan resmi akan dibuka melalui browser."
  echo "Setelah Bridge RC4 terpasang, update Bridge berikutnya dapat dilakukan langsung dari menu UPDATE di Furina Bridge."
  if [[ "$BRIDGE_VERSION" == "0.1.1" || "$BRIDGE_VERSION" == "0.2.0" ]]; then
    echo "CATATAN SEKALI SAJA: Bridge prototipe lama memakai debug signature. Jika Android berkata aplikasi bentrok/tidak dapat di-update, uninstall HANYA Furina Bridge lama lalu install APK rilis resmi."
  fi
  termux-open-url "$APK_URL" >/dev/null 2>&1 || true
fi

printf '[7/7] Final checks...\n'
furina status >/dev/null || true
printf '\nSelesai.\n'
printf 'Pemakaian harian: buka Termux lalu ketik: furina\n'
printf 'Update Core berikutnya: furina update\n'
printf 'Update Bridge berikutnya: buka Furina Bridge → UPDATE → Perbarui\n'
printf 'Perbaikan: furina repair\n'
printf 'Optimasi model lokal berdasarkan HP: furina optimize\n\n'
