# Furina On-Demand Device Evidence Protocol

## Purpose
Provide the engineering company with truthful target-Android local-model captures without adding a benchmark button, continuous request-data polling, GitHub credentials to the APK, or personal conversation data to engineering evidence.

This protocol is an evidence transport. It does not weaken `engineering/evidence/behavioral-run.schema.json`: raw device capture is not canonical BEHAVIORAL evidence until the generated outputs are independently scored and assembled into that schema.

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

## Demand-driven wake-up
The Edge Function stores the authoritative request, then emits a Supabase Realtime Broadcast on `furina-device-evidence-signal`. The broadcast is deliberately only a generic wake signal; it carries no scenario data, target SHA, user data, credentials, or evidence payload.

An authenticated foreground Furina session subscribes to that signal. On receipt it performs one authenticated request fetch. This is event-driven request discovery, not periodic request-data polling. Lifecycle probes on app/session activation, focus, or return to foreground remain only as reconnect/missed-signal fallback.

If Furina is fully closed or Android suspends the WebView, Realtime is not treated as a guaranteed background wake mechanism. The stored request remains authoritative and is discovered automatically the next time the native session becomes active. No button is required.

## Device behavior
When no active request exists, the APK performs no benchmark and no periodic evidence fetch. A foreground authenticated session may keep the lightweight Realtime signal subscription open; no model run or request payload transfer occurs until a request signal or lifecycle fallback probe happens.

When an authenticated owner device receives a valid active request:
- wait for a user-idle window;
- cancel/defer if the user interacts;
- require exact `targetCommit == BuildConfig.GIT_SHA`;
- require the selected local model to be installed;
- run only the synthetic scenario setup and latest user turn;
- bypass `UnifiedAiEngine.generate()` so synthetic turns are never persisted into user conversation/memory/relationship maintenance;
- discard all persistence-derived continuity fields before inference;
- unload native benchmark state after capture;
- upload raw generated outputs plus bounded runtime metadata and explicit privacy flags.

No UI, notification, or chat message is created by the evidence agent.

## Transport trust boundary
The APK uses the existing Furina backup Supabase session; no GitHub credential or Supabase admin credential is placed in the client. If no authorized session exists, the evidence agent stays inert.

The control workflow authenticates to the Edge Function with GitHub Actions OIDC bound to this repository, the main-branch device-evidence workflow, and the `furina-device-evidence` audience. The Edge Function keeps request/result objects in a private engineering prefix that normal client RLS cannot read directly.

The Realtime wake channel is public because its payload contains only `{ "signal": true }`. Public visibility of that generic signal grants no request access: request fetch and result upload still require the authorized Furina Supabase user session, while engineering control operations still require the bound GitHub OIDC identity.

Never put API keys, auth tokens, recovery keys, personal messages, memory rows, or user identifiers in evidence artifacts/comments.

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

If an Actions wait window ends before the device responds, keep the same non-expired request in issue #42. A later issue-state update re-enters the idempotent request/collect workflow; an already completed backend result is collected instead of rerunning the device benchmark.

After scoring the raw outputs against the canonical judge manifest, create a schema-valid behavioral record only if all required provenance/evidence conditions are satisfied. A device capture for an older installed build can diagnose that build but cannot approve a newer behavioral change.

## Failure behavior
Missing auth, model unavailable, target SHA mismatch, expired request, timeout, malformed output, checksum mismatch, moved provenance, unavailable artifact, or control-plane signal failure all fail closed. Record the blocker/recheck condition; do not fabricate outputs or downgrade the evidence requirement.
