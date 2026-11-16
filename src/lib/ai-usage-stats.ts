export function getUsageSharePercent(value: number, total: number): number | null {
  if (!Number.isFinite(value) || !Number.isFinite(total) || value <= 0 || total <= 0) return null;
  return Math.min(100, Math.max(1, Math.round((value / total) * 100)));
}

export function nextJakartaMonthReset(now: Date): Date {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Jakarta",
    year: "numeric",
    month: "numeric",
  }).formatToParts(now);
  const year = Number(parts.find((part) => part.type === "year")?.value);
  const month = Number(parts.find((part) => part.type === "month")?.value);
  return new Date(Date.UTC(year, month, 1) - 7 * 60 * 60 * 1000);
}

export function formatResetCountdown(resetAt: string, now: number): string {
  const remaining = Math.max(0, Date.parse(resetAt) - now);
  const totalMinutes = Math.ceil(remaining / 60_000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days} hari ${hours} jam`;
  if (hours > 0) return `${hours} jam ${minutes} menit`;
  return `${minutes} menit`;
}