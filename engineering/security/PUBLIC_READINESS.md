# Furina public-visibility readiness

This repository must remain private until every hard blocker below is satisfied.

## Signing continuity

- Keep the existing Android release key while it remains private and uncompromised.
- The release keystore must not exist in the public working tree or public history.
- Trusted CI receives the existing key only through `FURINA_RELEASE_KEYSTORE_B64`, `FURINA_KEYSTORE_PASSWORD`, `FURINA_KEY_ALIAS`, and `FURINA_KEY_PASSWORD` secrets.
- External fork pull requests must never receive release-signing material and may only perform unsigned/debug validation.
- The APK workflow continues to enforce the expected release certificate SHA-256.

The owner has now stored all four signing values as repository Actions secrets. This satisfies the secret handoff prerequisite, but not the Git-history prerequisite below.

## Active backend authorization

The active Furina Google login + encrypted backup backend is Supabase project `fxebamfwewsvtscrbwxk`.

Live verification on 2026-08-11 confirmed:

- the `furina-backups` storage bucket exists;
- SELECT/INSERT/UPDATE/DELETE policies are restricted to `authenticated` users;
- every policy scopes objects to the folder whose first path segment equals `auth.uid()`;
- the project has no `public.memories` table.

Therefore the historical Lovable/Supabase `smltficntqkoncyrnajx` memories schema is not the authorization boundary for current Furina backup/login and is not a public-readiness blocker. Legacy web/server configuration remains optional and is no longer pinned in `.env.example`.

Supabase publishable keys are client identifiers, not authorization boundaries. RLS/storage policy remains the security boundary.

## Environment configuration

- `.env` is not tracked.
- `.env.example` contains only active client-facing backup configuration plus blank placeholders for optional legacy server configuration.
- Service-role keys, provider API keys, personal access tokens, signing credentials, and private keys must never be committed.

## History boundary

Deleting sensitive files from the current tree does not remove them from old Git commits. The release keystore and signing fallback credentials existed in this repository's history.

**Do not change this existing repository from private to public while those historical commits remain reachable.**

Safe options:

1. thoroughly rewrite and verify all reachable Git/PR history before changing this repository's visibility; or
2. preferred: publish a new history-clean build mirror from the sanitized snapshot while keeping the original Furina repository private.

The second option has the smallest blast radius and preserves the private repository as the canonical archive.

## Repository controls before public use

- protect `main` in the public build repository against force-push/deletion;
- require appropriate review/status checks;
- keep workflow permissions minimal;
- never use `pull_request_target` to execute untrusted fork code with privileged tokens/secrets;
- keep the public-repository safety gate green;
- never copy the private Git history into the public build repository.

## Current gate

Completed:

- existing release signing key retained;
- signing material stored in four GitHub Actions secrets;
- signing material removed from the sanitized candidate tree;
- hardcoded signing fallbacks removed;
- active Furina backup backend identified and its owner-scoped storage policies verified live;
- `.env` removed from the sanitized candidate tree;
- public-repository safety gate added;
- fork PR signing isolation added.

Still required before public visibility:

- use a history-clean publication boundary (preferred public build mirror), or perform and verify a complete sensitive-history rewrite;
- enable `main` protection on whichever repository becomes public.
