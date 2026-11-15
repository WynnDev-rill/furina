import { useEffect, useState, type FormEvent } from "react";
import { useServerFn } from "@tanstack/react-start";
import { ExternalLink, KeyRound, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  addGeminiKey,
  getAiUsage,
  removeGeminiKey,
  setGeminiProvider,
} from "@/lib/ai-usage.functions";

type Usage = Awaited<ReturnType<typeof getAiUsage>>;
const number = new Intl.NumberFormat("id-ID");
const panel = "settings-group space-y-3 p-4";

export function AiUsageSettings({ userId }: { userId?: string | null }) {
  const getUsage = useServerFn(getAiUsage);
  const addKey = useServerFn(addGeminiKey);
  const removeKey = useServerFn(removeGeminiKey);
  const setProvider = useServerFn(setGeminiProvider);
  const [usage, setUsage] = useState<Usage>();
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (!userId) return;
    let ignore = false;
    getUsage({ data: { userId } }).then(
      (data) => {
        if (!ignore) setUsage(data);
      },
      () => {
        if (!ignore) setError("Penggunaan belum dapat dimuat.");
      },
    );
    return () => {
      ignore = true;
    };
  }, [getUsage, userId, loadAttempt]);

  async function update(action: () => Promise<unknown>) {
    if (!userId || busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      setUsage(await getUsage({ data: { userId } }));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Perubahan belum dapat disimpan.");
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    if (!userId) return;
    void update(async () => {
      await addKey({ data: { userId, key: secret } });
      setSecret("");
    });
  }

  return (
    <div className="space-y-3">
      <section className={panel}>
        <h3 className="font-semibold">Penggunaan chat bulan ini</h3>
        {usage ? (
          <dl className="divide-y divide-border/50">
            {usage.usage.map(({ provider, requests, tokens }) => (
              <div
                key={provider}
                className="flex flex-wrap items-baseline justify-between gap-x-3 py-2 text-sm"
              >
                <dt>{provider === "gemini" ? "Gemini langsung" : "Lovable AI Gateway"}</dt>
                <dd className="text-muted-foreground">
                  {number.format(requests)} balasan
                  {tokens > 0 && ` · ${number.format(tokens)} token`}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">
            {userId
              ? error
                ? "Data belum tersedia."
                : "Memuat…"
              : "Masuk untuk melihat penggunaan akunmu."}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Kuota resmi dan waktu reset tersedia di dasbor penyedia.
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <a
            href="https://lovable.dev/projects/1a1621d2-7cae-4972-8cdc-269778779da2"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 underline underline-offset-4"
          >
            Lovable <ExternalLink size={13} aria-hidden="true" />
          </a>
          <a
            href="https://aistudio.google.com/usage"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 underline underline-offset-4"
          >
            Google AI Studio <ExternalLink size={13} aria-hidden="true" />
          </a>
        </div>
      </section>
      {error && (
        <p role="alert" className="px-2 text-sm">
          {error}
        </p>
      )}
      {error && userId && !usage && (
        <Button
          variant="outline"
          onClick={() => {
            setError("");
            setLoadAttempt((attempt) => attempt + 1);
          }}
        >
          Coba lagi
        </Button>
      )}
      {usage && userId && (
        <section className={panel}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="flex items-center gap-2 font-semibold">
              <KeyRound size={16} aria-hidden="true" /> API key Gemini
            </h3>
            <Switch
              aria-label="Gunakan Gemini langsung untuk chat"
              checked={usage.enabled && usage.eligible && usage.keys.length > 0}
              disabled={
                busy ||
                !usage.eligible ||
                !usage.keys.length ||
                (!usage.enabled && !usage.keys.some((key) => !key.invalid))
              }
              onCheckedChange={(enabled) =>
                void update(() => setProvider({ data: { userId, enabled } }))
              }
            />
          </div>
          {usage.keys.length > 0 && (
            <ul className="divide-y divide-border/50">
              {usage.keys.map((key) => (
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
          )}
          {usage.eligible ? (
            <>
              <p className="text-xs text-muted-foreground">
                Gemini menerima isi chat dan konteks yang relevan. Hindari data pribadi jika memakai
                tingkat gratis.
              </p>
              {usage.keys.length < 5 ? (
                <form className="flex flex-wrap gap-2" onSubmit={save}>
                  <Input
                    className="min-w-32 flex-1"
                    type="password"
                    aria-label="API key Gemini baru"
                    placeholder="Tempel API key Gemini"
                    autoComplete="off"
                    autoCapitalize="none"
                    spellCheck={false}
                    value={secret}
                    onChange={(event) => setSecret(event.target.value)}
                    maxLength={256}
                    required
                  />
                  <Button type="submit" disabled={busy || secret.trim().length < 20}>
                    Simpan
                  </Button>
                </form>
              ) : (
                <p className="text-sm text-muted-foreground">Batas 5 API key tercapai.</p>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Masukkan tanggal lahir di Akun &amp; data. Gemini langsung tersedia untuk usia 18+.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
