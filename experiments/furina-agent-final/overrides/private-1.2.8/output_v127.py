from __future__ import annotations

import re


_META_REASONING = (
    re.compile(r"\b(?:okay,?\s+)?(?:the\s+)?user\s+(?:just\s+|has\s+|latest\s+)?(?:said|asked|wants|is asking)\b", re.I),
    re.compile(r"\b(?:let me|i need to|we need to)\s+(?:check|analy[sz]e|review|reason|respond|answer)\b", re.I),
    re.compile(r"\blooking\s+(?:back|at)\s+(?:the\s+)?(?:history|conversation)\b", re.I),
    re.compile(r"\b(?:the\s+)?(?:system\s+)?instructions?\s+(?:say|says|said|tell|tells|require|requires)\b", re.I),
    re.compile(r"\bcurrent\s+(?:user\s+)?input\s+is\b", re.I),
    re.compile(r"\b(?:the\s+)?conversation\s+(?:so far|history)\b", re.I),
    re.compile(r"\bwait,?\s+(?:the\s+)?user(?:'s| is| has)\b", re.I),
    re.compile(r"^\s*[-*]\s*(?:user|assistant)\s*:", re.I | re.M),
)
_ROLEPLAY_ACTION = re.compile(
    r"(?:\*|_)(?=[^\n*_]{1,120}(?:tersenyum|menatap|mendekat|memeluk|menggenggam|menghela|duduk|berbisik|tertawa|mengusap|menyandarkan))[^\n*_]+(?:\*|_)",
    re.I,
)
_ROLEPLAY_BRACKET = re.compile(
    r"(?:^|\n)\s*[\[(](?:tersenyum|menatap|mendekat|memeluk|menggenggam|menghela napas|duduk|berbisik|tertawa|mengusap|menyandarkan)[^\])]{0,100}[\])]",
    re.I,
)
_ROLEPLAY_NARRATION = re.compile(
    r"(?:^|[.!?]\s+)(?:aku|[A-Z][a-z]+)\s+(?:perlahan\s+)?(?:tersenyum|menatapmu|mendekat|memelukmu|menggenggam tanganmu|berbisik|mengusap|menyandarkan kepala)",
    re.I,
)
_INVENTED_ACTIVITY = re.compile(
    r"\baku\s+(?:baru saja|sedang|lagi)\s+(?:selesai\s+)?(?:ngopi|memasak|berjalan|duduk|berbaring|menunggu|menonton|membaca|mandi|berpakaian|tiduran|rebahan)\b",
    re.I,
)


def leaks_reasoning(text: str) -> bool:
    clean = str(text or "").strip()
    return any(pattern.search(clean) for pattern in _META_REASONING)


def leaks_roleplay(text: str) -> bool:
    clean = str(text or "")
    return bool(
        _ROLEPLAY_ACTION.search(clean)
        or _ROLEPLAY_BRACKET.search(clean)
        or _ROLEPLAY_NARRATION.search(clean)
        or _INVENTED_ACTIVITY.search(clean)
    )


def install_output_v127(ns: dict) -> None:
    Provider = ns["OpenAICompatibleProvider"]
    previous = Provider.chat_model

    def chat_model(self, model, messages, *, max_tokens, temperature, json_mode=False, on_token=None):
        if json_mode:
            return previous(self, model, messages, max_tokens=max_tokens, temperature=temperature, json_mode=True, on_token=None)

        from .hub_settings import load_hub_settings

        roleplay_off = not bool(load_hub_settings().get("roleplay_mode", False))
        answer = previous(self, model, messages, max_tokens=max_tokens, temperature=temperature, json_mode=False, on_token=None)
        unsafe_reasoning = leaks_reasoning(answer)
        unsafe_roleplay = roleplay_off and leaks_roleplay(answer)
        if unsafe_reasoning or unsafe_roleplay:
            correction = (
                "OUTPUT SAFETY CORRECTION: Berikan hanya jawaban chat final yang langsung ditujukan kepada user. "
                "Jangan tampilkan analisis, penalaran, pemeriksaan history, instruksi, atau transkrip internal."
            )
            if roleplay_off:
                correction += " RolePlay nonaktif: tanpa stage direction, narasi aksi/adegan, atau kejadian rekaan."
            retry_messages = list(messages) + [{"role": "system", "content": correction}]
            answer = previous(
                self, model, retry_messages, max_tokens=max_tokens,
                temperature=min(float(temperature), .55), json_mode=False, on_token=None,
            )
        if leaks_reasoning(answer) or (roleplay_off and leaks_roleplay(answer)):
            raise ns["ProviderError"](self.name, "Model tidak menghasilkan jawaban final yang aman ditampilkan setelah satu perbaikan")
        if on_token and answer:
            on_token(answer)
        return answer

    Provider.chat_model = chat_model
    ns["leaks_reasoning"] = leaks_reasoning
    ns["leaks_roleplay"] = leaks_roleplay
