#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc1"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
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
pkg install -y python python-pip git cmake ninja clang make curl ccache util-linux termux-tools
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
SRC="$TMP/src/termux"
test -f "$SRC/core/furina_agent/cli.py"

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
EXPECTED_BRIDGE="$(python -c 'import json; print(json.load(open("'$TMP'/manifest.json"))["bridge_version"])')"
if [[ "$BRIDGE_VERSION" == "$EXPECTED_BRIDGE" ]]; then
  echo "Bridge final sudah terpasang."
  furina connect >/dev/null 2>&1 || true
else
  echo "Bridge final perlu dipasang/update: $EXPECTED_BRIDGE"
  RELEASE_BASE="$(python -c 'import json; print(json.load(open("'$TMP'/manifest.json"))["bridge_release_base"])')"
  curl -fsSL --retry 3 "$RELEASE_BASE/bridge.json" -o "$TMP/bridge.json"
  APK_URL="$(python -c 'import json; print(json.load(open("'$TMP'/bridge.json"))["apk_url"])')"
  APK_SHA="$(python -c 'import json; print(json.load(open("'$TMP'/bridge.json"))["sha256"])')"
  curl -fL --retry 3 "$APK_URL" -o "$ROOT/cache/Furina-Agent-Bridge.apk"
  echo "$APK_SHA  $ROOT/cache/Furina-Agent-Bridge.apk" | sha256sum -c -
  echo
  echo "Android installer akan dibuka."
  if [[ "$BRIDGE_VERSION" == "0.1.1" || "$BRIDGE_VERSION" == "0.2.0" ]]; then
    echo "CATATAN SEKALI SAJA: Bridge prototipe lama memakai debug signature. Jika Android berkata aplikasi bentrok/tidak dapat di-update, uninstall HANYA Furina Bridge lama lalu install file yang sama. Setelah final ini, update berikutnya memakai signing tetap."
  fi
  termux-open "$ROOT/cache/Furina-Agent-Bridge.apk" >/dev/null 2>&1 || true
fi

printf '[7/7] Final checks...\n'
furina status >/dev/null || true
printf '\nSelesai.\n'
printf 'Pemakaian harian: buka Termux lalu ketik: furina\n'
printf 'Update berikutnya: furina update\n'
printf 'Perbaikan: furina repair\n'
printf 'Optimasi model lokal berdasarkan HP: furina optimize\n\n'
