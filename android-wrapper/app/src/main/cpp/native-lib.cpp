#include <jni.h>
#include <android/log.h>
#include <algorithm>
#include <atomic>
#include <mutex>
#include <string>
#include <vector>

#include "llama.h"
#include "mtmd.h"
#include "mtmd-helper.h"

#define LOG_TAG "FurinaLLM"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace {
std::mutex g_mutex;
llama_model * g_model = nullptr;
std::string g_model_path;
std::atomic<bool> g_cancelled{false};
bool g_backend_initialized = false;

void ensure_backend() {
    if (!g_backend_initialized) {
        llama_backend_init();
        g_backend_initialized = true;
    }
}

void unload_locked() {
    if (g_model != nullptr) {
        llama_model_free(g_model);
        g_model = nullptr;
    }
    g_model_path.clear();
}

void call_string(JNIEnv * env, jobject listener, jmethodID method, const std::string & value) {
    jstring text = env->NewStringUTF(value.c_str());
    env->CallVoidMethod(listener, method, text);
    env->DeleteLocalRef(text);
}

std::string jstring_value(JNIEnv * env, jstring value) {
    if (value == nullptr) return {};
    const char * raw = env->GetStringUTFChars(value, nullptr);
    std::string result(raw ? raw : "");
    if (raw) env->ReleaseStringUTFChars(value, raw);
    return result;
}

