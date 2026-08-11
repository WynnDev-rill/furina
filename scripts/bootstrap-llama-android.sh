#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"

rm -rf "$WORK"
git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$WORK"
git -C "$WORK" checkout "$LLAMA_COMMIT"

# Overlay the audited Android sample runtime, then apply Furina's deterministic
# companion and mobile stability policies. All patches fail closed if the
# pinned source layout changes.
cp "$ROOT/scripts/overlays/ai_chat.cpp" "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
cp "$ROOT/scripts/overlays/InferenceEngineImpl.kt" "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-companion-runtime-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-offline-stability-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-warm-session-reset-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/InferenceEngine.kt" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"

# Furina targets physical Android phones. Do not spend CI time or APK space on
# the x86_64 emulator backend; every supported device here is arm64.
sed -i 's/listOf("arm64-v8a", "x86_64")/listOf("arm64-v8a")/' \
    "$WORK/examples/llama.android/lib/build.gradle.kts"

pushd "$WORK/examples/llama.android" >/dev/null
chmod +x gradlew
./gradlew :lib:assembleRelease --no-daemon --stacktrace
popd >/dev/null

mkdir -p "$ROOT/android-wrapper/app/libs"
cp "$WORK/examples/llama.android/lib/build/outputs/aar/lib-release.aar" "$ROOT/android-wrapper/app/libs/llama-android.aar"

echo "Pinned llama.cpp Android AAR installed at android-wrapper/app/libs/llama-android.aar"
