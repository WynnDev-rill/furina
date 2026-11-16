export async function requestOpenRouter<T>(
  keys: T[],
  readKey: (row: T) => Promise<string | null>,
  request: (key: string, signal: AbortSignal) => Promise<Response>,
  markInvalid: (row: T) => Promise<void>,
  timeoutMs = 15000,
) {
  const deadline = Date.now() + timeoutMs;
  let last: Response | null = null;
  for (const row of keys) {
    const key = await readKey(row);
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    if (!key) continue;
    await last?.body?.cancel().catch(() => undefined);
    last = await request(key, AbortSignal.timeout(Math.min(8000, remaining))).catch(
      () => new Response(null, { status: 504 }),
    );
    if (last.status === 401) await markInvalid(row);
    if (![401, 402, 403, 404, 429, 500, 502, 503, 504].includes(last.status)) return last;
  }
  return last;
}