std::string token_piece(const llama_vocab * vocab, llama_token token) {
    std::vector<char> buffer(32);
    int32_t written = llama_token_to_piece(vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    if (written < 0) {
        buffer.resize(static_cast<size_t>(-written));
        written = llama_token_to_piece(vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    }
    if (written <= 0) return {};
    return std::string(buffer.data(), static_cast<size_t>(written));
}

llama_context * create_context(int context_size, int thread_count) {
    llama_context_params params = llama_context_default_params();
    params.n_ctx = static_cast<uint32_t>(std::max(2048, context_size));
    params.n_batch = 512;
    params.n_ubatch = 512;
    params.n_threads = std::max(2, thread_count);
    params.n_threads_batch = std::max(2, thread_count);
    params.no_perf = true;
    return llama_init_from_model(g_model, params);
}

llama_sampler * create_sampler(float temperature) {
    llama_sampler_chain_params chain_params = llama_sampler_chain_default_params();
    llama_sampler * sampler = llama_sampler_chain_init(chain_params);
    llama_sampler_chain_add(sampler, llama_sampler_init_top_k(40));
    llama_sampler_chain_add(sampler, llama_sampler_init_top_p(0.92f, 1));
    llama_sampler_chain_add(sampler, llama_sampler_init_min_p(0.05f, 1));
    llama_sampler_chain_add(sampler, llama_sampler_init_temp(std::clamp(temperature, 0.1f, 1.5f)));
    llama_sampler_chain_add(sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
    return sampler;
}

bool stream_generation(
        JNIEnv * env,
        jobject listener,
        jmethodID on_token,
        jmethodID on_error,
        llama_context * context,
        int max_tokens,
        float temperature) {
    const llama_vocab * vocab = llama_model_get_vocab(g_model);
    llama_sampler * sampler = create_sampler(temperature);

    for (int generated = 0; generated < max_tokens && !g_cancelled.load(); ++generated) {
        llama_token token = llama_sampler_sample(sampler, context, -1);
        if (llama_vocab_is_eog(vocab, token)) break;

        llama_sampler_accept(sampler, token);
        std::string piece = token_piece(vocab, token);
        if (!piece.empty()) call_string(env, listener, on_token, piece);

        llama_token next_token = token;
        llama_batch next_batch = llama_batch_get_one(&next_token, 1);
        if (llama_decode(context, next_batch) != 0) {
            llama_sampler_free(sampler);
            call_string(env, listener, on_error, "Generasi berhenti karena decoder gagal.");
            return false;
        }
    }

    llama_sampler_free(sampler);
    return true;
}
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeLoad(
        JNIEnv * env,
        jclass,
        jstring path) {
    std::string requested = jstring_value(env, path);

    std::lock_guard<std::mutex> lock(g_mutex);
    ensure_backend();

    if (g_model != nullptr && g_model_path == requested) return JNI_TRUE;
    unload_locked();

    llama_model_params params = llama_model_default_params();
    params.n_gpu_layers = 0;

    g_model = llama_model_load_from_file(requested.c_str(), params);
    if (g_model == nullptr) {
        LOGE("Failed to load model: %s", requested.c_str());
        return JNI_FALSE;
    }
    g_model_path = requested;
    return JNI_TRUE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeUnload(JNIEnv *, jclass) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_cancelled.store(true);
    unload_locked();
}

extern "C" JNIEXPORT void JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeCancel(JNIEnv *, jclass) {
    g_cancelled.store(true);
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeIsLoaded(JNIEnv *, jclass) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model != nullptr ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeGenerate(
        JNIEnv * env,
        jclass,
        jstring prompt,
        jint max_tokens,
        jfloat temperature,
        jint context_size,
        jint thread_count,
        jobject listener) {
    jclass listener_class = env->GetObjectClass(listener);
    jmethodID on_token = env->GetMethodID(listener_class, "onToken", "(Ljava/lang/String;)V");
    jmethodID on_complete = env->GetMethodID(listener_class, "onComplete", "()V");
    jmethodID on_error = env->GetMethodID(listener_class, "onError", "(Ljava/lang/String;)V");
    std::string prompt_text = jstring_value(env, prompt);

    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model == nullptr) {
        call_string(env, listener, on_error, "Model belum dimuat.");
        return;
    }

    g_cancelled.store(false);
    const llama_vocab * vocab = llama_model_get_vocab(g_model);
    int32_t token_count = llama_tokenize(vocab, prompt_text.c_str(), static_cast<int32_t>(prompt_text.size()), nullptr, 0, true, true);
    if (token_count >= 0) {
        call_string(env, listener, on_error, "Tokenizer gagal menghitung token prompt.");
        return;
    }

    std::vector<llama_token> prompt_tokens(static_cast<size_t>(-token_count));
    token_count = llama_tokenize(vocab, prompt_text.c_str(), static_cast<int32_t>(prompt_text.size()), prompt_tokens.data(), static_cast<int32_t>(prompt_tokens.size()), true, true);
    if (token_count <= 0) {
        call_string(env, listener, on_error, "Prompt tidak dapat diproses.");
        return;
    }
    prompt_tokens.resize(static_cast<size_t>(token_count));

    int32_t n_ctx = std::max<int32_t>(2048, context_size);
    if (static_cast<int32_t>(prompt_tokens.size()) + max_tokens + 32 > n_ctx) {
        call_string(env, listener, on_error, "Percakapan terlalu panjang untuk konteks model saat ini.");
        return;
    }

    llama_context * context = create_context(n_ctx, thread_count);
    if (context == nullptr) {
        call_string(env, listener, on_error, "RAM perangkat tidak cukup untuk membuat konteks model.");
        return;
    }

    llama_batch batch = llama_batch_get_one(prompt_tokens.data(), static_cast<int32_t>(prompt_tokens.size()));
    if (llama_decode(context, batch) != 0) {
        llama_free(context);
        call_string(env, listener, on_error, "Model gagal membaca prompt.");
        return;
    }

    if (!stream_generation(env, listener, on_token, on_error, context, max_tokens, temperature)) {
        llama_free(context);
        return;
    }

    llama_free(context);
    env->CallVoidMethod(listener, on_complete);
}

extern "C" JNIEXPORT void JNICALL
Java_com_wynndev_furina_OfflineModelEngine_nativeGenerateVision(
        JNIEnv * env,
        jclass,
        jstring prompt,
        jstring image_path,
        jstring mmproj_path,
        jint max_tokens,
        jfloat temperature,
        jint context_size,
        jint thread_count,
        jobject listener) {
    jclass listener_class = env->GetObjectClass(listener);
    jmethodID on_token = env->GetMethodID(listener_class, "onToken", "(Ljava/lang/String;)V");
    jmethodID on_complete = env->GetMethodID(listener_class, "onComplete", "()V");
    jmethodID on_error = env->GetMethodID(listener_class, "onError", "(Ljava/lang/String;)V");

    std::string prompt_text = jstring_value(env, prompt);
    std::string image_file = jstring_value(env, image_path);
    std::string projector_file = jstring_value(env, mmproj_path);

    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model == nullptr) {
        call_string(env, listener, on_error, "Model Qwen3.5 belum dimuat.");
        return;
    }

    g_cancelled.store(false);
    llama_context * context = create_context(std::max<int32_t>(4096, context_size), thread_count);
    if (context == nullptr) {
        call_string(env, listener, on_error, "RAM tidak cukup untuk konteks gambar Qwen3.5.");
        return;
    }

    mtmd_context_params vision_params = mtmd_context_params_default();
    vision_params.use_gpu = false;
    vision_params.print_timings = false;
    vision_params.n_threads = std::max(2, static_cast<int>(thread_count));
    vision_params.warmup = false;
    vision_params.batch_max_tokens = 512;

    mtmd_context * vision = mtmd_init_from_file(projector_file.c_str(), g_model, vision_params);
    if (vision == nullptr || !mtmd_support_vision(vision)) {
        if (vision) mtmd_free(vision);
        llama_free(context);
        call_string(env, listener, on_error, "Projector gambar Qwen3.5 tidak kompatibel atau rusak.");
        return;
    }

    mtmd_helper_bitmap_wrapper loaded = mtmd_helper_bitmap_init_from_file(vision, image_file.c_str(), false);
    if (loaded.bitmap == nullptr) {
        mtmd_free(vision);
        llama_free(context);
        call_string(env, listener, on_error, "Gambar tidak dapat dibaca. Gunakan JPG, PNG, BMP, atau WebP.");
        return;
    }

    if (prompt_text.find(mtmd_default_marker()) == std::string::npos) {
        prompt_text = std::string(mtmd_default_marker()) + "\n" + prompt_text;
    }

    mtmd_input_text input_text {
        prompt_text.data(),
        prompt_text.size(),
        true,
        true
    };
    const mtmd_bitmap * bitmaps[] = { loaded.bitmap };
    mtmd_input_chunks * chunks = mtmd_input_chunks_init();
    int32_t tokenized = mtmd_tokenize(vision, chunks, &input_text, bitmaps, 1);
    if (tokenized != 0) {
        mtmd_input_chunks_free(chunks);
        mtmd_bitmap_free(loaded.bitmap);
        if (loaded.video_ctx) mtmd_helper_video_free(loaded.video_ctx);
        mtmd_free(vision);
        llama_free(context);
        call_string(env, listener, on_error, "Qwen3.5 gagal memproses gambar.");
        return;
    }

    llama_pos n_past = 0;
    int32_t evaluated = mtmd_helper_eval_chunks(vision, context, chunks, 0, 0, 512, true, &n_past);
    mtmd_input_chunks_free(chunks);
    mtmd_bitmap_free(loaded.bitmap);
    if (loaded.video_ctx) mtmd_helper_video_free(loaded.video_ctx);

    if (evaluated != 0) {
        mtmd_free(vision);
        llama_free(context);
        call_string(env, listener, on_error, "Gambar gagal dimasukkan ke konteks model.");
        return;
    }

    if (!stream_generation(env, listener, on_token, on_error, context, max_tokens, temperature)) {
        mtmd_free(vision);
        llama_free(context);
        return;
    }

    mtmd_free(vision);
    llama_free(context);
    env->CallVoidMethod(listener, on_complete);
}
