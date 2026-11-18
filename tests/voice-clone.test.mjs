import assert from "node:assert/strict";
import test from "node:test";
import { sourceFunction } from "./source-function.mjs";

function xttsFixture({ stalled = false, crlf = false } = {}) {
  let controller;
  let cancelled = false;
  const calls = [];
  const stream = new ReadableStream({
    start(value) {
      controller = value;
      if (!stalled) {
        const newline = crlf ? "\r\n" : "\n";
        controller.enqueue(
          new TextEncoder().encode(
            `event: complete${newline}data: [{"url":"https://coqui-xtts.hf.space/audio.wav"}]${newline}${newline}`,
          ),
        );
      }
    },
    cancel() {
      cancelled = true;
    },
  });
  const call = sourceFunction("../src/lib/furina.functions.ts", "callXttsSpace", {
    AbortSignal: { timeout: () => AbortSignal.timeout(25) },
    fetch: async (url, init = {}) => {
      calls.push({ url, signal: init.signal });
      if (url.endsWith("/upload")) return Response.json(["/tmp/sample.wav"]);
      if (url.endsWith("/call/predict")) return Response.json({ event_id: "test" });
      init.signal?.addEventListener("abort", () => controller.error(init.signal.reason), {
        once: true,
      });
      return new Response(stream);
    },
  });
  return {
    call: () => call("Hello", "YQ==", "audio/wav", "ja"),
    calls,
    cancelled: () => cancelled,
    close: () => {
      try {
        controller.close();
      } catch {}
    },
  };
}

test("a stalled XTTS stream is interrupted by the request deadline", async () => {
  const f = xttsFixture({ stalled: true });
  let timer;
  try {
    const result = await Promise.race([
      f.call().then(
        () => "unexpected success",
        () => "aborted",
      ),
      new Promise((resolve) => {
        timer = setTimeout(() => resolve("hung"), 180);
      }),
    ]);
    assert.equal(result, "aborted");
    assert.ok(f.calls.every(({ signal }) => signal instanceof AbortSignal));
  } finally {
    clearTimeout(timer);
    f.close();
  }
});

test("XTTS releases the event stream after receiving a complete result", async () => {
  const f = xttsFixture();
  try {
    assert.equal(await f.call(), "https://coqui-xtts.hf.space/audio.wav");
    assert.equal(f.cancelled(), true);
  } finally {
    f.close();
  }
});

test("XTTS accepts CRLF event delimiters", async () => {
  const f = xttsFixture({ crlf: true });
  const timer = setTimeout(f.close, 50);
  try {
    assert.equal(await f.call(), "https://coqui-xtts.hf.space/audio.wav");
  } finally {
    clearTimeout(timer);
    f.close();
  }
});
