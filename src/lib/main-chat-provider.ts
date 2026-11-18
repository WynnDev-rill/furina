export function mainChatProvider(
  settings: {
    chat_provider?: string;
    use_nvidia_chat?: boolean;
    use_gemini?: boolean;
    lovable_chat?: boolean;
  } | null,
  signedIn: boolean,
  eligible: boolean,
) {
  if (signedIn && settings?.chat_provider === "nvidia") {
    if (!eligible) throw new Error("API key percakapan tersedia untuk usia 18 tahun ke atas.");
    if (!settings.use_nvidia_chat)
      throw new Error("NVIDIA percakapan nonaktif. Aktifkan di AI dan API Key.");
    return { nvidia: true, personalGeminiEnabled: false, lovableChat: false };
  }
  return {
    nvidia: false,
    personalGeminiEnabled: signedIn && eligible && !!settings?.use_gemini,
    lovableChat: settings?.lovable_chat ?? true,
  };
}
