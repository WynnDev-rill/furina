import { createClient } from "npm:@supabase/supabase-js@2.106.2";

const BUCKET = "furina-backups";
const ROOT = "engineering/device-evidence";
const REQUEST_PATH = `${ROOT}/request.json`;
const RESULT_PREFIX = `${ROOT}/results`;
const DEVICE_PATH = `${ROOT}/device.json`;
const ENROLLMENT_PREFIX = `${ROOT}/enrollments`;
const CHALLENGE_PATH = `${ROOT}/challenge.json`;
const SIGNAL_TOPIC = "furina-device-evidence-signal";
const GITHUB_AUDIENCE = "furina-device-evidence";
const GITHUB_REPOSITORY = "WynnDev-rill/furina";
const CONTROL_WORKFLOW_REF = "WynnDev-rill/furina/.github/workflows/furina-device-evidence.yml@refs/heads/main";
const BUILD_WORKFLOW_REF = "WynnDev-rill/furina/.github/workflows/build-furina-apk.yml@refs/heads/main";
const GITHUB_JWKS = "https://token.actions.githubusercontent.com/.well-known/jwks";
const SIGNATURE_DOMAIN = "furina-device-evidence-v1";
const MAX_REQUEST_BYTES = 128_000;
const MAX_RESULT_BYTES = 512_000;
const MAX_ENROLLMENT_MS = 120 * 24 * 60 * 60 * 1000;
const CHALLENGE_TTL_MS = 2 * 60 * 1000;

const cors = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, apikey, content-type, x-client-info",
  "access-control-allow-methods": "POST, OPTIONS",
  "content-type": "application/json; charset=utf-8",
};

class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: cors });
}

function secretKey() {
  const modern = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (modern) {
    const parsed = JSON.parse(modern) as Record<string, string>;
    const key = parsed.default ?? Object.values(parsed)[0];
    if (key) return key;
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!legacy) throw new Error("Supabase admin key unavailable");
  return legacy;
}

function adminClient() {
  return createClient(Deno.env.get("SUPABASE_URL")!, secretKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

function bearer(req: Request) {
  const value = req.headers.get("authorization") ?? "";
  return value.toLowerCase().startsWith("bearer ") ? value.slice(7).trim() : "";
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

function decodeBase64(value: string) {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}

function decodeJsonPart(value: string) {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value))) as Record<string, unknown>;
}

async function verifyGithubOidc(token: string, expectedWorkflowRef: string) {
  if (!token) throw new HttpError(401, "missing GitHub OIDC token");
  const parts = token.split(".");
  if (parts.length !== 3) throw new HttpError(401, "invalid GitHub OIDC token");
  const header = decodeJsonPart(parts[0]);
  const claims = decodeJsonPart(parts[1]);
  if (header.alg !== "RS256" || typeof header.kid !== "string") {
    throw new HttpError(401, "unsupported GitHub OIDC algorithm");
  }

  const jwksResponse = await fetch(GITHUB_JWKS, { headers: { accept: "application/json" } });
  if (!jwksResponse.ok) throw new Error("GitHub JWKS unavailable");
  const jwks = await jwksResponse.json() as { keys?: JsonWebKey[] };
  const jwk = jwks.keys?.find((item) => item.kid === header.kid);
  if (!jwk) throw new HttpError(401, "GitHub signing key not found");
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const signature = decodeBase64Url(parts[2]);
  const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  if (!await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, signature, signed)) {
    throw new HttpError(401, "invalid GitHub OIDC signature");
  }

  const now = Math.floor(Date.now() / 1000);
  const audience = claims.aud;
  const audienceOk = audience === GITHUB_AUDIENCE || (Array.isArray(audience) && audience.includes(GITHUB_AUDIENCE));
  if (claims.iss !== "https://token.actions.githubusercontent.com" || !audienceOk) {
    throw new HttpError(403, "invalid GitHub OIDC issuer/audience");
  }
  if (typeof claims.exp !== "number" || claims.exp <= now) throw new HttpError(401, "expired GitHub OIDC token");
  if (typeof claims.nbf === "number" && claims.nbf > now + 30) throw new HttpError(401, "GitHub OIDC token not active");
  if (claims.repository !== GITHUB_REPOSITORY) throw new HttpError(403, "wrong GitHub repository");
  if (claims.workflow_ref !== expectedWorkflowRef) throw new HttpError(403, "wrong GitHub workflow provenance");
  if (claims.ref !== "refs/heads/main") throw new HttpError(403, "GitHub control request must originate from main");
  return claims;
}

