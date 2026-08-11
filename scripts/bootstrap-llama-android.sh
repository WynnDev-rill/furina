#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
RUNTIME_PATCH_REV="offline-v5.0-mobile-accelerators"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"
OPENCL_WORK="${TMPDIR:-/tmp}/furina-opencl-sdk"
LOG="$ROOT/gradle-build.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must point to the Android NDK}"

prepare_host_gpu_tools() {
  if command -v glslc >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1 && \
     [[ -d /usr/share/cmake/SPIRV-Headers ]]; then
    return
  fi
  if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y glslc spirv-headers ninja-build
  else
    echo "Vulkan build requires glslc, SPIRV-Headers and Ninja on the host." >&2
    exit 1
  fi
}

prepare_opencl_sdk() {
  rm -rf "$OPENCL_WORK"
  mkdir -p "$OPENCL_WORK/prefix"

  git clone --depth 1 https://github.com/KhronosGroup/OpenCL-Headers.git "$OPENCL_WORK/headers"
  cmake -S "$OPENCL_WORK/headers" -B "$OPENCL_WORK/headers-build" -G Ninja \
    -DBUILD_TESTING=OFF \
    -DOPENCL_HEADERS_BUILD_TESTING=OFF \
    -DOPENCL_HEADERS_BUILD_CXX_TESTS=OFF \
    -DCMAKE_INSTALL_PREFIX="$OPENCL_WORK/prefix"
  cmake --build "$OPENCL_WORK/headers-build" --target install

  git clone --depth 1 https://github.com/KhronosGroup/OpenCL-ICD-Loader.git "$OPENCL_WORK/loader"
  cmake -S "$OPENCL_WORK/loader" -B "$OPENCL_WORK/loader-build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
    -DOPENCL_ICD_LOADER_HEADERS_DIR="$OPENCL_WORK/prefix/include" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=28 \
    -DANDROID_STL=c++_shared
  cmake --build "$OPENCL_WORK/loader-build"

  mkdir -p "$OPENCL_WORK/prefix/lib"
  cp "$OPENCL_WORK/loader-build/libOpenCL.so" "$OPENCL_WORK/prefix/lib/libOpenCL.so"
  export FURINA_OPENCL_PREFIX="$OPENCL_WORK/prefix"
  echo "Prepared Android OpenCL link SDK at $FURINA_OPENCL_PREFIX"
}

prepare_host_gpu_tools
prepare_opencl_sdk

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
python3 "$ROOT/scripts/fix-offline-runtime-v4-kotlin-regex.py" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-offline-checkpoint-chat-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
python3 "$ROOT/scripts/apply-offline-backend-autotune-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp" \
  "$WORK/examples/llama.android/lib/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt"
python3 "$ROOT/scripts/apply-mobile-gpu-build-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/CMakeLists.txt"

echo "Applying Furina runtime patch revision: $RUNTIME_PATCH_REV"

# Furina targets physical Android phones. Do not spend CI time or APK space on x86_64.
sed -i 's/listOf("arm64-v8a", "x86_64")/listOf("arm64-v8a")/' \
    "$WORK/examples/llama.android/lib/build.gradle.kts"

pushd "$WORK/examples/llama.android" >/dev/null
chmod +x gradlew
# GitHub's Gradle CDN can occasionally exceed the wrapper's short default read timeout.
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
