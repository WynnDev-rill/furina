#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"

rm -rf "$WORK"
git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$WORK"
git -C "$WORK" checkout "$LLAMA_COMMIT"

pushd "$WORK/examples/llama.android" >/dev/null
chmod +x gradlew
./gradlew :lib:assembleRelease --no-daemon --stacktrace
popd >/dev/null

mkdir -p "$ROOT/android-wrapper/app/libs"
cp "$WORK/examples/llama.android/lib/build/outputs/aar/lib-release.aar" "$ROOT/android-wrapper/app/libs/llama-android.aar"

echo "Pinned llama.cpp Android AAR installed at android-wrapper/app/libs/llama-android.aar"
