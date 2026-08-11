# Furina On-Demand Device Evidence Protocol

## Purpose
Provide the engineering company with truthful target-Android local-model captures without continuous request-data polling, Google/Supabase user login, GitHub credentials in the APK, or personal conversation data in engineering evidence.

The APK exposes no permanent benchmark control. A temporary evidence card appears only while engineering has a valid active device request for the exact installed build, and the benchmark starts only after the user explicitly presses the start action.

This protocol is an evidence transport. It does not weaken `engineering/evidence/behavioral-run.schema.json`: raw device capture is not canonical BEHAVIORAL evidence until generated outputs are independently scored and assembled into that schema.

## Request rule
Create a device request only when current triage/review actually requires behavioral or device evidence that an installed target build can provide. Do not create speculative requests merely because an hourly shift ran.

The mutable `FURINA_LAB_STATE` object in issue #42 carries at most one `deviceEvidenceRequest`:

```json
{
  "status": "requested",
  "requestId": "device-<unique-id>",
  "targetCommit": "<40-char source commit embedded in the installed APK>",
  "benchmarkVersion": "1",
  "expiresAt": "<ISO-8601 timestamp>"
}
```

`targetCommit` is the APK source provenance being measured, not automatically the current PR head. Never use capture from one commit to certify behavioral claims about a different head.

Editing issue #42 with `status=requested` triggers `.github/workflows/furina-device-evidence.yml`. The workflow generates the model-input manifest from the exact requested commit and sends only that manifest to the device mailbox. Judge expectations never enter device input.

## Official-build device enrollment
The engineering evidence identity is independent of the user's backup/login account.

For a successful non-PR `main` APK build:
1. GitHub Actions generates a random 256-bit one-time enrollment token and masks it from Actions logs.
2. The raw token is passed only to Gradle and embedded in that exact official APK as `BuildConfig.EVIDENCE_ENROLLMENT_TOKEN`.
3. The workflow sends only `SHA-256(token)` plus the exact `github.sha` and expiry to the Edge Function.
4. That control operation uses GitHub Actions OIDC with audience `furina-device-evidence`. The Edge Function accepts it only from this repository, `refs/heads/main`, and `.github/workflows/build-furina-apk.yml@refs/heads/main`, with the OIDC `sha` equal to the enrollment commit.
5. On first evidence probe, Android creates an RSA-2048 signing key in Android Keystore and registers its public key using the one-time token. The backend consumes the enrollment for that exact commit and pins the engineering evidence identity to the device.

The APK derives its stable device identifier from the application package plus Android `ANDROID_ID`, then hashes it before transport. No Google account, Supabase Auth user, email, personal profile, backup recovery key, or GitHub credential participates in enrollment.

Normal APK updates preserve the Android Keystore key. A later official `main` APK can refresh exact-build enrollment for the same pinned device with a new one-time token. A different device ID is rejected by the private engineering mailbox.

## Demand-driven request discovery
The Edge Function stores the authoritative request, then emits a Supabase Realtime Broadcast on `furina-device-evidence-signal`. The broadcast is deliberately only a generic public wake signal; it carries no scenario data, target SHA, device ID, user data, credentials, or evidence payload.

A foreground Furina native session subscribes to that signal using the project's public Supabase client. On receipt it asks the native evidence bridge to perform one signed request fetch. This is event-driven request discovery, not periodic request-data polling. Lifecycle probes on app activation, focus, or return to foreground remain only as reconnect/missed-signal fallback.

If Furina is fully closed or Android suspends the WebView, Realtime is not treated as a guaranteed background wake mechanism. The stored request remains authoritative and is discovered automatically the next time the native session becomes active. Discovery alone never starts model inference.

When a valid request is discovered, Furina shows a temporary in-app card stating that Loop Engineering requires data for the next repair. The card is absent when no valid request exists. The user may explicitly start the benchmark from that card; there is no automatic idle-time benchmark.

## Device request/result authentication
Request fetch and result upload use a short-lived challenge rather than a reusable bearer credential.

For each operation the registered device obtains a random challenge from the Edge Function and signs a canonical message with its Android Keystore private key. The signature binds:
- protocol domain;
- operation (`request` or `result`);
- hashed device identifier;
- challenge ID and nonce;
- exact APK commit;
- SHA-256 of the raw result payload for uploads.

