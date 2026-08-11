#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
RUNTIME_PATCH_REV="offline-v4.7"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"
LOG="$ROOT/gradle-build.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

rm -rf "$WORK"
git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git "$WORK"
git -C "$WORK" checkout "$LLAMA_COMMIT"

# Overlay the audited Android sample runtime, then apply deterministic policies in order.
# Every patch fails closed if the pinned upstream layout changes.
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
python3 "$ROOT/scripts/normalize-offline-runtime-v4-input.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
python3 "$ROOT/scripts/apply-offline-runtime-v4-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/InferenceEngine.kt" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-offline-checkpoint-chat-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"

echo "Applying Furina runtime patch revision: $RUNTIME_PATCH_REV"

# Furina targets physical Android phones. Do not spend CI time or APK space on x86_64.
sed -i 's/listOf("arm64-v8a", "x86_64")/listOf("arm64-v8a")/' \
    "$WORK/examples/llama.android/lib/build.gradle.kts"

pushd "$WORK/examples/llama.android" >/dev/null
chmod +x gradlew
# GitHub's Gradle CDN can occasionally exceed the wrapper's short default read timeout.
# Keep the pinned distribution but allow enough time for one large download and retry transient I/O.
printf '\nnetworkTimeout=120000\n' >> gradle/wrapper/gradle-wrapper.properties
for attempt in 1 2 3; do
  if ./gradlew :lib:assembleRelease --no-daemon --stacktrace; then
    break
  fi
  if [[ "$attempt" -eq 3 ]]; then
    echo "Pinned llama.android Gradle build failed after $attempt attempts" >&2
    exit 1
  fi
  echo "Gradle attempt $attempt failed; retrying in $((attempt * 8))s..." >&2
  sleep $((attempt * 8))
done
popd >/dev/null

mkdir -p "$ROOT/android-wrapper/app/libs"
cp "$WORK/examples/llama.android/lib/build/outputs/aar/lib-release.aar" "$ROOT/android-wrapper/app/libs/llama-android.aar"

echo "Pinned llama.cpp Android AAR installed at android-wrapper/app/libs/llama-android.aar"
