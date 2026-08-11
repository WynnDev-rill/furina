#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: build-hexagon-runtime.sh <llama.cpp-source> <jniLibs-arm64-output>" >&2
  exit 2
fi

LLAMA_SRC="$(cd "$1" && pwd)"
OUT_DIR="$2"
IMAGE="ghcr.io/snapdragon-toolchain/arm64-android:v0.7"
BUILD_DIR="build-furina-hexagon"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required for the official Snapdragon Hexagon toolchain" >&2
  exit 3
}
docker info >/dev/null 2>&1 || {
  echo "Docker daemon is unavailable; cannot build Hexagon runtime" >&2
  exit 3
}

rm -rf "$LLAMA_SRC/$BUILD_DIR"
cp "$LLAMA_SRC/docs/backend/snapdragon/CMakeUserPresets.json" "$LLAMA_SRC/CMakeUserPresets.json"

# Use the upstream Snapdragon toolchain image and the preset shipped by the same pinned llama.cpp
# commit. Build only the five runtime targets Furina packages instead of the whole llama.cpp tree.
docker run --rm --pull=missing --platform linux/amd64 \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$LLAMA_SRC:/workspace" \
  -w /workspace \
  "$IMAGE" \
  bash -lc "
    set -euo pipefail
    cmake --preset arm64-android-snapdragon-release -B '$BUILD_DIR' \\
      -DGGML_BACKEND_DL=ON \\
      -DBUILD_SHARED_LIBS=ON \\
      -DGGML_OPENCL=OFF \\
      -DGGML_VULKAN=OFF \\
      -DGGML_RPC=OFF \\
      -DLLAMA_BUILD_TESTS=OFF \\
      -DLLAMA_BUILD_EXAMPLES=OFF \\
      -DLLAMA_BUILD_SERVER=OFF
    cmake --build '$BUILD_DIR' --config Release --target \\
      ggml-hexagon htp-v73 htp-v75 htp-v79 htp-v81 -j 2
  "

mkdir -p "$OUT_DIR"

copy_required() {
  local name="$1"
  local found
  found="$(find "$LLAMA_SRC/$BUILD_DIR" -type f -name "$name" -print -quit)"
  if [[ -z "$found" ]]; then
    echo "Hexagon build did not produce required $name" >&2
    exit 4
  fi
  cp "$found" "$OUT_DIR/$name"
}

copy_required libggml-hexagon.so
copy_required libggml-htp-v73.so
copy_required libggml-htp-v75.so
copy_required libggml-htp-v79.so
copy_required libggml-htp-v81.so

# The plugin must consume the libggml-base already packaged by Furina's main pinned AAR build.
# Do not copy a second base/CPU runtime from the Snapdragon build.
for f in "$OUT_DIR"/libggml-hexagon.so "$OUT_DIR"/libggml-htp-v*.so; do
  test -s "$f"
done

echo "Prepared Hexagon/HTP runtime modules in $OUT_DIR"
