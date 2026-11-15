export const defaultMemoryPolicy = {
  use_saved: true,
  use_history: true,
  history_after: null as string | null,
};

export function historyAfter<T extends { at?: number }>(messages: T[], cutoff: string | null) {
  if (!cutoff) return messages;
  const boundary = Date.parse(cutoff);
  return messages.filter(({ at }) => at !== undefined && at > boundary);
}

export const memorySections = [
  { label: "Tentangmu", kinds: ["fact"] },
  { label: "Preferensi dan cara kerja", kinds: ["preference", "style"] },
  { label: "Relasi dan kejadian", kinds: ["relation", "episodic"] },
  { label: "Percakapan terdahulu", kinds: ["summary", "meta_summary"] },
];
