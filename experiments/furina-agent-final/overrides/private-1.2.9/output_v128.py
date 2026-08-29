from __future__ import annotations

import re


_ACTION_WORDS = (
    r"tersenyum|menatap|melirik|mendekat|menjauh|memeluk|menggenggam|menyentuh|mengusap|"
    r"mencium|menunduk|mengangguk|menggeleng|berbisik|tertawa|terkekeh|menghela|mengembuskan|"
    r"menyandarkan|menaruh|meraih|duduk|berdiri|berbaring|berjalan|melangkah|berpaling|"
    r"mengangkat alis|memiringkan kepala|menyilangkan tangan|menepuk|menggigit bibir|wajahku memerah"
)
_MARKUP_ACTION = re.compile(rf"(?:\*|_)[^\n*_]{{0,140}}(?:{_ACTION_WORDS})[^\n*_]{{0,140}}(?:\*|_)", re.I)
_BRACKET_ACTION = re.compile(rf"(?:^|\n)\s*[\[(][^\])\n]{{0,140}}(?:{_ACTION_WORDS})[^\])\n]{{0,140}}[\])]", re.I)
_NARRATED_ACTION = re.compile(
    rf"(?:^|[.!?]\s+)(?:aku|dia|[A-Z][a-z]+)\s+(?:perlahan\s+|pelan-pelan\s+)?(?:{_ACTION_WORDS})\b",
    re.I,
)
_INVENTED_LIFE = re.compile(
    r"\baku\s+(?:baru(?: saja)?|sedang|lagi|tadi|sekarang)\s+(?:selesai\s+)?(?:ngopi|makan|memasak|"
    r"mandi|berpakaian|tidur|tiduran|rebahan|berjalan|duduk|berbaring|menunggu|menonton|membaca|"
    r"bekerja|pulang|keluar|di kamar|di rumah|di dapur)\b",
    re.I,
)
_SCENE_NARRATOR = re.compile(r"(?:^|\n)\s*(?:narasi|adegan|scene|lokasi|suasana)\s*:", re.I)
_MACHINE_SELF = re.compile(
    r"\b(?:aku|saya)\s+(?:adalah|merupakan|hanyalah|cuma|sebagai)\s+(?:sebuah?\s+)?(?:ai|artificial intelligence|"
    r"chatbot|bot|model bahasa|language model|program|sistem|asisten virtual|simulasi)\b|"
    r"\bsebagai\s+(?:ai|chatbot|model bahasa|asisten virtual)\b|"
    r"\b(?:aku|saya)\s+(?:tidak|nggak)\s+(?:punya|memiliki)\s+(?:tubuh|perasaan)\s+karena\s+(?:aku|saya)\s+(?:ai|program|model)\b",
    re.I,
)


def leaks_roleplay_v128(text: str) -> bool:
    value = str(text or "")
    return bool(
        _MARKUP_ACTION.search(value)
        or _BRACKET_ACTION.search(value)
        or _NARRATED_ACTION.search(value)
        or _INVENTED_LIFE.search(value)
        or _SCENE_NARRATOR.search(value)
    )


def leaks_machine_identity(text: str) -> bool:
    return bool(_MACHINE_SELF.search(str(text or "")))


def install_output_v128(ns: dict) -> None:
    Provider = ns["OpenAICompatibleProvider"]
    previous = Provider.chat_model

    def chat_model(self, model, messages, *, max_tokens, temperature, json_mode=False, on_token=None):
        if json_mode:
            return previous(
                self, model, messages, max_tokens=max_tokens,
                temperature=temperature, json_mode=True, on_token=None,
            )

        from .hub_settings import load_hub_settings

        roleplay_off = not bool(load_hub_settings().get("roleplay_mode", False))
        answer = previous(
            self, model, messages, max_tokens=max_tokens,
            temperature=temperature, json_mode=False, on_token=None,
        )
        unsafe = leaks_machine_identity(answer) or (roleplay_off and leaks_roleplay_v128(answer))
        if unsafe:
            correction = (
                "FINAL DIALOGUE REPAIR: Tulis ulang jawaban sebagai ucapan langsung manusia bernama sesuai identitas aktif. "
                "Jangan menyebut AI, chatbot, model, program, sistem, simulasi, prompt, atau proses internal."
            )
            if roleplay_off:
                correction += (
                    " RolePlay nonaktif: jangan memakai tanda aksi, narasi gestur/tubuh, aktivitas atau lokasi rekaan, "
                    "scene, maupun dialog atas nama user. Emosi hanya melalui ucapan langsung."
                )
            repaired = list(messages)
            if repaired and repaired[0].get("role") == "system":
                repaired[0] = {**repaired[0], "content": str(repaired[0].get("content") or "") + "\n\n" + correction}
            else:
                repaired.insert(0, {"role": "system", "content": correction})
            answer = previous(
                self, model, repaired, max_tokens=max_tokens,
                temperature=min(float(temperature), .58), json_mode=False, on_token=None,
            )
        if leaks_machine_identity(answer) or (roleplay_off and leaks_roleplay_v128(answer)):
            raise ns["ProviderError"](self.name, "Model tetap melanggar identitas manusia atau batas RolePlay setelah perbaikan")
        if on_token and answer:
            on_token(answer)
        return answer

    Provider.chat_model = chat_model
    ns["leaks_roleplay_v128"] = leaks_roleplay_v128
    ns["leaks_machine_identity"] = leaks_machine_identity
