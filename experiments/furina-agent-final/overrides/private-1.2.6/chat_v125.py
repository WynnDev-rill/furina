from __future__ import annotations


def install_chat_v125(ns: dict) -> None:
    FurinaChat = ns["FurinaChat"]
    extract_explicit_memories = ns["extract_explicit_memories"]

    def commit_preferred_response(self, user_text: str, answer: str) -> str:
        """Commit one explicitly selected live-training answer exactly once."""
        user_text = str(user_text or "").strip()
        answer = str(answer or "").strip()
        if not user_text or not answer:
            raise ValueError("Pesan dan respons terpilih tidak boleh kosong.")
        source_message_id = self.store.add_message("user", user_text)
        for text, kind, importance in extract_explicit_memories(user_text):
            self.store.add_memory(
                text,
                kind,
                importance,
                confidence=min(.97, importance + .12),
                source="explicit",
                source_message_id=source_message_id,
                source_evidence=user_text,
            )
            dimension = "preference" if kind == "preference" else "goal" if kind == "goal" else "identity" if kind == "identity" else "profile"
            self.store.upsert_belief(dimension, text, min(.97, importance + .08), source="explicit")
        self.store.add_message("assistant", answer)
        turn = self.store.increment_state("companion_turns", 1)
        self._schedule_background(user_text, answer, turn)
        return answer

    FurinaChat.commit_preferred_response = commit_preferred_response
