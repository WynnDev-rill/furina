type BackgroundProvider = {
  name: string;
  enabled: boolean | undefined;
  request: () => Promise<Response | null>;
};

export async function requestBackgroundChain(providers: BackgroundProvider[]) {
  let response: Response | null = null;
  const failures: { name: string; status: number | null }[] = [];
  for (const provider of providers) {
    if (!provider.enabled) continue;
    await response?.body?.cancel().catch(() => undefined);
    response = await provider.request().catch(() => new Response(null, { status: 503 }));
    if (response?.ok) return { response, provider: provider.name, failures };
    failures.push({ name: provider.name, status: response?.status ?? null });
  }
  return { response, provider: null, failures };
}
