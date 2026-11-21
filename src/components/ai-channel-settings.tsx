import { useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { GeminiKeySettings } from "./gemini-key-settings";
import { Switch } from "./ui/switch";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { getAiChannelSettings, setLovableChannel } from "@/lib/ai-usage.functions";

const channels = [
  ["chat", "Percakapan utama"],
  ["background", "Pekerjaan latar belakang"],
] as const;

export function AiChannelSettings({
  userId,
  openAccount,
}: {
  userId?: string | null;
  openAccount: () => void;
}) {
  const getSettings = useServerFn(getAiChannelSettings);
  const change = useServerFn(setLovableChannel);
  const [settings, setSettings] = useState<Awaited<ReturnType<typeof getAiChannelSettings>>>();
  const [backgroundProvider, setBackgroundProvider] = useState<"openrouter" | "nvidia">(
    "openrouter",
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const readGeneration = useRef(0);

  useEffect(() => {
    if (!userId) return;
    let current = true;
    async function reload() {
      if (!userId || running.current) return;
      const generation = readGeneration.current;
      try {
        const result = await getSettings({ data: { userId } });
        if (current && !running.current && generation === readGeneration.current) {
          setSettings(result);
          setError("");
        }
      } catch {
        if (current && generation === readGeneration.current)
          setError("Pengaturan AI belum dapat dimuat.");
      }
    }
    void reload();
    const timer = window.setInterval(reload, 12000);
    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [getSettings, userId]);

  async function save(channel: "chat" | "background", enabled: boolean) {
    if (!userId || running.current) return;
    running.current = true;
    readGeneration.current++;
    setBusy(true);
    setError("");
    try {
      await change({ data: { userId, channel, enabled } });
      setSettings((previous) => (previous ? { ...previous, [channel]: enabled } : previous));
    } catch {
      setError("Pengaturan Lovable belum dapat disimpan.");
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <section className="settings-group space-y-3 p-4">
        <h3 className="text-sm font-semibold">AI default · Lovable</h3>
        {!userId && (
          <p className="text-sm text-muted-foreground">Masuk untuk mengatur penyedia AI.</p>
        )}
        {channels.map(([id, title]) => (
          <div className="flex items-center justify-between gap-3" key={id}>
            <Label htmlFor={`lovable-${id}`}>{title}</Label>
            <Switch
              id={`lovable-${id}`}
              checked={settings?.[id] ?? true}
              disabled={!settings || busy}
              onCheckedChange={(enabled) => void save(id, enabled)}
            />
          </div>
        ))}
        {error && (
          <p role="alert" className="text-sm">
            {error}
          </p>
        )}
        {settings?.issues.map((issue, index) => (
          <p key={index} role="status" className="text-sm text-muted-foreground">
            {issue}
          </p>
        ))}
      </section>
      <h3 className="px-4 text-sm font-semibold">AI opsional</h3>
      <h4 className="px-4 text-sm text-muted-foreground">Percakapan utama</h4>
      <GeminiKeySettings userId={userId} openAccount={openAccount} provider="gemini" />
      <div className="space-y-2 px-4">
        <Label htmlFor="furina-background-provider">Pekerjaan latar belakang</Label>
        <Select
          value={backgroundProvider}
          onValueChange={(value) =>
            setBackgroundProvider(value === "nvidia" ? "nvidia" : "openrouter")
          }
        >
          <SelectTrigger id="furina-background-provider" className="settings-control">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="settings-select-menu">
            <SelectItem value="openrouter">OpenRouter</SelectItem>
            <SelectItem value="nvidia">NVIDIA</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <GeminiKeySettings
        key={backgroundProvider}
        userId={userId}
        openAccount={openAccount}
        provider={backgroundProvider}
      />
      <p className="px-4 text-xs text-muted-foreground">
        Urutan tugas latar saat penyedia aktif: OpenRouter, NVIDIA, lalu Lovable.
      </p>
    </div>
  );
}
