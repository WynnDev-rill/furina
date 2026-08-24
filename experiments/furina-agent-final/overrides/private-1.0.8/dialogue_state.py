from __future__ import annotations

from dataclasses import dataclass
import re


_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[\wÀ-ÿ']+", re.UNICODE)
_NEGATION = re.compile(r"^\s*(?:tidak|nggak|enggak|gak|ga|bukan|nope|no)\b", re.I)
_CLARIFY = re.compile(r"^\s*(?:maksud(?:nya)?|apa maksud(?:nya)?|gimana maksud(?:nya)?|hah|ha\?|apa\?)\b", re.I)


def _clean(value: object, limit: int = 520) -> str:
    text = _SPACE.sub(" ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    keep = max(40, (limit - 5) // 2)
    return text[:keep].rstrip() + " … " + text[-keep:].lstrip()


def _user_move(text: str) -> str:
    clean = _clean(text, 240)
    words = _WORD.findall(clean)
    if _NEGATION.search(clean):
        return "correction_or_rejection"
    if _CLARIFY.search(clean):
        return "clarification_request"
    if clean.endswith("?"):
        return "question"
    if len(words) <= 1 and len(clean) <= 12:
        return "low_information"
    return "statement"


def _substantive_user_turn(text: str) -> bool:
    clean = _clean(text, 260)
    words = _WORD.findall(clean)
    if _NEGATION.search(clean) or _CLARIFY.search(clean):
        return False
    return len(words) >= 4 or len(clean) >= 30


@dataclass(frozen=True)
class DialogueState:
    fresh_thread: bool
    latest_user_move: str
    topic_anchor: str
    user_evidence: tuple[str, ...]
    assistant_continuity: tuple[tuple[str, str], ...]

    def render(self) -> str:
        lines = [
            "DIALOGUE STATE — grounding percakapan saat ini, bukan persona dan bukan memory jangka panjang.",
            f"thread={'fresh' if self.fresh_thread else 'active'}",
            f"latest_user_move={self.latest_user_move}",
            f"topic_anchor={self.topic_anchor or '(belum ada topik yang ditetapkan pengguna)'}",
        ]
        if self.user_evidence:
            lines.append("UCAPAN USER — sumber kebenaran percakapan:")
            lines.extend(f"- {item}" for item in self.user_evidence)
        else:
            lines.append("UCAPAN USER SEBELUMNYA: (belum ada)")

        if self.assistant_continuity:
            lines.append("UCAPAN FURINA SEBELUMNYA — hanya continuity, bukan fakta tentang user:")
            for status, text in self.assistant_continuity:
                lines.append(f"- [{status}] {text}")
        else:
            lines.append("UCAPAN FURINA SEBELUMNYA: (belum ada)")

        lines.append(
            "Gunakan ucapan user untuk menetapkan apa yang benar-benar terjadi. Ucapan Furina lama boleh membantu memahami referensi, "
            "tetapi asumsi Furina tidak menjadi kenyataan hanya karena pernah diucapkan. Jika user menolak atau meminta klarifikasi, "
            "perbarui pemahaman dan jangan mempertahankan asumsi lama. Jika belum ada topik, biarkan percakapan tetap terbuka tanpa menciptakan latar tersembunyi."
        )
        return "\n".join(lines)


class DialogueStateBuilder:
    """Build a compact, user-grounded view of one short-term conversation thread.

    This is deliberately not an intent router and never generates a response.
    It only separates user evidence from Furina's own prior improvisation so a
    small roleplay-tuned model can keep continuity without treating its previous
    guesses as facts.
    """

    @staticmethod
    def build(history: list[dict], latest_user: str) -> DialogueState:
        rows: list[tuple[str, str]] = []
        for row in history[-12:]:
            role = str(row.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = _clean(row.get("content"), 520)
            if content:
                rows.append((role, content))

        prior_user = [text for role, text in rows if role == "user"]
        prior_assistant = [text for role, text in rows if role == "assistant"]
        move = _user_move(latest_user)

        user_evidence = tuple((_clean(text, 360) for text in prior_user[-3:]))
        topic_anchor = ""
        for candidate in list(prior_user) + [latest_user]:
            if _substantive_user_turn(candidate):
                topic_anchor = _clean(candidate, 360)

        assistant_rows: list[tuple[str, str]] = []
        for text in prior_assistant[-2:]:
            assistant_rows.append(("unverified_character_utterance", _clean(text, 420)))
        if assistant_rows and move == "correction_or_rejection":
            assistant_rows[-1] = ("rejected_or_corrected_by_user", assistant_rows[-1][1])
        elif assistant_rows and move == "clarification_request":
            assistant_rows[-1] = ("user_requests_clarification", assistant_rows[-1][1])

        return DialogueState(
            fresh_thread=not bool(rows),
            latest_user_move=move,
            topic_anchor=topic_anchor,
            user_evidence=user_evidence,
            assistant_continuity=tuple(assistant_rows),
        )
