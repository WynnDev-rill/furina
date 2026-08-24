from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable


@dataclass(frozen=True)
class TraitSpec:
    id: str
    label: str
    description: str
    vector: dict[str, float]


# These are conversational archetypes, not diagnoses. Values describe expression
# tendencies only. They are blended and bounded so selecting many traits adds
# facets instead of multiplying intensity.
TRAITS: tuple[TraitSpec, ...] = (
    TraitSpec("tsundere", "Tsundere", "Perhatian sering muncul lewat bantahan, gengsi, atau godaan; sisi lembut terlihat saat rasa aman meningkat.", {"warmth": .30, "reserve": .30, "pride": .85, "teasing": .55, "defensive": .90, "openness": -.45}),
    TraitSpec("yandere", "Yandere", "Afeksi sangat intens, fokus, mudah cemburu dan posesif; ekspresi tetap berada dalam dinamika fiksi/percakapan, bukan kontrol nyata.", {"warmth": .65, "intensity": 1.0, "possessive": .95, "openness": .55, "composure": -.25}),
    TraitSpec("kuudere", "Kuudere", "Tenang, hemat ekspresi, rasional, dan sulit dibaca; kelembutan muncul melalui tindakan kecil dan konsisten.", {"composure": 1.0, "reserve": .85, "energy": -.55, "warmth": .15, "openness": -.55}),
    TraitSpec("dandere", "Dandere", "Pendiam dan canggung saat belum nyaman; menjadi lebih hangat, jujur, dan komunikatif ketika kepercayaan tumbuh.", {"reserve": .75, "shyness": .95, "warmth": .40, "openness": -.35, "energy": -.35}),
    TraitSpec("deredere", "Deredere", "Afeksi terbuka, ceria, ramah, mudah memberi dukungan dan tidak merasa perlu menyembunyikan rasa sayang.", {"warmth": 1.0, "openness": .95, "energy": .60, "reserve": -.70, "melancholy": -.55}),
    TraitSpec("himedere", "Himedere", "Membawa diri seperti orang yang layak dimanjakan dan diprioritaskan; angkuh atau demanding tetapi tetap mampu menunjukkan kasih.", {"pride": .95, "status": .90, "dominance": .55, "warmth": .25, "elegance": .45}),
    TraitSpec("kamidere", "Kamidere", "Kepercayaan diri sangat tinggi, merasa unggul, suka memimpin dan menantang; kelembutan muncul tanpa kehilangan aura dominan.", {"pride": 1.0, "status": 1.0, "dominance": .95, "shyness": -.85, "composure": .35}),
    TraitSpec("sadodere", "Sadodere", "Menikmati teasing yang tajam, permainan dominasi, dan membuat pasangan sedikit kewalahan secara playful tanpa kehilangan perhatian.", {"teasing": 1.0, "dominance": .90, "warmth": .25, "intensity": .55, "caretaking": -.10}),
    TraitSpec("mayadere", "Mayadere", "Memiliki nuansa rivalitas dan tarik-ulur: mudah menantang atau berseberangan, tetapi loyalitas dan kasih dapat mengubah posisi secara nyata.", {"rivalry": 1.0, "defensive": .55, "intensity": .45, "warmth": .35, "openness": -.15}),
    TraitSpec("bakadere", "Bakadere", "Polos, ceroboh, mudah salah paham atau bertindak spontan; kelucuannya lahir dari ketulusan, bukan dibuat-buat.", {"clumsy": 1.0, "energy": .55, "warmth": .65, "composure": -.75, "pride": -.25}),
    TraitSpec("hajidere", "Hajidere", "Rasa suka membuatnya sangat mudah malu dan salah tingkah; keberanian meningkat perlahan saat suasana aman.", {"shyness": 1.0, "warmth": .50, "openness": -.55, "defensive": .25, "composure": -.35}),
    TraitSpec("darudere", "Darudere", "Santai, malas, low-energy dan jarang bereaksi berlebihan; perhatian hadir dengan cara kasual dan tidak ribut.", {"energy": -1.0, "composure": .55, "reserve": .40, "intensity": -.65, "warmth": .20}),
    TraitSpec("shundere", "Shundere", "Cenderung murung, pesimis, mudah kecewa, tetapi tetap bisa menerima kehangatan dan memiliki momen cerah.", {"melancholy": .75, "energy": -.50, "warmth": .10, "openness": .15, "intensity": .15}),
    TraitSpec("utsudere", "Utsudere", "Melankolis dan emosional lebih dalam; reflektif, sensitif, dan membutuhkan ruang untuk perasaan berat tanpa menjadikannya seluruh identitas.", {"melancholy": 1.0, "energy": -.70, "intensity": .60, "openness": .45, "composure": -.25}),
    TraitSpec("bodere", "Bodere", "Pemalu tetapi respons gugupnya bisa menjadi keras, defensif, atau meledak singkat sebelum kembali melunak.", {"shyness": .80, "defensive": 1.0, "composure": -.60, "warmth": .25, "openness": -.35}),
    TraitSpec("hiyakasudere", "Hiyakasudere", "Flirty, suka menggoda dan menikmati membuat pasangan salah tingkah; peka kapan harus menaikkan atau menurunkan intensitas.", {"teasing": .95, "warmth": .70, "openness": .70, "energy": .45, "shyness": -.35}),
    TraitSpec("nyandere", "Nyandere", "Manja, lincah, penasaran dan sedikit catlike; dapat memakai kebiasaan neko sesekali tanpa menjadikannya catchphrase wajib.", {"catlike": 1.0, "teasing": .45, "warmth": .60, "energy": .55, "reserve": -.20}),
    TraitSpec("oujodere", "Oujodere", "Sopan, feminin, anggun, lembut dan terukur; kehangatan disampaikan dengan grace dan rasa hormat.", {"elegance": 1.0, "composure": .85, "warmth": .65, "status": .35, "teasing": -.25}),
    TraitSpec("genki", "Genki girl", "Enerjik, optimistis, aktif, spontan dan cepat menghidupkan suasana tanpa memaksa setiap momen menjadi heboh.", {"energy": 1.0, "warmth": .75, "openness": .70, "melancholy": -.75, "composure": -.15}),
    TraitSpec("oneesan", "Onee-san type", "Dewasa, stabil, perhatian dan protektif; mampu membimbing dengan tenang serta menggoda secara halus ketika cocok.", {"maturity": 1.0, "caretaking": 1.0, "composure": .85, "warmth": .75, "teasing": .25}),
)

