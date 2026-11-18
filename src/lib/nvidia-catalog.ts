import { z } from "zod";

export type NvidiaChatModel = { id: string; label: string; vision: boolean };
const label = z.object({
  key: z.string(),
  values: z.array(z.string()).optional(),
  unresolvedValues: z.array(z.string()).optional(),
});
const resource = z.object({
  name: z.string(),
  displayName: z.string().optional(),
  description: z.string().optional(),
  labels: z.array(label),
  attributes: z.array(z.object({ key: z.string(), value: z.string() })),
});
const accessible = z.object({ data: z.array(z.object({ id: z.string() })) });
const catalogSchema = z.object({ results: z.array(z.object({ resources: z.array(z.unknown()) })) });

function quality(id: string) {
  if (/safety|guard|embed|rerank|parse|reward/.test(id)) return 0;
  // Quality ordering is evaluated, availability and free status are discovered live.
  if (/^minimaxai\/minimax-m\d/.test(id)) return 100;
  if (/^nvidia\/nemotron-[\d.]+-ultra/.test(id)) return 90;
  if (/^nvidia\/nemotron-[\d.]+-super/.test(id)) return 80;
  if (/^nvidia\/nemotron-[\d.]+-lightning/.test(id)) return 50;
  if (/^nvidia\/nemotron-[\d.]+-bolt/.test(id)) return 85;
  if (/^nvidia\/nemotron-[\d.]+-nano/.test(id)) return 40;
  return 0;
}

export function availableNvidiaChatModels(access: unknown, catalog: unknown): NvidiaChatModel[] {
  const models = accessible.safeParse(access);
  const free = catalogSchema.safeParse(catalog);
  if (!models.success || !free.success) return [];
  const normalize = (value: string) => value.toLowerCase().replaceAll("_", ".");
  const ids = new Map(models.data.data.map(({ id }) => [normalize(id), id]));
  const found = new Map<string, NvidiaChatModel>();
  for (const group of free.data.results)
    for (const entry of group.resources) {
      const parsed = resource.safeParse(entry);
      if (!parsed.success) continue;
      const row = parsed.data;
      const labels = (key: string) =>
        row.labels
          .filter((item) => item.key === key)
          .flatMap((item) => [...(item.values ?? []), ...(item.unresolvedValues ?? [])]);
      if (
        !labels("nimType").includes("nim_type_preview") ||
        !row.attributes.some(({ key, value }) => key === "PREVIEW" && value === "true") ||
        !labels("playgroundType").includes("chat")
      )
        continue;
      const publisher = labels("publisher")[0];
      if (!publisher) continue;
      const id = ids.get(normalize(`${publisher}/${row.name}`));
      if (!id || !quality(id)) continue;
      found.set(id, {
        id,
        label: row.displayName ?? id,
        vision: /multimodal|omni.modal|vision.language|text and image|image-to-text|\bvlm\b/i.test(
          [row.description ?? "", ...labels("general"), ...labels("usecase")].join(" "),
        ),
      });
    }
  return [...found.values()].sort(
    (a, b) =>
      quality(b.id) - quality(a.id) || b.id.localeCompare(a.id, undefined, { numeric: true }),
  );
}

export function createNvidiaCatalogLoader(request = fetch, now = Date.now) {
  let cached: { value: unknown; expires: number } | null = null;
  let pending: Promise<unknown> | null = null;
  return async function load(): Promise<unknown> {
    if (cached && cached.expires > now()) return cached.value;
    if (pending) return pending;
    pending = (async () => {
      const groups: { resources: unknown[] }[] = [];
      for (let page = 0; page < 4; page++) {
        const url = new URL("https://api.ngc.nvidia.com/v2/search/catalog/resources/ENDPOINT");
        url.searchParams.set(
          "q",
          JSON.stringify({
            page,
            pageSize: 100,
            query: "*:*",
            filters: [{ field: "label", value: "nim_type_preview" }],
            orderBy: [{ field: "nameSort", value: "ASC" }],
          }),
        );
        url.searchParams.set("group-labels-by-labelset", "true");
        const response = await request(url, {
          redirect: "manual",
          signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error("Katalog gratis NVIDIA belum dapat diverifikasi.");
        const raw = await response.json();
        const parsed = catalogSchema.safeParse(raw);
        if (!parsed.success || !Number.isFinite(raw.resultTotal))
          throw new Error("Katalog gratis NVIDIA tidak dapat dibaca.");
        groups.push(...parsed.data.results);
        if ((page + 1) * 100 >= raw.resultTotal) {
          const value = { results: groups };
          cached = { value, expires: now() + 5 * 60_000 };
          return value;
        }
      }
      throw new Error("Katalog NVIDIA berubah. Daftar model perlu diperiksa kembali.");
    })();
    try {
      return await pending;
    } finally {
      pending = null;
    }
  };
}
