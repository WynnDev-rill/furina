import { useEffect, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { birthdayContext, localCalendar } from "@/lib/birth-date";
import { getBirthDate, setBirthDate } from "@/lib/furina.functions";

export function BirthDateSettings({ userId }: { userId: string }) {
  const read = useServerFn(getBirthDate);
  const write = useServerFn(setBirthDate);
  const [saved, setSaved] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [today, setToday] = useState(() => localCalendar(new Date()));
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const update = () =>
      setToday(localCalendar(new Date(), Intl.DateTimeFormat().resolvedOptions().timeZone));
    update();
    const timer = setInterval(update, 30_000);
    document.addEventListener("visibilitychange", update);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  useEffect(() => {
    if (!userId) return;
    let active = true;
    setPending(true);
    read({ data: { userId } })
      .then(({ birthDate }) => {
        if (active) {
          setSaved(birthDate);
          setDraft(birthDate ?? "");
          setLoaded(true);
          setError("");
        }
      })
      .catch(() => {
        if (active) setError("Tanggal lahir belum dapat dimuat.");
      })
      .finally(() => {
        if (active) setPending(false);
      });
    return () => {
      active = false;
    };
  }, [userId, read, refresh]);
  async function save(birthDate: string | null) {
    setPending(true);
    setError("");
    try {
      const saved = await write({
        data: { userId, birthDate, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
      });
      setSaved(saved.birthDate);
      setDraft(saved.birthDate ?? "");
    } catch {
      setError("Tanggal lahir belum tersimpan. Periksa tanggal dan coba lagi.");
    } finally {
      setPending(false);
    }
  }
  const age = saved ? birthdayContext(saved, today)?.age : undefined;
  return (
    <section className="settings-group space-y-2">
      <Label htmlFor="furina-birth-date">Tanggal lahir</Label>
      <Input
        id="furina-birth-date"
        type="date"
        min="1900-01-01"
        max={today.toISOString().slice(0, 10)}
        value={draft}
        disabled={pending || !loaded}
        onChange={(event) => setDraft(event.target.value)}
      />
      {age !== undefined && <p className="text-sm">{age} tahun</p>}
      <p className="text-xs text-muted-foreground">
        Opsional. Untuk respons sesuai usia dan ucapan ulang tahun.
      </p>
      {error && (
        <p role="alert" className="text-sm">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {loaded ? (
          <>
            <Button
              size="sm"
              onClick={() => void save(draft)}
              disabled={pending || !draft || draft === saved}
            >
              Simpan tanggal
            </Button>
            {saved && (
              <Button
                size="sm"
                variant="outline"
                disabled={pending}
                onClick={() => void save(null)}
              >
                Hapus tanggal
              </Button>
            )}
          </>
        ) : (
          error && (
            <Button size="sm" onClick={() => setRefresh((v) => v + 1)}>
              Coba lagi
            </Button>
          )
        )}
      </div>
    </section>
  );
}
