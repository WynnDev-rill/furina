from __future__ import annotations

import hashlib
import json
import re

from .training_corpus import (
    CURATED_CONVERSATION_CORPUS,
    category_contract,
    sanitize_external_utterance,
)

_FORBIDDEN = re.compile(
    r"(?i)\b(furina|genshin|fontaine|archon|teyvat|assistant_name|partner_mode|"
    r"personality_traits|training room|memori pengguna)\b"
)


def prompt_fingerprint(text: str) -> str:
    normalized = " ".join(str(text or "").casefold().split())
    return hashlib.blake2s(normalized.encode(), digest_size=10).hexdigest()


def load_neutral_corpus() -> tuple[dict, ...]:
    records = []
    for item in CURATED_CONVERSATION_CORPUS:
        prompt = sanitize_external_utterance(item.text)
        if not prompt or _FORBIDDEN.search(prompt):
            continue
        records.append({
            "id": "curated:" + item.id,
            "topic_id": "curated:" + item.id,
            "context": item.arc,
            "prompt": prompt,
            "categories": tuple(item.categories),
            "source": "quality-gated Indonesian conversation pattern",
        })
    return tuple(records)


def select_corpus_prompt(category_id: str, retired: set[str], seed: str, cursor: int = 0) -> tuple[dict | None, int]:
    candidates = [row for row in load_neutral_corpus() if category_id in row["categories"]]
    if not candidates:
        candidates = list(load_neutral_corpus())
    if not candidates:
        return None, cursor
    start_key = hashlib.blake2s(f"{seed}:{category_id}:{cursor}".encode(), digest_size=4).digest()
    start = int.from_bytes(start_key, "big") % len(candidates)
    for offset in range(len(candidates)):
        row = candidates[(start + offset) % len(candidates)]
        if row["id"] in retired or "fp:" + prompt_fingerprint(row["prompt"]) in retired:
            continue
        return dict(row), cursor + offset + 1
    return None, cursor + len(candidates)


def parse_neutral_prompt(raw: str) -> dict:
    text = str(raw or "").strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    context = " ".join(str(value.get("context") or "").split())[:500]
    prompt = " ".join(str(value.get("prompt") or "").split())[:420]
    prompt = sanitize_external_utterance(prompt) or ""
    if not prompt or len(prompt) < 6 or _FORBIDDEN.search(context + " " + prompt):
        return {}
    return {"context": context, "prompt": prompt}


def fallback_neutral_prompt(category_id: str, sequence: int, anchor: dict | None = None) -> dict:
    situations = {
        "natural": ("Aku baru selesai mengubah satu bagian kecil, tapi sekarang malah ragu dengan hasilnya.", "perubahan kecil"),
        "emotional": ("Aku sudah berusaha tenang, tapi kegagalan kecil tadi masih menggangguku.", "kekecewaan ringan"),
        "partner": ("Hari ini kita jarang bicara. Aku ingin ditemani sebentar tanpa membuatnya terasa berat.", "kedekatan sehari-hari"),
        "playful": ("Wah, akhirnya kamu menyadarinya juga. Cepat sekali, ya.", "candaan ringan"),
        "length": ("Aku punya beberapa pilihan dan semuanya ada kekurangannya. Bantu aku melihat inti keputusannya.", "pendapat bertahap"),
        "language": ("Kayaknya idenya udah benar, cuma cara ngomongnya masih terasa kaku.", "bahasa kasual"),
        "initiative": ("Aku belum meminta bantuan, tetapi dari tadi juga tidak berhasil memulai.", "inisiatif proporsional"),
        "ambiguous_tone": ("Bagus sekali. Benar-benar sesuai dugaan.", "nada ambigu"),
        "mixed_emotion": ("Aku senang hasilnya berhasil, tapi sekaligus takut tidak bisa mengulanginya.", "dua emosi bersamaan"),
    }
    prompt, label = situations.get(category_id, situations["natural"])
    if sequence:
        prompt = prompt.rstrip(".") + f" Kali ini situasinya sedikit berbeda dari sebelumnya ({sequence + 1})."
    context = str((anchor or {}).get("context") or category_contract(category_id))[:300]
    digest = prompt_fingerprint(f"{category_id}:{sequence}:{context}:{prompt}")
    return {
        "id": "derived:" + digest,
        "context": context,
        "prompt": prompt,
        "categories": (category_id,),
        "source": "neutral derived fallback",
        "label": label,
    }
