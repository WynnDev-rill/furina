# Experimental providers

## Conversation

Stage 1 uses AI Horde's official anonymous key `0000000000`. It is intentionally kept behind a provider module because anonymous requests have the lowest queue priority and may be restricted under high load.

## Voice

Stage 1 temporarily uses the device Japanese speech engine to validate speaking state and mouth motion. Stage 3 will replace this with the community VOICEVOX/TTS Quest integration and retain device TTS only as fallback.
