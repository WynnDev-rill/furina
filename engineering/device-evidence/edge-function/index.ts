import { createClient } from "npm:@supabase/supabase-js@2.106.2";

const BUCKET = "furina-backups";
const REQUEST_PATH = ".engineering/device-evidence/request.json";
const RESULT_PREFIX = ".engineering/device-evidence/results";
const OWNER_USER_SHA256 = "423e8e5dc4bd553ac5f8ebd9f46725669d206403f78c4613e6b166e17b281ca1";
const GITHUB_AUDIENCE = "furina-device-evidence";
const GITHUB_REPOSITORY = "WynnDev-rill/furina";
const GITHUB_WORKFLOW_REF = "WynnDev-rill/furina/.github/workflows/furina-device-evidence.yml@refs/heads/main";
const GITHUB_JWKS = "https://token.actions.githubusercontent.com/.well-known/jwks";
const MAX_REQUEST_BYTES = 128_000;
const MAX_RESULT_BYTES = 512_000;

const cors = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, apikey, content-type, x-client-info",
  "access-control-allow-methods": "POST, OPTIONS",
  "content-type": "application/json; charset=utf-8",
};

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

function publishableKey() {
  const modern = Deno.env.get("SUPABASE_PUBLISHABLE_KEYS");
  if (modern) {
    const parsed = JSON.parse(modern) as Record<string, string>;
    const key = parsed.default ?? Object.values(parsed)[0];
    if (key) return key;
  }
  const legacy = Deno.env.get("SUPABASE_ANON_KEY");
  if (!legacy) throw new Error("Supabase publishable key unavailable");
  return legacy;
}

function adminClient() {
  return createClient(Deno.env.get("SUPABASE_URL")!, secretKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

function bearer(req: Request) {
  const value = req.headers.get("authorization") ?? "";
  if (!value.toLowerCase().startsWith("bearer ")) return "";
  return value.slice(7).trim();
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const raw = atob(padded);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

function decodeJsonPart(value: string) {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value))) as Record<string, unknown>;
}

async function verifyGithubOidc(token: string) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("invalid GitHub OIDC token");
  const header = decodeJsonPart(parts[0]);
  const claims = decodeJsonPart(parts[1]);
  if (header.alg !== "RS256" || typeof header.kid !== "string") throw new Error("unsupported GitHub OIDC algorithm");

  const jwksResponse = await fetch(GITHUB_JWKS, { headers: { accept: "application/json" } });
  if (!jwksResponse.ok) throw new Error("GitHub JWKS unavailable");
  const jwks = await jwksResponse.json() as { keys?: JsonWebKey[] };
  const jwk = jwks.keys?.find((item) => item.kid === header.kid);
  if (!jwk) throw new Error("GitHub signing key not found");
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  const signature = decodeBase64Url(parts[2]);
  if (!await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, signature, signed)) {
    throw new Error("invalid GitHub OIDC signature");
  }

  const now = Math.floor(Date.now() / 1000);
  const audience = claims.aud;
  const audienceOk = audience === GITHUB_AUDIENCE || (Array.isArray(audience) && audience.includes(GITHUB_AUDIENCE));
  if (claims.iss !== "https://token.actions.githubusercontent.com" || !audienceOk) throw new Error("invalid GitHub OIDC issuer/audience");
  if (typeof claims.exp !== "number" || claims.exp <= now) throw new Error("expired GitHub OIDC token");
  if (typeof claims.nbf === "number" && claims.nbf > now + 30) throw new Error("GitHub OIDC token not active");
  if (claims.repository !== GITHUB_REPOSITORY) throw new Error("wrong GitHub repository");
  if (claims.workflow_ref !== GITHUB_WORKFLOW_REF) throw new Error("wrong GitHub workflow provenance");
  if (claims.ref !== "refs/heads/main") throw new Error("GitHub control request must originate from main");
  return claims;
}

async function sha256(value: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes)).map((part) => part.toString(16).padStart(2, "0")).join("");
}

