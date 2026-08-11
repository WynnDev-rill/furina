# Furina public-visibility readiness

This repository must remain private until every hard blocker below is satisfied.

## Signing continuity

- Keep the existing Android release key while it remains private and uncompromised. Replacing it merely because the repository may become public is unnecessary and risks breaking update continuity.
- The release keystore must not exist in the Git working tree or public history.
- Trusted CI must receive the existing key only through `FURINA_RELEASE_KEYSTORE_B64` plus `FURINA_KEYSTORE_PASSWORD`, `FURINA_KEY_ALIAS`, and `FURINA_KEY_PASSWORD` repository/environment secrets.
- External fork pull requests must never receive release-signing material and may only perform unsigned/debug validation.
- The expected release certificate SHA-256 remains enforced by the APK workflow.

## Environment configuration

- `.env` is not tracked. `.env.example` contains client-facing publishable configuration only.
- Service-role keys, provider API keys, personal access tokens, signing credentials, and private keys must never be committed.
- Supabase publishable/anon keys are not treated as authorization boundaries. RLS/storage policy is the authorization boundary.

## Backend authorization

The historical `memories` migration granted anon/public access. Before public visibility, production must have the corrective `harden_memories_rls` migration applied and verified:

- anon has no table access to `public.memories`;
- authenticated users can operate only on rows where `auth.uid() = user_id`;
- the five-argument `match_memories` RPC remains service-role-only;
- storage buckets that contain user data remain owner-scoped/authenticated-only.

A committed migration is not proof that production has applied it. Production verification is required.

## History boundary

Deleting sensitive files from the current tree does not remove them from old Git commits. **Do not change this existing repository from private to public while the old release keystore or signing credentials remain reachable in its history.**

Use one of these safe publication boundaries:

1. thoroughly rewrite and verify all reachable Git/PR history before changing this repository's visibility; or
2. preferred for a temporary public-build period: publish a new history-clean repository/mirror from a sanitized snapshot while keeping the original Furina repository private.

The second option has the smaller blast radius and preserves the private repository as the canonical archive.

## Repository controls before public use

- protect `main` against force-push/deletion;
- require review/status checks appropriate to the public build repository;
- keep workflow permissions minimal;
- never use `pull_request_target` to execute untrusted fork code with privileged tokens/secrets;
- keep public-repository safety gate green;
- review Actions artifacts/logs before exposing an existing repository.

## Current gate

Public visibility is **BLOCKED** until:

- signing key is safely stored outside Git and trusted CI can reconstruct/sign with the same certificate;
- production Supabase RLS hardening is applied and verified;
- a history-clean publication boundary is chosen/verified;
- `main` protection is enabled.
