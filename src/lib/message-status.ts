export function recoverMessageStatuses<T extends { role: string; status?: string }>(
  messages: T[],
): T[] {
  return messages.map((message, index) => {
    if (message.role !== "user" || !["sending", "sent"].includes(message.status ?? ""))
      return message;
    // An answer can be durable even when the final user-status write failed.
    return { ...message, status: messages[index + 1]?.role === "assistant" ? "read" : "failed" };
  });
}