async function sha256(value: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes)).map((part) => part.toString(16).padStart(2, "0")).join("");
}

function randomHex(byteCount = 32) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteCount));
  return Array.from(bytes).map((part) => part.toString(16).padStart(2, "0")).join("");
}

async function readObject(path: string) {
  const { data, error } = await adminClient().storage.from(BUCKET).download(path);
  if (error) {
    const code = (error as { statusCode?: string | number }).statusCode;
    if (code === 404 || code === "404" || /not found/i.test(error.message)) return null;
    throw error;
  }
  return JSON.parse(await data.text()) as Record<string, unknown>;
}

async function writeObject(path: string, body: unknown) {
  const serialized = JSON.stringify(body);
  const { error } = await adminClient().storage.from(BUCKET).upload(
    path,
    new Blob([serialized], { type: "application/json" }),
    { upsert: true, contentType: "application/json", cacheControl: "0" },
  );
  if (error) throw error;
}

async function deleteObject(path: string) {
  const { error } = await adminClient().storage.from(BUCKET).remove([path]);
  if (error && !/not found/i.test(error.message)) throw error;
}

async function signalRequest() {
  const baseUrl = Deno.env.get("SUPABASE_URL");
  if (!baseUrl) throw new Error("Supabase URL unavailable");
  const key = secretKey();
  const response = await fetch(`${baseUrl}/realtime/v1/api/broadcast`, {
    method: "POST",
    headers: {
      apikey: key,
      authorization: `Bearer ${key}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      messages: [{ topic: SIGNAL_TOPIC, event: "request", payload: { signal: true } }],
    }),
  });
  if (!response.ok) throw new Error(`Realtime request signal failed (${response.status})`);
}

function requireString(value: unknown, name: string, maxLength: number) {
  if (typeof value !== "string" || value.trim().length === 0 || value.length > maxLength) {
    throw new Error(`invalid ${name}`);
  }
  return value.trim();
}

function requireCommit(value: unknown, name = "commit") {
  const commit = requireString(value, name, 40).toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(commit)) throw new Error(`invalid ${name}`);
  return commit;
}

function requireHex64(value: unknown, name: string) {
  const text = requireString(value, name, 64).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(text)) throw new Error(`invalid ${name}`);
  return text;
}

function requireDeviceId(value: unknown) {
  return requireHex64(value, "deviceId");
}

function requirePublicKey(value: unknown) {
  const encoded = requireString(value, "publicKeySpki", 4096);
  let bytes: Uint8Array;
  try {
    bytes = decodeBase64(encoded);
  } catch {
    throw new Error("invalid publicKeySpki encoding");
  }
  if (bytes.byteLength < 128 || bytes.byteLength > 2048) throw new Error("invalid publicKeySpki size");
  return { encoded, bytes };
}

async function importDeviceKey(encoded: string) {
  return await crypto.subtle.importKey(
    "spki",
    requirePublicKey(encoded).bytes,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
}

function validateInputs(value: unknown, benchmarkVersion: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid inputs");
  const inputs = value as Record<string, unknown>;
  if (inputs.schemaVersion !== 1 || inputs.benchmarkVersion !== benchmarkVersion || !Array.isArray(inputs.scenarios)) {
    throw new Error("invalid input manifest");
  }
  if (inputs.scenarios.length < 1 || inputs.scenarios.length > 128) throw new Error("invalid scenario count");
  const ids = new Set<string>();
  for (const raw of inputs.scenarios) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("invalid scenario");
    const scenario = raw as Record<string, unknown>;
    if ("expect" in scenario || "scores" in scenario) throw new Error("judge data leaked into model inputs");
    const id = requireString(scenario.scenarioId, "scenarioId", 120);
    if (ids.has(id)) throw new Error("duplicate scenarioId");
    ids.add(id);
    requireString(scenario.user, "scenario user", 4_000);
    if (!Array.isArray(scenario.setup) || scenario.setup.length > 32) throw new Error("invalid scenario setup");
    for (const rawTurn of scenario.setup) {
      if (!rawTurn || typeof rawTurn !== "object" || Array.isArray(rawTurn)) throw new Error("invalid setup turn");
      const turn = rawTurn as Record<string, unknown>;
      if (turn.role !== "user" && turn.role !== "assistant") throw new Error("invalid setup role");
      requireString(turn.content, "setup content", 4_000);
    }
  }
  return { inputs, ids };
}

function validateControlRequest(body: Record<string, unknown>) {
  const requestId = requireString(body.requestId, "requestId", 120);
  if (!/^[A-Za-z0-9._:-]{8,120}$/.test(requestId)) throw new Error("invalid requestId");
  const targetCommit = requireCommit(body.targetCommit, "targetCommit");
  const benchmarkVersion = requireString(body.benchmarkVersion, "benchmarkVersion", 80);
  const expiresAt = requireString(body.expiresAt, "expiresAt", 80);
  const expiresMs = Date.parse(expiresAt);
  if (!Number.isFinite(expiresMs) || expiresMs <= Date.now() || expiresMs > Date.now() + 24 * 60 * 60 * 1000) {
    throw new Error("invalid expiresAt");
  }
  const { inputs } = validateInputs(body.inputs, benchmarkVersion);
  return {
    schemaVersion: 1,
    requestId,
    targetCommit,
    benchmarkVersion,
    expiresAt,
    inputs,
    status: "requested",
    requestedAt: new Date().toISOString(),
  };
}

function validateResult(result: unknown, request: Record<string, unknown>) {
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("invalid result");
  const record = result as Record<string, unknown>;
  if (record.schemaVersion !== 1 || record.actualModelRun !== true) throw new Error("result is not an actual model run");
  if (record.requestId !== request.requestId || record.commit !== request.targetCommit || record.benchmarkVersion !== request.benchmarkVersion) {
    throw new Error("result provenance mismatch");
  }
  const privacy = record.privacy as Record<string, unknown> | undefined;
  if (!privacy || privacy.syntheticInputsOnly !== true || privacy.containsSecrets !== false || privacy.containsPersonalConversation !== false || privacy.persistedToUserMemory !== false) {
    throw new Error("invalid result privacy boundary");
  }
  if (!record.model || typeof record.model !== "object" || Array.isArray(record.model)) throw new Error("missing model metadata");
  const model = record.model as Record<string, unknown>;
  requireString(model.provider, "model provider", 120);
  requireString(model.identifier, "model identifier", 240);
  if (!Array.isArray(record.scenarios)) throw new Error("missing result scenarios");
  const expected = validateInputs(request.inputs, String(request.benchmarkVersion)).ids;
  if (record.scenarios.length !== expected.size) throw new Error("result scenario count mismatch");
  const seen = new Set<string>();
  for (const raw of record.scenarios) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("invalid result scenario");
    const scenario = raw as Record<string, unknown>;
    if ("scores" in scenario) throw new Error("raw device capture must not self-score");
    const id = requireString(scenario.scenarioId, "result scenarioId", 120);
    if (!expected.has(id) || seen.has(id)) throw new Error("result scenario provenance mismatch");
    seen.add(id);
    requireString(scenario.output, "model output", 12_000);
  }
  return record;
}

function enrollmentPath(commit: string) {
  return `${ENROLLMENT_PREFIX}/${commit}.json`;
}

function deviceCanonical(action: string, deviceId: string, challengeId: string, nonce: string, appCommit: string, payloadHash: string) {
  return [SIGNATURE_DOMAIN, action, deviceId, challengeId, nonce, appCommit, payloadHash].join("\n");
}

async function verifyDeviceCall(body: Record<string, unknown>, action: "request" | "result") {
  const deviceId = requireDeviceId(body.deviceId);
  const challengeId = requireHex64(body.challengeId, "challengeId");
  const nonce = requireHex64(body.nonce, "nonce");
  const appCommit = requireCommit(body.appCommit, "appCommit");
  const signatureEncoded = requireString(body.signature, "signature", 4096);

  const device = await readObject(DEVICE_PATH);
  if (!device || device.deviceId !== deviceId || typeof device.publicKeySpki !== "string") {
    throw new HttpError(403, "device not registered");
  }

  const challenge = await readObject(CHALLENGE_PATH);
  if (!challenge || challenge.deviceId !== deviceId || challenge.challengeId !== challengeId || challenge.nonce !== nonce) {
    throw new HttpError(401, "invalid device challenge");
  }
  if (Date.parse(String(challenge.expiresAt)) <= Date.now()) {
    await deleteObject(CHALLENGE_PATH);
    throw new HttpError(401, "expired device challenge");
  }

  let resultRaw = "";
  let payloadHash = "";
  if (action === "result") {
    resultRaw = requireString(body.resultRaw, "resultRaw", MAX_RESULT_BYTES);
    payloadHash = await sha256(resultRaw);
  }
  const canonical = deviceCanonical(action, deviceId, challengeId, nonce, appCommit, payloadHash);
  let signature: Uint8Array;
  try {
    signature = decodeBase64(signatureEncoded);
  } catch {
    await deleteObject(CHALLENGE_PATH);
    throw new HttpError(401, "invalid device signature encoding");
  }
  const key = await importDeviceKey(String(device.publicKeySpki));
  const verified = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    signature,
    new TextEncoder().encode(canonical),
  );
  await deleteObject(CHALLENGE_PATH);
  if (!verified) throw new HttpError(401, "invalid device signature");
  return { deviceId, appCommit, resultRaw };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (contentLength > MAX_RESULT_BYTES + 32_000) return json({ error: "payload too large" }, 413);

  try {
    const body = await req.json() as Record<string, unknown>;
    const action = requireString(body.action, "action", 40);

    if (action === "control_enrollment") {
      const claims = await verifyGithubOidc(bearer(req), BUILD_WORKFLOW_REF);
      const targetCommit = requireCommit(body.targetCommit, "targetCommit");
      if (claims.sha !== targetCommit) throw new HttpError(403, "enrollment commit does not match build OIDC sha");
      const tokenHash = requireHex64(body.tokenHash, "tokenHash");
      const expiresAt = requireString(body.expiresAt, "expiresAt", 80);
      const expiresMs = Date.parse(expiresAt);
      if (!Number.isFinite(expiresMs) || expiresMs <= Date.now() || expiresMs > Date.now() + MAX_ENROLLMENT_MS) {
        throw new Error("invalid enrollment expiry");
      }
      await writeObject(enrollmentPath(targetCommit), {
        schemaVersion: 1,
        targetCommit,
        tokenHash,
        expiresAt,
        createdAt: new Date().toISOString(),
        workflowRunId: claims.run_id,
        status: "active",
      });
      return json({ ok: true, targetCommit });
    }

    if (action === "control_request" || action === "control_collect") {
      await verifyGithubOidc(bearer(req), CONTROL_WORKFLOW_REF);
      if (action === "control_request") {
        const request = validateControlRequest(body);
        if (JSON.stringify(request).length > MAX_REQUEST_BYTES) throw new Error("request manifest too large");
        const existing = await readObject(REQUEST_PATH);
        if (existing?.requestId === request.requestId) {
          if (existing.targetCommit !== request.targetCommit || existing.benchmarkVersion !== request.benchmarkVersion) {
            return json({ error: "requestId provenance conflict" }, 409);
          }
          if (existing.status === "completed") return json({ ok: true, requestId: request.requestId, alreadyCompleted: true });
          if (existing.status === "requested" && Date.parse(String(existing.expiresAt)) > Date.now()) {
            await signalRequest();
            return json({ ok: true, requestId: request.requestId, alreadyRequested: true, signaled: true });
          }
        }
        if (existing?.status === "requested" && Date.parse(String(existing.expiresAt)) > Date.now()) {
          return json({ error: "another evidence request is active" }, 409);
        }
        await writeObject(REQUEST_PATH, request);
        await signalRequest();
        return json({ ok: true, requestId: request.requestId, signaled: true });
      }
      const requestId = requireString(body.requestId, "requestId", 120);
      const request = await readObject(REQUEST_PATH);
      if (!request || request.requestId !== requestId) return json({ ready: false, reason: "request_not_found" });
      const result = await readObject(`${RESULT_PREFIX}/${requestId}.json`);
      return result ? json({ ready: true, result }) : json({ ready: false, reason: "result_pending" });
    }

    if (action === "register") {
      const deviceId = requireDeviceId(body.deviceId);
      const targetCommit = requireCommit(body.targetCommit, "targetCommit");
      const enrollmentToken = requireString(body.enrollmentToken, "enrollmentToken", 128).toLowerCase();
      if (!/^[0-9a-f]{64}$/.test(enrollmentToken)) throw new Error("invalid enrollmentToken");
      const publicKey = requirePublicKey(body.publicKeySpki);
      await importDeviceKey(publicKey.encoded);
      const publicKeyHash = await sha256(publicKey.encoded);
      const enrollment = await readObject(enrollmentPath(targetCommit));
      if (!enrollment || enrollment.targetCommit !== targetCommit || Date.parse(String(enrollment.expiresAt)) <= Date.now()) {
        throw new HttpError(403, "device enrollment unavailable or expired");
      }
      if (await sha256(enrollmentToken) !== enrollment.tokenHash) throw new HttpError(403, "invalid device enrollment token");

      const existingDevice = await readObject(DEVICE_PATH);
      if (existingDevice && existingDevice.deviceId !== deviceId) {
        throw new HttpError(403, "engineering evidence is already bound to another device");
      }
      if (enrollment.status === "consumed") {
        const sameBinding = existingDevice?.deviceId === deviceId &&
          existingDevice?.publicKeySha256 === publicKeyHash &&
          enrollment.consumedDeviceId === deviceId &&
          enrollment.consumedPublicKeySha256 === publicKeyHash;
        if (!sameBinding) throw new HttpError(409, "device enrollment token already consumed");
        return json({ ok: true, deviceId, alreadyRegistered: true });
      }

      const now = new Date().toISOString();
      await writeObject(DEVICE_PATH, {
        schemaVersion: 1,
        deviceId,
        publicKeySpki: publicKey.encoded,
        publicKeySha256: publicKeyHash,
        registeredAt: existingDevice?.registeredAt ?? now,
        updatedAt: now,
        lastEnrollmentCommit: targetCommit,
      });
      await writeObject(enrollmentPath(targetCommit), {
        ...enrollment,
        status: "consumed",
        consumedAt: now,
        consumedDeviceId: deviceId,
        consumedPublicKeySha256: publicKeyHash,
      });
      return json({ ok: true, deviceId });
    }

    if (action === "device_challenge") {
      const deviceId = requireDeviceId(body.deviceId);
      const device = await readObject(DEVICE_PATH);
      if (!device || device.deviceId !== deviceId || typeof device.publicKeySpki !== "string") {
        throw new HttpError(403, "device not registered");
      }
      const challengeId = randomHex(32);
      const nonce = randomHex(32);
      const expiresAt = new Date(Date.now() + CHALLENGE_TTL_MS).toISOString();
      await writeObject(CHALLENGE_PATH, {
        schemaVersion: 1,
        deviceId,
        challengeId,
        nonce,
        createdAt: new Date().toISOString(),
        expiresAt,
      });
      return json({ challengeId, nonce, expiresAt });
    }

    if (action === "request") {
      const verified = await verifyDeviceCall(body, "request");
      const request = await readObject(REQUEST_PATH);
      if (!request || request.status !== "requested" || Date.parse(String(request.expiresAt)) <= Date.now()) {
        return json({ request: null });
      }
      if (request.targetCommit !== verified.appCommit) return json({ request: null, reason: "build_mismatch" });
      return json({ request });
    }

    if (action === "result") {
      const verified = await verifyDeviceCall(body, "result");
      const request = await readObject(REQUEST_PATH);
      if (!request || request.status !== "requested" || Date.parse(String(request.expiresAt)) <= Date.now()) {
        return json({ error: "no active request" }, 409);
      }
      if (request.targetCommit !== verified.appCommit) throw new HttpError(409, "result build mismatch");
      let parsed: unknown;
      try {
        parsed = JSON.parse(verified.resultRaw);
      } catch {
        throw new Error("invalid result JSON");
      }
      const result = validateResult(parsed, request);
      if (JSON.stringify(result).length > MAX_RESULT_BYTES) return json({ error: "result too large" }, 413);
      await writeObject(`${RESULT_PREFIX}/${request.requestId}.json`, result);
      await writeObject(REQUEST_PATH, { ...request, status: "completed", completedAt: new Date().toISOString() });
      return json({ ok: true, requestId: request.requestId });
    }

    return json({ error: "unknown action" }, 400);
  } catch (error) {
    if (error instanceof HttpError) return json({ error: error.message }, error.status);
    return json({ error: error instanceof Error ? error.message : "request failed" }, 400);
  }
});
