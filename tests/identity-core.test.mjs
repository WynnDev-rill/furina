import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { applyReview, emptyIdentity, identityPrompt, observeTurn, parseIdentity, proposalSchema, readyForReview } from "../src/lib/identity-core.ts";

const thread = randomUUID();
const start = 1_800_000_000_000;
const evidence = (at, conversation = thread) => ({ turn: randomUUID(), at, thread: conversation });
const experience = "Aku suka diskusi yang beda pendapat dengan tenang.";
const preference = { key: "calm_debate", category: "bond", text: "Furina terbiasa menyampaikan perbedaan pendapat dengan hangat.", quote: experience };
const propose = (...observations) => proposalSchema.parse({ observations, retract: [] });

test("reviews require six distinct recent turns and a cooldown", () => {
  let state = emptyIdentity();
  for (let i = 0; i < 5; i++) state = observeTurn(state, evidence(start + i));
  const sixth = evidence(start + 5);
  assert.equal(readyForReview(state, sixth.at), false);
  state = observeTurn(state, sixth);
  assert.equal(readyForReview(state, sixth.at), true);
  assert.equal(observeTurn(state, sixth), state);
  assert.equal(readyForReview({ ...state, lastReview: start }, sixth.at), false);
});

test("one turn cannot affect replies and a later thread establishes continuity", () => {
  const first = applyReview(emptyIdentity(), propose(preference), evidence(start), experience);
  assert.equal(first.candidates.length, 1);
  assert.doesNotMatch(identityPrompt(first), /terbiasa menyampaikan/);
  const sameSession = applyReview(first, propose(preference), evidence(start + 31 * 60_000), experience);
  assert.equal(sameSession.established.length, 0);
  const otherThread = applyReview(sameSession, propose(preference), evidence(start + 62 * 60_000, randomUUID()), experience);
  const restored = parseIdentity(JSON.parse(JSON.stringify(otherThread)));
  assert.match(identityPrompt(restored), /terbiasa menyampaikan/);
  assert.match(identityPrompt(restored), /anggun/);
  assert.equal(restored.candidates.length, 0);
  assert.doesNotMatch(identityPrompt({ ...restored, enabled: false }), /terbiasa menyampaikan/);
});

test("ungrounded observations and reversals leave identity intact", () => {
  const initial = applyReview(emptyIdentity(), propose(preference), evidence(start), "Pesan yang berbeda.");
  assert.equal(initial.candidates.length, 0);
  const s = applyReview(initial, propose(preference), evidence(start), experience);
  const established = applyReview(s, propose(preference), evidence(start + 86400_000), experience);
  const retract = proposalSchema.parse({ observations: [], retract: [{ key: preference.key, quote: "Aku ingin kebiasaan itu berhenti." }] });
  assert.equal(applyReview(established, retract, evidence(start + 90_000_000), "Baiklah.").established.length, 1);
  assert.equal(applyReview(established, retract, evidence(start + 90_000_000), retract.retract[0].quote).established.length, 0);
});