The backend verifies the signature against the pinned public key and consumes the challenge. A valid signature still does not bypass provenance checks: a request is returned only when its `targetCommit` matches the installed APK commit, and a result must match that same request/commit/benchmark version.

No long-lived server secret, service-role key, GitHub token, private key, or user access token is embedded in the APK.

## Device behavior
When no active request exists, the APK performs no benchmark and no periodic evidence-data fetch. A foreground session may keep the lightweight public Realtime signal subscription open; no model run or request payload transfer occurs until a request signal or lifecycle fallback probe happens.

When the pinned device receives a valid active request:
- show the temporary engineering-data card only for that active request;
- do not run inference until the user explicitly presses the start action;
- if ordinary Furina inference is currently busy, refuse/defer the benchmark and keep the request available for manual retry;
- never cancel an ordinary Furina generation merely to collect evidence;
- require exact `targetCommit == BuildConfig.GIT_SHA`;
- require the selected local model to be installed;
- expose benchmark progress to the temporary card as completed/total synthetic scenarios;
- run only the synthetic scenario setup and latest user turn;
- bypass `UnifiedAiEngine.generate()` so synthetic turns are never persisted into user conversation/memory/relationship maintenance;
- discard all persistence-derived continuity fields before inference;
- isolate every scenario with an explicit throwaway native session boundary followed by the exact scenario session, forcing `setSystemPrompt`/chat-KV reset while reusing loaded GGUF weights;
- unload native benchmark state after capture;
- upload raw generated outputs plus bounded runtime metadata and explicit privacy flags.

If result upload temporarily fails, the web agent retries the already-produced raw report instead of spending another local-model run only because transport failed.

The evidence card is status-only except for the explicit start action. No benchmark conversation, personal chat message, or user-memory entry is created. The card disappears when there is no active request and briefly confirms successful upload before hiding.

## Transport trust boundary
The build workflow authenticates enrollment setup with GitHub Actions OIDC. The engineering control workflow authenticates request/collect operations with a separately bound GitHub Actions OIDC provenance. The device authenticates request/result operations with its Android Keystore key. These authorities are intentionally separate.

The Edge Function stores enrollment records, the pinned device public key, request/result objects, and short-lived challenges under a private engineering prefix in the existing private storage bucket. Normal clients do not receive service-role access to that prefix.

The Realtime wake channel is public because its payload contains only `{ "signal": true }`. Public visibility of that generic signal grants no request or evidence access; those still require the registered device signature and exact-build match.

Never put API keys, raw enrollment tokens, auth tokens, recovery keys, personal messages, memory rows, or user identifiers in evidence artifacts/comments.

## Capture result
The raw result must bind:
- `requestId`;
- exact 40-character `commit`;
- `benchmarkVersion`;
- `actualModelRun=true`;
- local provider/model identity;
- every requested scenario ID exactly once;
- non-empty model output per scenario;
- runtime timing metadata;
- `syntheticInputsOnly=true`;
- `containsSecrets=false`;
- `containsPersonalConversation=false`;
- `persistedToUserMemory=false`.

Raw capture must not contain rubric scores. Scoring is a separate evidence-reset step using the judge manifest.

## Engineering consumption
A ready capture is published as a GitHub Actions artifact with a `FURINA_DEVICE_EVIDENCE_READY_V1` issue comment pointer. Before using it, the shift must directly fetch the workflow artifact and verify request ID, checksum, exact target commit, benchmark version, scenario set, `actualModelRun`, and privacy fields.

The control workflow never stays alive waiting for the target device. Each issue-state update performs one idempotent request submission followed by one immediate collect attempt. If the device result is not ready, the run publishes a pending pointer and exits. The same non-expired request remains authoritative in issue #42; a later engineering shift re-enters the workflow and collects an already completed backend result without rerunning the device benchmark.

After scoring raw outputs against the canonical judge manifest, create a schema-valid behavioral record only if all required provenance/evidence conditions are satisfied. A device capture for an older installed build can diagnose that build but cannot approve a newer behavioral change.

## Failure behavior
Missing/invalid device enrollment, invalid challenge/signature, model unavailable, target SHA mismatch, expired request, malformed output, checksum mismatch, moved provenance, unavailable artifact, or control-plane signal failure all fail closed. Record the blocker/recheck condition; do not fabricate outputs or downgrade the evidence requirement.
