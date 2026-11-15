export function parseBirthDate(value: string, now = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(value + "T00:00:00Z");
  if (!Number.isFinite(+date) || date.toISOString().slice(0, 10) !== value) return null;
  if (value < "1900-01-01" || value > now.toISOString().slice(0, 10)) return null;
  return date;
}

export function localCalendar(now: Date, timezone?: string) {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone ?? "Asia/Jakarta",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now);
    return new Date(
      Date.UTC(
        ...(["year", "month", "day"].map(
          (part, index) =>
            Number(parts.find(({ type }) => type === part)?.value) - (index === 1 ? 1 : 0),
        ) as [number, number, number]),
      ),
    );
  } catch {
    return localCalendar(now, "Asia/Jakarta");
  }
}

export function birthdayContext(value: string, today: Date) {
  const birth = parseBirthDate(value, today);
  if (!birth) return null;
  const year = today.getUTCFullYear(),
    month = birth.getUTCMonth(),
    day = birth.getUTCDate();
  const anniversary = (y: number) =>
    Date.UTC(y, month, Math.min(day, new Date(Date.UTC(y, month + 1, 0)).getUTCDate()));
  const age = year - birth.getUTCFullYear() - Number(+today < anniversary(year));
  const next = +today > anniversary(year) ? anniversary(year + 1) : anniversary(year);
  return { age, year, daysUntil: Math.round((next - +today) / 86_400_000) };
}

export function ageInstructions(age?: number) {
  const base =
    "Bersikap aman untuk semua usia. Hindari konten seksual eksplisit, eksploitasi, dan instruksi berbahaya. Tanggal lahir yang diisi pengguna bukan verifikasi dan tidak membuka akses ke konten dewasa.";
  return age !== undefined && age >= 18
    ? base
    : base +
        " Terapkan batas yang sesuai anak dan remaja. Jangan lakukan roleplay romantis atau seksual dengan pengguna, jangan mendorong ketergantungan, dan untuk situasi serius anjurkan dukungan orang dewasa tepercaya.";
}
