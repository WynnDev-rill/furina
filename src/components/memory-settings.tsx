import { useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Bookmark, Ellipsis, History, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  addMemory,
  clearAllMemories,
  deleteMemory,
  listMemories,
  saveMemoryControl,
  updateMemory,
} from "@/lib/furina.functions";
import { memorySections } from "@/lib/memory-policy";

type MemoryData = Awaited<ReturnType<typeof listMemories>>;
type Memory = MemoryData["memories"][number];
const controls = [
  {
    key: "use_saved",
    icon: Bookmark,
    title: "Memori tersimpan",
    description: "Gunakan detail yang kamu simpan sendiri.",
  },
  {
    key: "use_history",
    icon: History,
    title: "Referensi riwayat",
    description: "Pelajari dan gunakan konteks dari obrolan terdahulu.",
  },
] as const;

export function MemorySettings({ userId }: { userId: string }) {
  const list = useServerFn(listMemories);
  const saveControl = useServerFn(saveMemoryControl);
  const add = useServerFn(addMemory);
  const edit = useServerFn(updateMemory);
  const forget = useServerFn(deleteMemory);
  const clear = useServerFn(clearAllMemories);
  const [data, setData] = useState<MemoryData | null>(null);
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<"summary" | "all">("summary");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState<{ id?: string; text: string } | null>(null);
  const actionRunning = useRef(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!userId) return;
    let current = true;
    list({ data: { userId } })
      .then((payload) => {
        if (current) setData(payload);
      })
      .catch(() => {
        if (current) setError(true);
      });
    return () => {
      current = false;
    };
  }, [list, userId, retry]);

  async function apply(action: () => Promise<unknown>, success: string, after?: () => void) {
    if (actionRunning.current) return;
    actionRunning.current = true;
    setBusy(true);
    setNotice("");
    try {
      await action();
      after?.();
      setData(await list({ data: { userId } }));
      setNotice(success);
    } catch {
      setNotice("Perubahan atau pemuatan ulang gagal. Coba lagi.");
    } finally {
      actionRunning.current = false;
      setBusy(false);
    }
  }

  const memories = data?.memories ?? [];
  const active = memories.filter((m) =>
    m.saved ? data?.policy.use_saved : !m.compressed && data?.policy.use_history,
  );
  const shown = memories.filter((m) =>
    m.content.toLocaleLowerCase("id").includes(query.trim().toLocaleLowerCase("id")),
  );
  const row = (m: Memory) => (
    <li key={m.id} className="memory-note">
      <div>
        <p>{m.content}</p>
        {view === "all" && <small>{m.saved ? "Tersimpan" : "Dari riwayat"}</small>}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button aria-label="Opsi memori" variant="ghost" size="icon" disabled={busy}>
            <Ellipsis size={17} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="glass-surface message-actions">
          {!m.saved && m.content.length <= 800 && (
            <DropdownMenuItem
              onSelect={() =>
                void apply(
                  () => edit({ data: { userId, id: m.id, content: m.content } }),
                  "Memori tersimpan.",
                )
              }
            >
              Simpan ke memori
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={() => setDraft({ id: m.id, text: m.content.slice(0, 800) })}>
            Koreksi
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive"
            onSelect={() => {
              if (
                !confirm(
                  "Hapus memori ini dan mulai ulang konteks otomatis? Pesan lama dan memori tersimpan lainnya tetap ada.",
                )
              )
                return;
              void apply(() => forget({ data: { userId, id: m.id } }), "Memori dihapus.");
            }}
          >
            Lupakan
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );

  if (!data) {
    return (
      <div className="settings-detail glass-surface" aria-live="polite">
        <p>{error ? "Memori belum dapat dimuat." : "Memuat memori…"}</p>
        {error && (
          <Button
            variant="outline"
            onClick={() => {
              setError(false);
              setRetry((n) => n + 1);
            }}
          >
            Coba lagi
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="memory-pages">
      <div className="settings-detail glass-surface memory-controls">
        {controls.map(({ key, icon: Icon, title, description }) => (
          <label key={key} className="memory-control">
            <Icon size={19} aria-hidden="true" />
            <span>
              <strong>{title}</strong>
              <small>{description}</small>
            </span>
            <Switch
              aria-label={title}
              checked={data.policy[key]}
              disabled={busy}
              onCheckedChange={(enabled) =>
                void apply(
                  () => saveControl({ data: { userId, key, enabled } }),
                  enabled ? "Diaktifkan." : "Dijeda.",
                )
              }
            />
          </label>
        ))}
      </div>

      <div className="settings-detail glass-surface memory-reader" aria-busy={busy}>
        <nav className="memory-nav" aria-label="Tampilan memori">
          <button
            type="button"
            aria-pressed={view === "summary"}
            onClick={() => setView("summary")}
          >
            Ringkasan
          </button>
          <button type="button" aria-pressed={view === "all"} onClick={() => setView("all")}>
            Kelola memori
          </button>
        </nav>
        {notice && (
          <p className="memory-notice" role="status">
            {notice}
          </p>
        )}

        {draft ? (
          <form
            className="memory-form"
            onSubmit={(event) => {
              event.preventDefault();
              const content = draft.text.trim();
              if (content.length < 2) return;
              void apply(
                () =>
                  draft.id
                    ? edit({ data: { userId, id: draft.id, content } })
                    : add({ data: { userId, content } }),
                "Memori tersimpan.",
                () => setDraft(null),
              );
            }}
          >
            <label htmlFor="furina-memory-draft">
              {draft.id ? "Koreksi memori" : "Tambah memori"}
            </label>
            <Textarea
              id="furina-memory-draft"
              value={draft.text}
              maxLength={800}
              rows={4}
              onChange={(event) => setDraft({ ...draft, text: event.target.value })}
              disabled={busy}
            />

            <div className="memory-form-actions">
              <Button variant="ghost" type="button" disabled={busy} onClick={() => setDraft(null)}>
                Batal
              </Button>
              <Button type="submit" disabled={busy || draft.text.trim().length < 2}>
                Simpan
              </Button>
            </div>
          </form>
        ) : view === "summary" ? (
          <>
            {memorySections.map(({ label, kinds }) => {
              const items = active
                .filter((m) => kinds.includes(m.kind))
                .sort(
                  (a, b) =>
                    Date.parse(b.created_at) - Date.parse(a.created_at) || a.id.localeCompare(b.id),
                );
              if (!items.length) return null;
              return (
                <section key={label} className="memory-section">
                  <h3>{label}</h3>
                  <ul>{items.slice(0, 3).map(row)}</ul>
                  {items.length > 3 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setQuery("");
                        setView("all");
                      }}
                    >
                      Lihat {items.length - 3} catatan lainnya
                    </Button>
                  )}
                </section>
              );
            })}
            {!active.length && (
              <p className="memory-empty">Belum ada memori aktif untuk dirangkum.</p>
            )}
          </>
        ) : (
          <>
            <div className="memory-tools">
              <div>
                <Search size={16} aria-hidden="true" />
                <Input
                  type="search"
                  aria-label="Cari memori"
                  placeholder="Cari memori…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <Button variant="outline" className="shrink-0" onClick={() => setDraft({ text: "" })}>
                <Plus size={16} /> Tambah
              </Button>
            </div>
            {shown.length ? (
              <ul>{shown.map(row)}</ul>
            ) : (
              <p className="memory-empty">{query ? "Tidak ada hasil." : "Belum ada memori."}</p>
            )}
            {(memories.length > 0 || data.policy.history_after) && (
              <Button
                variant="ghost"
                className="memory-clear text-destructive"
                disabled={busy}
                onClick={() => {
                  if (
                    !confirm(
                      "Hapus semua memori dan mulai ulang konteks otomatis? Percakapan dan profil tetap ada.",
                    )
                  )
                    return;
                  void apply(() => clear({ data: { userId } }), "Semua memori telah dihapus.");
                }}
              >
                Hapus semua memori
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
