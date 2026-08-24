from __future__ import annotations

from dataclasses import dataclass
import re

_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[\wÀ-ÿ']+", re.UNICODE)
_NEGATION = re.compile(r"^\s*(?:tidak|nggak|enggak|gak|ga|bukan|nope|no)\b", re.I)
_CLARIFY = re.compile(r"^\s*(?:maksud(?:nya)?|apa maksud(?:nya)?|gimana maksud(?:nya)?|hah|ha\?|apa\?)\b", re.I)
_ACK = re.compile(r"^\s*(?:iya|ya|yap|yep|oke|ok|baik|benar|bener|setuju|lanjut|terus|teruskan|hmm+|hm+)\s*[.!?]*$", re.I)


def _clean(value: object, limit: int = 420) -> str:
    text = _SPACE.sub(" ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    keep = max(40, (limit - 5) // 2)
    return text[:keep].rstrip() + " … " + text[-keep:].lstrip()


def _move(text: str) -> str:
    clean = _clean(text, 220)
    words = _WORD.findall(clean)
    if _NEGATION.search(clean):
        return "correction_or_rejection"
    if _CLARIFY.search(clean):
        return "clarification_request"
    if _ACK.search(clean):
        return "acknowledgement"
    if clean.endswith("?"):
        return "question"
    if len(words) <= 1 and len(clean) <= 12:
        return "low_information"
    return "statement"


def _substantive(text: str) -> bool:
    clean = _clean(text, 260)
    words = _WORD.findall(clean)
    if _NEGATION.search(clean) or _CLARIFY.search(clean) or _ACK.search(clean):
        return False
    return len(words) >= 4 or len(clean) >= 26


@dataclass(frozen=True)
class DialogueState:
    fresh_thread: bool
    latest_user_move: str
    topic_anchor: str
    user_evidence: tuple[str, ...]
    assistant_reference: tuple[str, str] | None

    def render(self) -> str:
        lines = [
            "DIALOGUE STATE — keadaan thread, bukan persona dan bukan memory jangka panjang.",
            f"thread={'fresh' if self.fresh_thread else 'active'}",
            f"latest_user_move={self.latest_user_move}",
            f"user_topic={self.topic_anchor or '(belum ada topik yang ditetapkan user)'}",
        ]
        if self.user_evidence:
            lines.append("BUKTI DARI USER:")
            lines.extend(f"- {x}" for x in self.user_evidence)
        else:
            lines.append("BUKTI DARI USER: (belum ada konteks substantif)")
        if self.assistant_reference:
            status, text = self.assistant_reference
            lines.append("REFERENSI BALASAN FURINA TERAKHIR — hanya untuk memahami respons user, bukan fakta:")
            lines.append(f"- [{status}] {text}")
        else:
            lines.append("BALASAN FURINA LAMA: tidak diperlukan untuk turn ini; jangan meneruskan wording, motif, atau skenario lama.")
        lines.append(
            "Tetapkan realitas percakapan dari ucapan user. Jika turn terbaru membuka pertanyaan/topik baru, tanggapi itu sebagai pusat turn. "
            "Jangan menyalin struktur, pembuka, metafora, atau dugaan dari balasan Furina sebelumnya."
        )
        return "\n".join(lines)


class DialogueStateBuilder:
    @staticmethod
    def build(history: list[dict], latest_user: str) -> DialogueState:
        rows: list[tuple[str, str]] = []
        for row in history[-12:]:
            role = str(row.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = _clean(row.get("content"), 420)
            if content:
                rows.append((role, content))

        prior_user = [text for role, text in rows if role == "user"]
        prior_assistant = [text for role, text in rows if role == "assistant"]
        move = _move(latest_user)

        topic = ""
        for candidate in [*prior_user[-4:], latest_user]:
            if _substantive(candidate):
                topic = _clean(candidate, 300)

        # User evidence may persist briefly, but assistant wording only enters a
        # turn when the user's latest message explicitly depends on it.
        evidence = tuple(_clean(x, 260) for x in prior_user[-2:] if _substantive(x))
        reference = None
        if prior_assistant and move in {"correction_or_rejection", "clarification_request", "acknowledgement"}:
            status = {
                "correction_or_rejection": "rejected_or_corrected",
                "clarification_request": "clarification_target",
                "acknowledgement": "acknowledged_context",
            }[move]
            reference = (status, _clean(prior_assistant[-1], 260))

        return DialogueState(
            fresh_thread=not bool(rows),
            latest_user_move=move,
            topic_anchor=topic,
            user_evidence=evidence,
            assistant_reference=reference,
        )
