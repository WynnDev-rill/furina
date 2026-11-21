export function mainChatProvider(
  settings: {
    use_gemini?: boolean;
    lovable_chat?: boolean;
  } | null,
  signedIn: boolean,
  eligible: boolean,
) {
  return {
    personalGeminiEnabled: signedIn && eligible && !!settings?.use_gemini,
    lovableChat: settings?.lovable_chat ?? true,
  };
}
