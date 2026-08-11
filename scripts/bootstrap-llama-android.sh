#!/usr/bin/env bash
set -euo pipefail

LLAMA_COMMIT="7ba604f1cb61cd14898138e9abc0b4ff2601f180"
RUNTIME_PATCH_REV="offline-v6.0-hexagon"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/furina-llama.cpp"
SDK_WORK="${TMPDIR:-/tmp}/furina-mobile-gpu-sdk"
OPENCL_WORK="$SDK_WORK/opencl"
VULKAN_HEADERS_PREFIX="$SDK_WORK/vulkan-headers"
LOG="$ROOT/gradle-build.log"
HEXAGON_EXPECTED=0
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must point to the Android NDK}"

prepare_host_gpu_tools() {
  if command -v glslc >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1 && \
     [[ -d /usr/share/cmake/SPIRV-Headers ]] && [[ -f /usr/include/vulkan/vulkan.hpp ]] && \
     [[ -f /usr/include/spirv/unified1/spirv.hpp ]]; then
    return
  fi
  if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y glslc spirv-headers ninja-build libvulkan-dev
  else
    echo "Vulkan build requires glslc, Vulkan-Hpp, SPIR-V headers and Ninja on the host." >&2
    exit 1
  fi
}

prepare_vulkan_headers() {
  rm -rf "$VULKAN_HEADERS_PREFIX"
  mkdir -p "$VULKAN_HEADERS_PREFIX/vulkan" "$VULKAN_HEADERS_PREFIX/spirv"
  cp -a /usr/include/vulkan/. "$VULKAN_HEADERS_PREFIX/vulkan/"
  cp -a /usr/include/spirv/. "$VULKAN_HEADERS_PREFIX/spirv/"
  test -s "$VULKAN_HEADERS_PREFIX/vulkan/vulkan.hpp"
  test -s "$VULKAN_HEADERS_PREFIX/spirv/unified1/spirv.hpp"
  export FURINA_VULKAN_HEADERS="$VULKAN_HEADERS_PREFIX"
  echo "Prepared isolated Vulkan-Hpp + SPIR-V headers at $FURINA_VULKAN_HEADERS"
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
prepare_vulkan_headers
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
python3 "$ROOT/scripts/fix-offline-backend-cpp-includes.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
python3 "$ROOT/scripts/apply-hexagon-runtime-env-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/ai_chat.cpp"
python3 "$ROOT/scripts/apply-mobile-gpu-build-policy.py" \
  "$WORK/examples/llama.android/lib/src/main/cpp/CMakeLists.txt"

echo "Applying Furina runtime patch revision: $RUNTIME_PATCH_REV"

# Build the experimental Qualcomm HTP plugin only where Docker is available. GitHub-hosted
# Linux runners satisfy this path; local Android developers retain CPU/Vulkan/OpenCL fallback.
HEXAGON_OUT="$WORK/examples/llama.android/lib/src/main/jniLibs/arm64-v8a"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Building optional Snapdragon Hexagon/HTP runtime from pinned llama.cpp..."
  bash "$ROOT/scripts/build-hexagon-runtime.sh" "$WORK" "$HEXAGON_OUT"
  HEXAGON_EXPECTED=1
else
  echo "Docker unavailable; skipping optional Hexagon backend. CPU/Vulkan/OpenCL remain enabled."
fi

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
AAR="$ROOT/android-wrapper/app/libs/llama-android.aar"
cp "$WORK/examples/llama.android/lib/build/outputs/aar/lib-release.aar" "$AAR"

# The Khronos ICD loader is used only to satisfy the cross-link. Runtime must resolve the
# Qualcomm vendor libOpenCL.so declared optional in AndroidManifest, not ship our temporary ICD.
if unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libOpenCL.so'; then
  zip -q -d "$AAR" 'jni/arm64-v8a/libOpenCL.so'
fi

# Fail closed if Gradle ever stops packaging the actual dynamic accelerator modules.
unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libggml-vulkan.so'
unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libggml-opencl.so'
unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libggml-cpu'
if [[ "$HEXAGON_EXPECTED" -eq 1 ]]; then
  unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libggml-hexagon.so'
  for arch in v73 v75 v79 v81; do
    unzip -l "$AAR" | grep -q "jni/arm64-v8a/libggml-htp-${arch}.so"
  done
fi
if unzip -l "$AAR" | grep -q 'jni/arm64-v8a/libOpenCL.so'; then
  echo "Refusing AAR that still bundles the temporary OpenCL ICD loader" >&2
  exit 1
fi

echo "Pinned llama.cpp Android AAR installed with CPU + Vulkan + OpenCL$([[ "$HEXAGON_EXPECTED" -eq 1 ]] && echo ' + Hexagon/HTP') modules at $AAR"
