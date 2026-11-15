import { z } from "zod";

export const messageQuote = z.object({
  id: z.string().uuid(),
  role: z.enum(["user", "assistant"]),
  excerpt: z.string().min(1).max(200),
});
export type MessageQuote = z.infer<typeof messageQuote>;

export function branchPrefix<T extends { id: string; replyTo?: MessageQuote }>(
  messages: T[],
  before: number,
  uuid: () => string,
) {
  const prefix = messages.slice(0, before);
  const ids = new Map(prefix.map((m) => [m.id, uuid()]));
  return prefix.map((m) => ({
    ...m,
    id: ids.get(m.id)!,
    replyTo: m.replyTo && { ...m.replyTo, id: ids.get(m.replyTo.id) ?? m.replyTo.id },
  }));
}
