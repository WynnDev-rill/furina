import { useEffect, useRef, useState, type FormEvent } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  addGeminiKey,
  getGeminiKeySettings,
  removeGeminiKey,
  setGeminiProvider,
  addOpenRouterKey,
  getOpenRouterKeySettings,
  removeOpenRouterKey,
  setOpenRouterProvider,
  addNvidiaKey,
  getNvidiaKeySettings,
  removeNvidiaKey,
  setNvidiaProvider,
} from "@/lib/ai-usage.functions";

type Settings = {
  enabled: boolean;
  eligible: boolean;
  keys: { id: string; suffix: string; invalid: boolean }[];
};

export function GeminiKeySettings({
  userId,
  openAccount,
  provider = "gemini",
}: {
  userId?: string | null;
  openAccount: () => void;
  provider?: "gemini" | "openrouter" | "nvidia";
}) {
  const providers = {
    gemini: {
      name: "Gemini",
      get: getGeminiKeySettings,
      add: addGeminiKey,
      remove: removeGeminiKey,
      set: setGeminiProvider,
    },
    openrouter: {
      name: "OpenRouter",
      get: getOpenRouterKeySettings,
      add: addOpenRouterKey,
      remove: removeOpenRouterKey,
      set: setOpenRouterProvider,
    },
    nvidia: {
      name: "NVIDIA",
      get: getNvidiaKeySettings,
      add: addNvidiaKey,
      remove: removeNvidiaKey,
      set: setNvidiaProvider,
    },
  } as const;
  const { name, get, add, remove, set } = providers[provider];
  const getSettings = useServerFn(get);
  const addKey = useServerFn(add);
  const removeKey = useServerFn(remove);
  const setProvider = useServerFn(set);
  const [settings, setSettings] = useState<Settings>();
  const [secret, setSecret] = useState("");
  const actionRunning = useRef(false);
  const readGeneration = useRef(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (!userId) return;
    let ignore = false;
    const reload = () => {
      if (actionRunning.current) return;
      const generation = readGeneration.current;
      getSettings({ data: { userId } }).then(
        (data) => {
          if (!ignore && generation === readGeneration.current) {
            setSettings(data);
            setLoadError(false);
          }
        },
        () => {
          if (!ignore && generation === readGeneration.current) setLoadError(true);
        },
      );
    };
    reload();
    return () => {
      ignore = true;
    };
  }, [getSettings, userId, loadAttempt, provider]);

  async function update(action: () => Promise<void>) {
    if (!userId || actionRunning.current) return;
    actionRunning.current = true;
    readGeneration.current++;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
      try {
        setSettings(await getSettings({ data: { userId } }));
        setLoadError(false);
      } catch {
        setLoadError(true);
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Perubahan belum dapat disimpan.");
    } finally {
      actionRunning.current = false;
      setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userId || (!settings && !loadError)) return;
    void update(async () => {
      await addKey({ data: { userId, key: secret } });
      setSecret("");
      setStatus("API key tersimpan.");
    });
  }

  return (
    <section className="settings-group space-y-3 p-4" aria-label={`API key ${name}`}>
      {!userId || settings?.eligible === false ? (
        <>
          <p className="text-sm text-muted-foreground">
            {userId
              ? `API key ${name} tersedia untuk usia 18+. Kamu bisa menambahkan tanggal lahir di Akun & data.`
              : `Masuk ke akun Furina untuk menambahkan API key ${name}.`}
          </p>
          <Button type="button" variant="outline" onClick={openAccount}>
            Buka Akun &amp; data
          </Button>
        </>
      ) : (
        <form className="space-y-2" onSubmit={save}>
          <Label htmlFor={`furina-${provider}-key`}>API key {name}</Label>
          <div className="flex flex-wrap gap-2">
            <Input
              id={`furina-${provider}-key`}
              className="min-w-32 flex-1"
              type="password"
              placeholder={`Tempel API key ${name}`}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              maxLength={300}
              required
            />
            <Button type="submit" disabled={busy || (!settings && !loadError) || !secret.trim()}>
              Simpan
            </Button>
          </div>
        </form>
      )}
      {error && (
        <p role="alert" className="text-sm">
          {error}
        </p>
      )}
      {status && (
        <p role="status" className="text-sm">
          {status}
        </p>
      )}
      {loadError && (
        <div className="flex flex-wrap items-center gap-2">
          <p role="alert" className="text-sm">
            Daftar API key belum dapat dimuat.
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => {
              setLoadError(false);
              setLoadAttempt((attempt) => attempt + 1);
            }}
          >
            Coba lagi
          </Button>
        </div>
      )}
      {userId && settings && !loadError && (
        <>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor={`furina-${provider}-direct`}>Gunakan API key {name}</Label>
            <Switch
              id={`furina-${provider}-direct`}
              checked={settings.enabled && settings.eligible}
              disabled={
                busy ||
                !settings.eligible ||
                (!settings.enabled && !settings.keys.some((key) => !key.invalid))
              }
              onCheckedChange={(enabled) =>
                void update(() => setProvider({ data: { userId, enabled } }))
              }
            />
          </div>
          {settings.eligible && (
            <p className="text-xs text-muted-foreground">
              {settings.enabled
                ? provider === "nvidia"
                  ? "NVIDIA aktif untuk pekerjaan latar."
                  : `${name} diprioritaskan.`
                : `API key ${name} nonaktif.`}
            </p>
          )}
          <ul className="divide-y divide-border/50">
            {settings.keys.map((key) => (
              <li
                key={key.id}
                className="flex min-h-11 items-center justify-between gap-2 py-1 text-sm"
              >
                <span>
                  <span className="font-mono">•••• {key.suffix}</span>
                  {key.invalid && <span className="ml-2 text-muted-foreground">Tidak aktif</span>}
                </span>
                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={busy}
                    aria-label={`Hapus API key berakhiran ${key.suffix}`}
                    onClick={() => void update(() => removeKey({ data: { userId, id: key.id } }))}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