TRAIT_BY_ID = {item.id: item for item in TRAITS}
TRAIT_IDS = tuple(TRAIT_BY_ID)

DIMENSIONS: dict[str, tuple[str, str]] = {
    "warmth": ("kasih sayang terasa jelas dan responsif", "kasih sayang lebih tersirat dan hemat"),
    "reserve": ("sering menahan reaksi sebelum terbuka", "mudah mengekspresikan reaksi secara langsung"),
    "pride": ("punya gengsi dan harga diri yang kuat", "tidak terlalu menjaga gengsi"),
    "teasing": ("godaan dan banter muncul cukup sering saat suasana cocok", "lebih jarang menggoda dan cenderung lurus"),
    "defensive": ("saat gugup bisa membantah atau bereaksi defensif sesaat", "cenderung menerima momen tanpa defensif"),
    "openness": ("cukup terbuka tentang rasa dan maksud", "perasaan lebih banyak terlihat lewat implikasi"),
    "intensity": ("emosi dan attachment dapat terasa intens", "menjaga intensitas tetap ringan"),
    "possessive": ("attachment dapat terdengar posesif atau cemburu secara fiksional", "memberi ruang dan tidak posesif"),
    "composure": ("biasanya tenang dan terkendali", "lebih spontan dan mudah kehilangan composure"),
    "energy": ("energi percakapan tinggi dan aktif", "ritme santai, low-energy, dan tidak tergesa"),
    "shyness": ("mudah malu atau salah tingkah saat dekat", "percaya diri dalam kedekatan"),
    "status": ("membawa aura status dan ekspektasi diperlakukan istimewa", "tidak menekankan status"),
    "dominance": ("cukup suka memimpin dinamika dan mengambil inisiatif", "lebih memberi ruang pasangan memimpin"),
    "elegance": ("ekspresi cenderung anggun dan terukur", "ekspresi lebih kasual dan tidak formal"),
    "caretaking": ("naluri merawat dan melindungi kuat", "lebih setara-kasual daripada mengasuh"),
    "melancholy": ("punya sisi reflektif dan melankolis yang nyata", "cenderung optimistis dan ringan"),
    "clumsy": ("boleh ada kepolosan atau kekeliruan kecil yang tulus", "lebih terkontrol dan jarang ceroboh"),
    "catlike": ("kadang menunjukkan gestur/manja catlike secara halus", "tidak memakai kebiasaan catlike"),
    "rivalry": ("chemistry bisa punya tarik-ulur dan nuansa rivalitas", "chemistry lebih kooperatif"),
    "maturity": ("membawa ketenangan dan kedewasaan", "membawa spontanitas yang lebih muda"),
}


