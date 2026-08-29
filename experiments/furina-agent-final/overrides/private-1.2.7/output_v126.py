from __future__ import annotations

import re


_BLOCK = re.compile(r"<(?:think|thinking|analysis|reasoning)>.*?</(?:think|thinking|analysis|reasoning)>", re.I | re.S)
_FINAL = re.compile(r"(?:^|\n)\s*(?:final(?: answer)?|jawaban akhir)\s*:\s*", re.I)
_LEADING = re.compile(r"^\s*(?:analysis|reasoning|thought process|thinking)\s*:\s*", re.I)


def visible_answer(text: str) -> str:
    clean = _BLOCK.sub("", str(text or "")).strip()
    markers = list(_FINAL.finditer(clean))
    if markers:
        clean = clean[markers[-1].end():].strip()
    elif _LEADING.search(clean):
        # Do not guess where naked reasoning ends. Hiding the entire unsafe
        # result is better than displaying internal notes as conversation.
        return ""
    clean = re.sub(r"^\s*(?:assistant|jawaban)\s*:\s*", "", clean, flags=re.I)
    return clean.strip()


def install_output_v126(ns: dict) -> None:
    Provider = ns["OpenAICompatibleProvider"]
    previous = Provider._chat_once

    def chat_once(self, model, messages, *, max_tokens, temperature, json_mode, on_token=None):
        # Online output is buffered before display. Provider-native reasoning
        # controls remain enabled, and this second boundary prevents tagged or
        # prefixed reasoning from ever reaching the visible streaming callback.
        answer, finish = previous(
            self, model, messages, max_tokens=max_tokens, temperature=temperature,
            json_mode=json_mode, on_token=None,
        )
        cleaned = answer if json_mode else visible_answer(answer)
        if not cleaned and answer and not json_mode:
            raise ns["ProviderError"](self.name, "Model mengirim proses berpikir tanpa jawaban final yang aman ditampilkan")
        if on_token and cleaned:
            on_token(cleaned)
        return cleaned, finish

    Provider._chat_once = chat_once
    ns["visible_answer"] = visible_answer
