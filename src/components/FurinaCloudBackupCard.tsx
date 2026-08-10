import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Cloud, Download, Loader2, LogIn, LogOut, ShieldCheck, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { formatCloudBytes, useFurinaCloudBackup } from "@/hooks/use-furina-cloud-backup";

function useSettingsPortalTarget() {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (window.location.pathname !== "/native") return;
    const find = () => {
      const dialog = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).find((el) => el.textContent?.includes("Pengaturan"));
      const scroll = dialog?.querySelector<HTMLElement>("div.min-h-0.flex-1.overflow-y-auto");
      const stack = scroll?.firstElementChild as HTMLElement | null;
      if (!stack) { setTarget(null); return; }
      let mount = stack.querySelector<HTMLElement>("#furina-cloud-backup-root");
      if (!mount) { mount = document.createElement("div"); mount.id = "furina-cloud-backup-root"; stack.prepend(mount); }
      setTarget(mount);
    };
    find(); const observer = new MutationObserver(find); observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);
  return target;
}

export function FurinaCloudBackupCard() {
  const target = useSettingsPortalTarget();
  const cloud = useFurinaCloudBackup();
  if (!target) return null;
  const userName = String(cloud.session?.user.user_metadata?.full_name || cloud.session?.user.user_metadata?.name || "Akun Google");
  const email = cloud.session?.user.email || "";
  const avatar = cloud.session?.user.user_metadata?.avatar_url as string | undefined;

  return createPortal(
    <section className="mb-6 space-y-4 rounded-2xl border bg-muted/10 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/12 text-sky-400"><Cloud className="h-[19px] w-[19px]" /></span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Backup akun</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">Google dipakai untuk identitas akun. Backup Furina tetap terenkripsi sebelum dikirim ke cloud.</p>
        </div>
      </div>

      {cloud.loadingAuth ? (
        <div className="flex min-h-12 items-center justify-center text-xs text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Memeriksa akun…</div>
      ) : !cloud.session ? (
        <>
          <div className="rounded-xl border bg-background/45 p-3 text-[11px] leading-relaxed text-muted-foreground">Masuk bersifat opsional. Furina tetap dapat dipakai sepenuhnya secara lokal tanpa akun.</div>
          <Button className="min-h-12 w-full rounded-xl" disabled={cloud.busy === "login"} onClick={() => void cloud.login()}>
            {cloud.busy === "login" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogIn className="mr-2 h-4 w-4" />} Masuk dengan Google
          </Button>
        </>
      ) : (
        <>
          <div className="flex items-center gap-3 rounded-xl border bg-background/45 p-3">
            {avatar ? <img src={avatar} alt="" className="h-10 w-10 rounded-full object-cover" referrerPolicy="no-referrer" /> : <div className="grid h-10 w-10 place-items-center rounded-full bg-sky-500/15 font-semibold text-sky-400">G</div>}
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{userName}</p><p className="truncate text-[11px] text-muted-foreground">{email}</p></div>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-1 text-[9px] font-semibold text-emerald-500"><ShieldCheck className="h-3 w-3" /> Tersambung</span>
          </div>
          <div className="flex min-h-11 items-center justify-between gap-4 rounded-xl border bg-background/35 px-3 py-2">
            <div><p className="text-xs font-medium">Backup otomatis</p><p className="text-[10px] text-muted-foreground">Maksimal sekali setiap 6 jam saat aplikasi aktif.</p></div>
            <Switch checked={cloud.autoBackup} onCheckedChange={cloud.setAuto} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button disabled={Boolean(cloud.busy)} onClick={() => void cloud.backup()}>{cloud.busy === "backup" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />} Backup</Button>
            <Button variant="outline" disabled={Boolean(cloud.busy) || !cloud.lastBackupAt} onClick={() => void cloud.restore()}>{cloud.busy === "restore" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />} Pulihkan</Button>
          </div>
          <div className="rounded-xl bg-muted/40 p-3 text-[10px] leading-relaxed text-muted-foreground">
            {cloud.lastBackupAt ? <>Backup cloud terakhir: <span className="font-medium text-foreground">{new Date(cloud.lastBackupAt).toLocaleString()}</span>{cloud.lastBackupSize ? ` · ${formatCloudBytes(cloud.lastBackupSize)}` : ""}</> : "Belum ada backup cloud."}
            <p className="mt-1">Recovery key tetap diperlukan di HP baru. API key online, file model AI, background custom, dan sampel suara tidak diunggah.</p>
          </div>
          <Button variant="ghost" className="min-h-11 w-full text-muted-foreground" disabled={cloud.busy === "logout"} onClick={() => void cloud.logout()}>{cloud.busy === "logout" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogOut className="mr-2 h-4 w-4" />} Keluar dari akun backup</Button>
        </>
      )}
    </section>,
    target,
  );
}
