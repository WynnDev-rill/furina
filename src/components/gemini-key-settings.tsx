import { useEffect, useState, type FormEvent } from "react";
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
} from "@/lib/ai-usage.functions";

type Settings = Awaited<ReturnType<typeof getGeminiKeySettings>>;

export function GeminiKeySettings({
  userId,
  openAccount,
}: {
  userId?: string | null;
  openAccount: () => void;
}) {
  const getSettings = useServerFn(getGeminiKeySettings);
  const addKey = useServerFn(addGeminiKey);
  const removeKey = useServerFn(removeGeminiKey);
  const setProvider = useServerFn(setGeminiProvider);
  const [settings, setSettings] = useState<Settings>();
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (!userId) return;
    let ignore = false;
    getSettings({ data: { userId } }).then(
      (data) => {
        if (!ignore) setSettings(data);
      },
      () => {
        if (!ignore) setLoadError(true);
      },
    );
    return () => {
      ignore = true;
    };
  }, [getSettings, userId, loadAttempt]);

  async function update(action: () => Promise<void>) {
    if (!userId || busy) return;
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
    <section className="settings-group space-y-3 p-4" aria-label="API key Gemini">
      {!userId || settings?.eligible === false ? (
        <>
          <p className="text-sm text-muted-foreground">
            {userId
              ? "API key Gemini tersedia untuk usia 18+. Kamu bisa menambahkan tanggal lahir di Akun & data."
              : "Masuk ke akun Furina untuk menambahkan API key Gemini."}
          </p>
          <Button type="button" variant="outline" onClick={openAccount}>
            Buka Akun &amp; data
          </Button>
        </>
      ) : (
        <form className="space-y-2" onSubmit={save}>
          <Label htmlFor="furina-gemini-key">API key Gemini</Label>
          <div className="flex flex-wrap gap-2">
            <Input
              id="furina-gemini-key"
              className="min-w-32 flex-1"
              type="password"
              placeholder="Tempel API key Gemini"
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
      {userId && settings && settings.keys.length > 0 && !loadError && (
        <>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="furina-gemini-direct">Gunakan Gemini langsung</Label>
            <Switch
              id="furina-gemini-direct"
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
          {settings.eligible && settings.enabled && (
            <p className="text-xs text-muted-foreground">
              Gemini menerima isi chat dan konteks yang relevan.
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
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
