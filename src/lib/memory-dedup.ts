// Used only after deciding that two recordings describe the same fact.
export function memoryTextKey(value: string) {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ").toLocaleLowerCase("id");
}

export function combineMemoryText(values: string[]) {
  const pieces = values.flatMap((value) =>
    value
      .trim()
      .split(/(?<=[.!?])\s+(?=\p{Lu})|\r?\n+/u)
      .filter(Boolean),
  );
  const unique = [...new Map(pieces.map((piece) => [memoryTextKey(piece), piece])).values()];
  const combined = unique.join("\n");
  // Keep very large memories separate. Never truncate a source to force a merge.
  return combined.length <= 800 ? combined : null;
}
