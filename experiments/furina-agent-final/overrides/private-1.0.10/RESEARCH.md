# Furina 1.0.10 research notes

This release is a personalization + runtime-ownership pass. It deliberately avoids canned social replies and response rewriting.

Research inputs used before implementation:

- Character.AI Creator Guide: strong characters front-load identity, use concrete behavioral logic rather than adjective piles, keep hard rules short, and use dialogue/behavior examples to establish voice and pacing. Long rule lists make behavior less reliable.
- Dere archetype references: dere labels are shorthand for how affection is expressed, not complete personalities. Main and less-common archetypes overlap and can be combined when treated as situational tendencies rather than mutually exclusive modes.
- Hiyakasudere/Teasedere references: playful/flirtatious teasing is distinct from sadistic or harmful treatment; the useful companion behavior is light provocation that can become sincere.
- Genki references: high energy, initiative, optimism and fast social tempo are the core signals, not a fixed catchphrase.
- Qwen3 guidance: non-thinking models respond best with model-appropriate sampling; excessive repetition should be handled with decoding/context quality rather than scripted replies.

Architecture decisions:

1. Personalization is stored once in Core and shared by Termux + FurinaHub + Online + Local.
2. The UI exposes 20 independent toggles with no combination limit.
3. Runtime compiles selected labels into concise behavioral logic; it does not dump twenty trope definitions verbatim into every prompt.
4. Contradictory traits are treated as situational tension (for example reserved + energetic) instead of one trait deleting another.
5. Potentially dark archetypes remain expressive/fictional personality signals while the existing relationship safety boundary continues to forbid real coercion, isolation, threats, or harm.
6. FurinaHub stops owning update checks. `furina update` is the sole update orchestrator and updates Core + bridge/APK boundary.
7. FurinaHub local model selection writes to the same Core configuration as Termux and must not create independent model state.
8. Hub chat/status uses one long-lived runtime path and bounded in-process state; UI polling must not spawn repeated Termux jobs/processes.
