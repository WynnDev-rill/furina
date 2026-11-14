import { useEffect, useState } from "react";
import { Check, Ellipsis, Pencil, Plus, Search, Star, StarOff, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

type Entry = {
  id: string;
  title: string;
  updatedAt: number;
  messages: { content: string }[];
};
const day = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric" });
const time = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit" });

export function ConversationHistory({
  entries,
  activeId,
  userId,
  pending,
  unavailable,
  onOpen,
  onNew,
  onRename,
  onDelete,
}: {
  entries: Entry[];
  activeId: string;
  userId: string;
  pending: boolean;
  unavailable: boolean;
  onOpen: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => Promise<boolean>;
}) {
  const key = `furina:history-pins:${userId}`;
  const [pinned, setPinned] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Entry | null>(null);

  useEffect(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
      if (Array.isArray(stored))
        setPinned(stored.filter((id): id is string => typeof id === "string"));
    } catch {
      /* Pins are optional when local storage is unavailable. */
    }
  }, [key]);

  function savePins(next: string[]) {
    setPinned(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* Keep this session's pins. */
    }
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const groups: { label: string; rows: { entry: Entry; match?: string }[] }[] = [
    { label: "Disematkan", rows: [] },
    { label: "Hari ini", rows: [] },
    { label: "Kemarin", rows: [] },
    { label: "Lebih lama", rows: [] },
  ];
  const term = query.trim().toLocaleLowerCase("id-ID");
  let count = 0;
  for (const entry of [...entries].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const isPinned = pinned.includes(entry.id);
    if (!entry.messages.length && entry.title === "Percakapan baru" && !isPinned) continue;
    let match: string | undefined;
    if (term && !entry.title.toLocaleLowerCase("id-ID").includes(term)) {
      match = entry.messages
        .slice()
        .reverse()
        .find((m) => m.content.toLocaleLowerCase("id-ID").includes(term))?.content;
      if (!match) continue;
      const index = match.toLocaleLowerCase("id-ID").indexOf(term);
      match = (index > 24 ? "…" : "") + match.slice(Math.max(0, index - 24), index + 74);
    }
    const group = isPinned
      ? 0
      : entry.updatedAt >= +today
        ? 1
        : entry.updatedAt >= +yesterday
          ? 2
          : 3;
    groups[group].rows.push({ entry, match });
    count++;
  }

  return (
    <>
      <SheetHeader className="history-heading space-y-0 text-left">
        <SheetTitle>Riwayat Percakapan</SheetTitle>
        <SheetDescription className="sr-only">Cari dan kelola percakapan Furina.</SheetDescription>
        <span className="history-count" aria-label={`${count} percakapan`}>
          {count}
        </span>
      </SheetHeader>
      <div className="history-tools">
        <div className="history-search">
          <Search size={17} aria-hidden="true" />
          <Input
            type="search"
            aria-label="Cari percakapan"
            placeholder="Cari percakapan…"
            value={query}
            onChange={(event) => {
              setEditing(null);
              setQuery(event.target.value);
            }}
          />
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="glass-surface history-action"
          aria-label="Percakapan baru"
          title="Percakapan baru"
          onClick={onNew}
          disabled={pending}
        >
          <Plus size={19} />
        </Button>
      </div>
      <div className="history-list">
        {unavailable ? (
          <p role="status">Riwayat akun belum berhasil dimuat.</p>
        ) : pending ? (
          <p role="status">Memuat riwayat…</p>
        ) : !count ? (
          <p role="status">{term ? "Tidak ada hasil pencarian." : "Belum ada percakapan."}</p>
        ) : (
          groups
            .filter(({ rows }) => rows.length)
            .map(({ label, rows }) => (
              <section key={label} aria-label={label}>
                <h3>{label}</h3>
                <ul>
                  {rows.map(({ entry, match }) => (
                    <li key={entry.id} className="history-row" data-active={entry.id === activeId}>
                      {editing?.id === entry.id ? (
                        <form
                          className="history-rename"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (!editing.title.trim()) return;
                            onRename(entry.id, editing.title);
                            setEditing(null);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Escape") {
                              event.stopPropagation();
                              setEditing(null);
                            }
                          }}
                        >
                          <Input
                            autoFocus
                            aria-label="Judul percakapan"
                            maxLength={120}
                            value={editing.title}
                            onChange={(event) =>
                              setEditing({ ...editing, title: event.target.value })
                            }
                          />
                          <Button
                            type="submit"
                            size="icon"
                            variant="ghost"
                            aria-label="Simpan judul"
                            disabled={!editing.title.trim()}
                          >
                            <Check />
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            aria-label="Batal ubah nama"
                            onClick={() => setEditing(null)}
                          >
                            <X />
                          </Button>
                        </form>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="history-open"
                            aria-current={entry.id === activeId ? "true" : undefined}
                            onClick={() => onOpen(entry.id)}
                          >
                            {label === "Disematkan" && (
                              <Star size={15} className="history-star" aria-hidden="true" />
                            )}
                            <span>
                              <strong>{entry.title}</strong>
                              <small>
                                {match ??
                                  (label === "Hari ini" || label === "Kemarin" ? time : day).format(
                                    entry.updatedAt,
                                  )}
                              </small>
                            </span>
                          </button>
                          <DropdownMenu modal={false}>
                            <DropdownMenuTrigger asChild>
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                aria-label={`Opsi ${entry.title}`}
                              >
                                <Ellipsis />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent
                              align="end"
                              className="glass-surface history-menu"
                              onCloseAutoFocus={(event) => {
                                if (document.querySelector(".history-rename"))
                                  event.preventDefault();
                              }}
                            >
                              <DropdownMenuItem
                                onSelect={() =>
                                  savePins(
                                    pinned.includes(entry.id)
                                      ? pinned.filter((id) => id !== entry.id)
                                      : [...pinned, entry.id],
                                  )
                                }
                              >
                                {pinned.includes(entry.id) ? (
                                  <>
                                    <StarOff /> Lepas sematan
                                  </>
                                ) : (
                                  <>
                                    <Star /> Sematkan
                                  </>
                                )}
                              </DropdownMenuItem>
                              <DropdownMenuItem onSelect={() => setEditing(entry)}>
                                <Pencil /> Ubah nama
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="history-delete"
                                onSelect={() => {
                                  void onDelete(entry.id).then((deleted) => {
                                    if (deleted && pinned.includes(entry.id))
                                      savePins(pinned.filter((id) => id !== entry.id));
                                  });
                                }}
                              >
                                <Trash2 /> Hapus
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ))
        )}
      </div>
    </>
  );
}