async function requireOwnerUser(req: Request) {
  const token = bearer(req);
  if (!token) throw new Response("missing auth", { status: 401 });
  const client = createClient(Deno.env.get("SUPABASE_URL")!, publishableKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${token}` } },
  });
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) throw new Response("invalid auth", { status: 401 });
  if (await sha256(data.user.id) !== OWNER_USER_SHA256) throw new Response("not authorized for engineering evidence", { status: 403 });
  return data.user;
}

async function readObject(path: string) {
  const { data, error } = await adminClient().storage.from(BUCKET).download(path);
  if (error) {
    if ((error as { statusCode?: string | number }).statusCode === "404" || /not found/i.test(error.message)) return null;
    throw error;
  }
  const text = await data.text();
  return JSON.parse(text) as Record<string, unknown>;
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

function requireString(value: unknown, name: string, maxLength: number) {
  if (typeof value !== "string" || value.trim().length === 0 || value.length > maxLength) throw new Error(`invalid ${name}`);
  return value.trim();
}

function validateInputs(value: unknown, benchmarkVersion: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid inputs");
  const inputs = value as Record<string, unknown>;
  if (inputs.schemaVersion !== 1 || inputs.benchmarkVersion !== benchmarkVersion || !Array.isArray(inputs.scenarios)) throw new Error("invalid input manifest");
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
  const targetCommit = requireString(body.targetCommit, "targetCommit", 40).toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(targetCommit)) throw new Error("invalid targetCommit");
  const benchmarkVersion = requireString(body.benchmarkVersion, "benchmarkVersion", 80);
  const expiresAt = requireString(body.expiresAt, "expiresAt", 80);
  const expiresMs = Date.parse(expiresAt);
  if (!Number.isFinite(expiresMs) || expiresMs <= Date.now() || expiresMs > Date.now() + 24 * 60 * 60 * 1000) throw new Error("invalid expiresAt");
  const { inputs } = validateInputs(body.inputs, benchmarkVersion);
  return { schemaVersion: 1, requestId, targetCommit, benchmarkVersion, expiresAt, inputs, status: "requested", requestedAt: new Date().toISOString() };
}

function validateResult(result: unknown, request: Record<string, unknown>) {
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("invalid result");
  const record = result as Record<string, unknown>;
  if (record.schemaVersion !== 1 || record.actualModelRun !== true) throw new Error("result is not an actual model run");
  if (record.requestId !== request.requestId || record.commit !== request.targetCommit || record.benchmarkVersion !== request.benchmarkVersion) throw new Error("result provenance mismatch");
  const privacy = record.privacy as Record<string, unknown> | undefined;
  if (!privacy || privacy.syntheticInputsOnly !== true || privacy.containsSecrets !== false || privacy.containsPersonalConversation !== false || privacy.persistedToUserMemory !== false) throw new Error("invalid result privacy boundary");
  if (!record.model || typeof record.model !== "object" || Array.isArray(record.model)) throw new Error("missing model metadata");
  const model = record.model as Record<string, unknown>;
  requireString(model.provider, "model provider", 120);
  requireString(model.identifier, "model identifier", 240);
  if (!Array.isArray(record.scenarios)) throw new Error("missing result scenarios");
  const expectedInputs = request.inputs as Record<string, unknown>;
  const expected = validateInputs(expectedInputs, String(request.benchmarkVersion)).ids;
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

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
  const contentLength = Number(req.headers.get("content-length") ?? "0");
  if (contentLength > MAX_RESULT_BYTES) return json({ error: "payload too large" }, 413);

  try {
    const body = await req.json() as Record<string, unknown>;
    const action = requireString(body.action, "action", 40);

    if (action === "control_request" || action === "control_collect") {
      await verifyGithubOidc(bearer(req));
      if (action === "control_request") {
        const request = validateControlRequest(body);
        if (JSON.stringify(request).length > MAX_REQUEST_BYTES) throw new Error("request manifest too large");
        const existing = await readObject(REQUEST_PATH);
        if (existing?.requestId === request.requestId) {
          if (existing.targetCommit !== request.targetCommit || existing.benchmarkVersion !== request.benchmarkVersion) {
            return json({ error: "requestId provenance conflict" }, 409);
          }
          if (existing.status === "completed") {
            return json({ ok: true, requestId: request.requestId, alreadyCompleted: true });
          }
          if (existing.status === "requested" && Date.parse(String(existing.expiresAt)) > Date.now()) {
            return json({ ok: true, requestId: request.requestId, alreadyRequested: true });
          }
        }
        if (existing?.status === "requested" && Date.parse(String(existing.expiresAt)) > Date.now()) {
          return json({ error: "another evidence request is active" }, 409);
        }
        await writeObject(REQUEST_PATH, request);
        return json({ ok: true, requestId: request.requestId });
      }
      const requestId = requireString(body.requestId, "requestId", 120);
      const request = await readObject(REQUEST_PATH);
      if (!request || request.requestId !== requestId) return json({ ready: false, reason: "request_not_found" });
      const result = await readObject(`${RESULT_PREFIX}/${requestId}.json`);
      return result ? json({ ready: true, result }) : json({ ready: false, reason: "result_pending" });
    }

    await requireOwnerUser(req);
    const request = await readObject(REQUEST_PATH);
    if (action === "request") {
      if (!request || request.status !== "requested" || Date.parse(String(request.expiresAt)) <= Date.now()) return json({ request: null });
      return json({ request });
    }
    if (action === "result") {
      if (!request || request.status !== "requested" || Date.parse(String(request.expiresAt)) <= Date.now()) return json({ error: "no active request" }, 409);
      const result = validateResult(body.result, request);
      const serialized = JSON.stringify(result);
      if (serialized.length > MAX_RESULT_BYTES) return json({ error: "result too large" }, 413);
      await writeObject(`${RESULT_PREFIX}/${request.requestId}.json`, result);
      await writeObject(REQUEST_PATH, { ...request, status: "completed", completedAt: new Date().toISOString() });
      return json({ ok: true, requestId: request.requestId });
    }

    return json({ error: "unknown action" }, 400);
  } catch (error) {
    if (error instanceof Response) return new Response(await error.text(), { status: error.status, headers: cors });
    return json({ error: error instanceof Error ? error.message : "request failed" }, 400);
  }
});
