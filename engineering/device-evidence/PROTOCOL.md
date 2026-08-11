# Furina On-Demand Device Evidence Protocol

## Purpose
Provide the engineering company with truthful target-Android local-model captures without adding a benchmark button, continuous device polling, GitHub credentials to the APK, or personal conversation data to engineering evidence.

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

## Device behavior
When no active request exists, the APK performs no benchmark and no recurring evidence polling. The invisible web agent may make a lightweight foreground probe when the native page/auth session becomes active or visible.

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

After scoring the raw outputs against the canonical judge manifest, create a schema-valid behavioral record only if all required provenance/evidence conditions are satisfied. A device capture for an older installed build can diagnose that build but cannot approve a newer behavioral change.

## Failure behavior
Missing auth, model unavailable, target SHA mismatch, expired request, timeout, malformed output, checksum mismatch, moved provenance, or unavailable artifact all fail closed. Record the blocker/recheck condition; do not fabricate outputs or downgrade the evidence requirement.
