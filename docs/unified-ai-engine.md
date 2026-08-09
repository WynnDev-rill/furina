# Furina Unified AI Engine

## Tujuan

Identitas Furina tidak lagi dimiliki oleh model. Qwen 4B, Qwen 9B, dan adapter online yang ditambahkan nanti menerima paket konteks yang sama dari satu orchestration layer. Model hanya melakukan inferensi.

## Alur

1. `ContextEngine` menyusun identity/personality, ringkasan sesi, learned memory relevan, potongan percakapan lama relevan, dan riwayat terbaru.
2. `UnifiedAiEngine` memilih `AiProvider`, menyimpan pesan pengguna, meneruskan stream token, menyimpan balasan, lalu memperbarui ringkasan lokal.
3. `LocalLlamaProvider` mempertahankan weights GGUF di RAM, tetapi menghidrasi ulang prompt dari database pada tiap permintaan. Ini mencegah state percakapan native menjadi sumber kebenaran.
4. `MemoryStore` tetap menjadi sumber kebenaran offline untuk history, memory, settings, dan summary.

## Budget konteks lokal

- identity/personality selalu dipertahankan;
- summary maksimal 1.200 karakter;
- relevant memory maksimal 900 karakter;
- relevant older history maksimal 800 karakter;
- recent history maksimal 1.800 karakter;
- user prompt dan ruang generasi berada di luar budget tersebut.

Budget ini aman untuk context 4K dan fallback 2K. Seluruh history tetap disimpan di SQLite; yang dibatasi hanya payload inferensi.

## Ekstensi provider online

Provider baru mengimplementasikan `AiProvider.prepare`, `AiProvider.stream`, `AiProvider.unload`, dan capabilities. Ia tidak boleh memiliki database personality/memory sendiri. Attachment sudah menjadi bagian kontrak request, tetapi provider lokal saat ini menyatakan capabilities attachment kosong.

Google login dan cloud backup sengaja tidak diimplementasikan. Lapisan persistence tetap terpisah sehingga sinkronisasi dapat ditambahkan nanti tanpa mengubah provider atau UI chat.