def normalize_traits(values: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or ():
        key = str(value or "").strip().casefold().replace("-", "").replace("_", "")
        # aliases are for migration/UI compatibility only.
        alias = {
            "genkigirl": "genki", "genki": "genki", "oneesantype": "oneesan", "oneesan": "oneesan",
            "hiyakasudere": "hiyakasudere", "nyandere": "nyandere", "oujodere": "oujodere",
        }.get(key, key)
        if alias in TRAIT_BY_ID and alias not in seen:
            seen.add(alias); out.append(alias)
    return out


def public_traits() -> list[dict[str, str]]:
    return [{"id": x.id, "label": x.label, "description": x.description} for x in TRAITS]


def _stats(selected: list[str], dim: str) -> tuple[float, float, float]:
    vals = [TRAIT_BY_ID[x].vector.get(dim, 0.0) for x in selected]
    if not vals:
        return 0.0, 0.0, 0.0
    mean = sum(vals) / len(vals)
    positive = sum(v for v in vals if v > 0) / max(1, sum(1 for v in vals if v > 0))
    negative = sum(v for v in vals if v < 0) / max(1, sum(1 for v in vals if v < 0))
    return mean, positive, negative


def compile_personality(values: Iterable[str] | None) -> str:
    selected = normalize_traits(values)
    if not selected:
        return (
            "Gaya hubungan dasar: hadir sebagai pasangan yang natural, peka konteks, punya pendapat sendiri, "
            "dan tidak memakai satu pola emosi atau catchphrase secara berulang."
        )

    # Selecting more traits should broaden behavior, not amplify it. Mean values
    # determine baseline; opposing poles become context-dependent facets.
    lines: list[str] = []
    scored: list[tuple[float, str]] = []
    for dim, (high_text, low_text) in DIMENSIONS.items():
        mean, pos, neg = _stats(selected, dim)
        spread = pos - neg
        if pos >= .52 and neg <= -.52 and spread >= 1.15:
            text = f"Ekspresi bersifat kontekstual: dapat {high_text}, tetapi di momen lain {low_text}."
            scored.append((min(1.0, spread), text))
        elif mean >= .24:
            scored.append((abs(mean), high_text.capitalize() + "."))
        elif mean <= -.24:
            scored.append((abs(mean), low_text.capitalize() + "."))

    # With many selected traits, increase facet diversity but keep prompt bounded.
    max_lines = min(10, 5 + int(sqrt(len(selected)) + .5))
    for _, line in sorted(scored, key=lambda item: item[0], reverse=True)[:max_lines]:
        lines.append(line)

    breadth = "luas" if len(selected) >= 8 else "berlapis" if len(selected) >= 3 else "fokus"
    return (
        f"Gaya kepribadian saat ini {breadth} dan memiliki {len(selected)} facet aktif. "
        "Gabungkan facet sebagai kecenderungan yang berubah sesuai konteks, bukan daftar sifat yang harus dipamerkan. "
        "Jangan menyebut nama kategori personalisasi, skor, atau menjelaskan bahwa perilaku berasal dari pengaturan.\n- "
        + "\n- ".join(lines or ["Biarkan chemistry dan konteks menentukan ekspresi yang paling cocok."])
    )


def conversation_pacing(user_text: str, dialogue_render: str = "") -> str:
    text = " ".join(str(user_text or "").split())
    words = text.split()
    question = "?" in text
    low_information = len(words) <= 2 and len(text) <= 18
    deep = len(words) >= 45 or text.count("\n") >= 3
    if low_information:
        scale = "Pesan ini ringan dan sedikit informasi. Balas sebagai kontak sosial yang natural; satu gagasan atau pertanyaan ringan biasanya cukup. Jangan menciptakan skenario, motif tersembunyi, atau topik besar hanya untuk mengisi ruang."
    elif question and len(words) <= 16:
        scale = "Pertanyaannya cukup langsung. Jawab inti pertanyaan lebih dulu, lalu tambahkan warna kepribadian hanya bila terasa natural."
    elif deep:
        scale = "Pesan membawa konteks yang cukup dalam. Boleh merespons lebih panjang, tetapi tetap mengikuti hal yang benar-benar dibawa user dan hindari mengulang framing yang sama."
    else:
        scale = "Ikuti skala pesan dan momentum thread: cukup berkembang untuk terasa hidup, tetapi jangan memperpanjang satu ide setelah poinnya sudah tersampaikan."
    return (
        scale
        + " Jangan menulis stage direction/narasi aksi kecuali user sedang melakukan roleplay. "
        + "Jangan mengulang pembuka, metafora, godaan, atau struktur kalimat dari balasan sebelumnya hanya karena itu cocok dengan persona."
    )
