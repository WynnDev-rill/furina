#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"

rm -rf "$WORK"
git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$WORK"
git -C "$WORK" checkout "$LLAMA_COMMIT"

# Tune the official Android sample for modern 8-core phones. Four active KiB threads
# left performance on the table, while an 8K KV cache delayed model preparation and
# consumed memory that is more valuable to Android. Long-term memory stays in SQLite
# retrieval; the hot llama.cpp context is deliberately kept at 4K.
AI_CHAT_CPP="$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
sed -i 's/constexpr int   N_THREADS_MAX           = 4;/constexpr int   N_THREADS_MAX           = 6;/' "$AI_CHAT_CPP"
sed -i 's/constexpr int   DEFAULT_CONTEXT_SIZE    = 8192;/constexpr int   DEFAULT_CONTEXT_SIZE    = 4096;/' "$AI_CHAT_CPP"

pushd "$WORK/examples/llama.android" >/dev/null
chmod +x gradlew
./gradlew :lib:assembleRelease --no-daemon --stacktrace
popd >/dev/null

mkdir -p "$ROOT/android-wrapper/app/libs"
cp "$WORK/examples/llama.android/lib/build/outputs/aar/lib-release.aar" "$ROOT/android-wrapper/app/libs/llama-android.aar"

echo "Pinned llama.cpp Android AAR installed at android-wrapper/app/libs/llama-android.aar"
