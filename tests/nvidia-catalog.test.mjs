import assert from "node:assert/strict";
import test from "node:test";
import { availableNvidiaChatModels } from "../src/lib/nvidia-catalog.ts";
export const access = {
  data: [
    { id: "minimaxai/minimax-m3.1-flash" },
    { id: "nvidia/nemotron-3-ultra-550b-a55b" },
    { id: "nvidia/nemotron-3.5-super-vl-120b-a12b" },
    { id: "nvidia/nemotron-3.5-content-safety" },
  ],
};
export function resource(name, publisher, free = true) {
  return {
    name,
    displayName: name,
    description: "Multimodal chat model accepting text and images",
    labels: [
      { key: "publisher", values: [publisher] },
      { key: "playgroundType", values: ["chat"] },
      {
        key: "nimType",
        unresolvedValues: free ? ["nim_type_preview"] : ["nim_type_upgrade_available"],
      },
    ],
    attributes: [{ key: "PREVIEW", value: String(free) }],
  };
}
export const catalog = {
  results: [
    {
      resources: [
        resource("nemotron-3.5-super-vl-120b-a12b", "nvidia"),
        resource("minimax-m3.1-flash", "minimaxai"),
        resource("nemotron-3-ultra-550b-a55b", "nvidia"),
        resource("nemotron-3.5-content-safety", "nvidia"),
      ],
    },
  ],
};

test("only ranks live accessible free conversational models, with evaluated MiniMax first", () => {
  assert.deepEqual(
    availableNvidiaChatModels(access, catalog).map((m) => m.id),
    [
      "minimaxai/minimax-m3.1-flash",
      "nvidia/nemotron-3-ultra-550b-a55b",
      "nvidia/nemotron-3.5-super-vl-120b-a12b",
    ],
  );
});
test("partner-only endpoints and inaccessible catalog entries never become candidates", () => {
  const paid = { results: [{ resources: [resource("minimax-m3.1-flash", "minimaxai", false)] }] };
  assert.deepEqual(availableNvidiaChatModels(access, paid), []);
  assert.deepEqual(availableNvidiaChatModels({ data: [] }, catalog), []);
});
test("unknown or malformed free metadata fails closed", () => {
  for (const data of [null, {}, { results: [{ resources: [null, {}] }] }])
    assert.deepEqual(availableNvidiaChatModels(access, data), []);
});
test("normalizes NVIDIA catalog aliases and deduplicates scored results", () => {
  const model = resource("nemotron-3_5-super-vl-120b-a12b", "nvidia");
  const result = availableNvidiaChatModels(access, { results: [{ resources: [model, model] }] });
  assert.equal(result.length, 1);
  assert.equal(result[0].vision, true);
});

test("fresh catalog verification is cached briefly and fails closed after expiry", async () => {
  const { createNvidiaCatalogLoader } = await import("../src/lib/nvidia-catalog.ts");
  let time = 1000,
    calls = 0;
  const load = createNvidiaCatalogLoader(
    async (url, init) => {
      assert.equal(new URL(url).origin, "https://api.ngc.nvidia.com");
      assert.equal(init.redirect, "manual");
      calls++;
      if (calls > 1) return new Response(null, { status: 503 });
      return Response.json({ ...catalog, resultTotal: 3 });
    },
    () => time,
  );
  const first = await load();
  assert.equal(await load(), first);
  assert.equal(calls, 1);
  time += 300001;
  await assert.rejects(load(), /diverifikasi/);
  assert.equal(calls, 2);
});

test("structured Image-to-Text and VLM labels identify live Nano Omni image support", () => {
  const row = resource("nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia");
  row.description = "An omni-modal reasoning model that understands images, video, speech, text.";
  row.labels.push({ key: "usecase", values: ["Image-to-Text"] });
  row.labels.find((x) => x.key === "general")?.values.splice(0);
  const found = availableNvidiaChatModels(
    { data: [{ id: "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning" }] },
    { results: [{ resources: [row] }] },
  );
  assert.equal(found[0].vision, true);
});
test("download availability is independent of a hosted Free Endpoint", () => {
  const row = resource("minimax-m3.1-flash", "minimaxai");
  row.attributes.push({ key: "AVAILABLE", value: "false" });
  assert.equal(availableNvidiaChatModels(access, { results: [{ resources: [row] }] }).length, 1);
});
