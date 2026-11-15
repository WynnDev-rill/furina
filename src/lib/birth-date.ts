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
  const profile =
    age === undefined
      ? " Usia belum tersimpan. Jangan menebak angkanya."
      : ` Usia pengguna saat ini menurut profil akun yang diisi pengguna: ${age} tahun. Jika pengguna bertanya umur atau usia mereka, jawab dengan angka ini. Dahulukan usia profil dari perkiraan dan memori lama. Sebutkan angka usia hanya jika ditanya.`;
  return age !== undefined && age >= 18
    ? base + profile
    : base +
        profile +
        " Terapkan batas yang sesuai anak dan remaja. Jangan lakukan roleplay romantis atau seksual dengan pengguna, jangan mendorong ketergantungan, dan untuk situasi serius anjurkan dukungan orang dewasa tepercaya.";
}

const birthdayTag = "<<<BIRTHDAY>>>";

export function birthdayInstructions(daysUntil: number | undefined, offerGreeting: boolean) {
  if (daysUntil === 0) {
    const today = "\n\nKONTEKS ULANG TAHUN: Ulang tahun pengguna hari ini.";
    return offerGreeting
      ? today +
          ` Jika momennya cocok, tulis satu ucapan singkat dengan suaramu sendiri, sesuai bahasa dan suasana percakapan. Awali dengan satu baris ${birthdayTag} diikuti isi ucapan pada baris yang sama, lalu jawab pesan pengguna di baris berikutnya seperti biasa. Kamu boleh melewati ucapan jika akan mengganggu. Tempatkan seluruh ucapan tambahan pada baris bertanda itu.`
      : today +
          " Jangan memulai ucapan ulang tahun lagi. Jika pengguna membahasnya, tanggapi seperti percakapan biasa.";
  }
  if (daysUntil !== undefined && daysUntil > 0 && daysUntil <= 7) {
    return `\n\nKONTEKS ULANG TAHUN: Ulang tahun pengguna dalam ${daysUntil} hari menurut waktu pengguna. Boleh menyinggungnya secara alami jika relevan, misalnya saat membahas rencana. Jangan mengucapkan selamat sebelum harinya.`;
  }
  return "";
}

export function splitBirthdayReply(output: string) {
  let greeting = "";
  const reply = output
    .replace(/^\s*<<<\s*BIRTHDAY\s*>>>[^\S\r\n]*(.*)$/gim, (_, line: string) => {
      if (!greeting) greeting = line.trim();
      return "";
    })
    .trim();
  return { reply, greeting };
}
