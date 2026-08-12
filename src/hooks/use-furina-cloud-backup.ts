import { useCallback, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { backupSupabase } from "@/integrations/supabase/backup-client";
import { base64ToBlob, blobToBase64, cloudBridge, NativeCloudTransfer } from "@/lib/cloud-backup-transfer";
import { toast } from "sonner";

const BUCKET = "furina-backups";
const FILE_NAME = "latest.furina";
const SNAPSHOT_PREFIX = "Furina-cloud-";
const SNAPSHOT_RETENTION = 5;
const AUTO_ENABLED_KEY = "furina:cloud:auto-enabled";
const LAST_AUTO_KEY = "furina:cloud:last-auto";
const AUTO_INTERVAL_MS = 6 * 60 * 60 * 1000;

function isSnapshotName(name: string) {
  return name.startsWith(SNAPSHOT_PREFIX) && name.endsWith(".furina");
}

export function formatCloudBytes(bytes = 0) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index >= 2 ? 1 : 0)} ${units[index]}`;
}

export function useFurinaCloudBackup() {
  const [session, setSession] = useState<Session | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [busy, setBusy] = useState<"backup" | "restore" | "login" | "logout" | null>(null);
  const [lastBackupAt, setLastBackupAt] = useState<string | null>(null);
  const [lastBackupSize, setLastBackupSize] = useState(0);
  const [autoBackup, setAutoBackup] = useState(() => typeof window === "undefined" || localStorage.getItem(AUTO_ENABLED_KEY) !== "0");
  const transfer = useRef<NativeCloudTransfer | null>(null);
  if (!transfer.current && typeof window !== "undefined") transfer.current = new NativeCloudTransfer();

  const refresh = useCallback(async (active: Session | null) => {
    if (!active) { setLastBackupAt(null); setLastBackupSize(0); return; }
    const { data, error } = await backupSupabase.storage.from(BUCKET).list(active.user.id, {
      limit: 16,
      sortBy: { column: "updated_at", order: "desc" },
    });
    if (error) return;
    const file = data?.find((item) => item.name === FILE_NAME) || data?.find((item) => isSnapshotName(item.name));
    if (!file) { setLastBackupAt(null); setLastBackupSize(0); return; }
    const meta = file as unknown as { updated_at?: string; created_at?: string; metadata?: { size?: number } };
    setLastBackupAt(meta.updated_at || meta.created_at || null);
    setLastBackupSize(Number(meta.metadata?.size || 0));
  }, []);

  const pruneSnapshots = useCallback(async (userId: string) => {
    const { data, error } = await backupSupabase.storage.from(BUCKET).list(userId, {
      limit: 32,
      sortBy: { column: "created_at", order: "desc" },
    });
    if (error || !data) return;
    const stale = data.filter((item) => isSnapshotName(item.name)).slice(SNAPSHOT_RETENTION);
    if (stale.length) {
      await backupSupabase.storage.from(BUCKET).remove(stale.map((item) => `${userId}/${item.name}`));
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    void backupSupabase.auth.getSession().then(({ data }) => {
      if (!mounted) return; setSession(data.session); setLoadingAuth(false); void refresh(data.session);
    });
    const { data: listener } = backupSupabase.auth.onAuthStateChange((_event, next) => {
      setSession(next); setLoadingAuth(false); void refresh(next);
    });
    return () => { mounted = false; listener.subscription.unsubscribe(); };
  }, [refresh]);

  useEffect(() => {
    const t = transfer.current; if (!t) return;
    t.install((rawUrl) => {
      void (async () => {
        const url = new URL(rawUrl);
        const oauthError = url.searchParams.get("error");
        if (oauthError) { setBusy(null); toast.error(url.searchParams.get("error_description") || oauthError); return; }
        const code = url.searchParams.get("code"); if (!code) return;
        const { error } = await backupSupabase.auth.exchangeCodeForSession(code);
        setBusy(null); error ? toast.error(error.message) : toast.success("Google terhubung. Backup cloud Furina aktif.");
      })();
    });
    return () => t.uninstall();
  }, []);

  const upload = useCallback(async (quiet = false) => {
    if (!session) throw new Error("Masuk dengan Google terlebih dahulu.");
    const payload = await transfer.current!.prepareBackup();
    const blob = base64ToBlob(payload.base64);
    const storage = backupSupabase.storage.from(BUCKET);
    const snapshotName = isSnapshotName(payload.fileName)
      ? payload.fileName
      : `${SNAPSHOT_PREFIX}${Date.now()}.furina`;

    const versioned = await storage.upload(`${session.user.id}/${snapshotName}`, blob, {
      upsert: false, contentType: "application/octet-stream", cacheControl: "0",
    });
    if (versioned.error && !versioned.error.message.toLowerCase().includes("already exists")) throw versioned.error;

    const latest = await storage.upload(`${session.user.id}/${FILE_NAME}`, blob, {
      upsert: true, contentType: "application/octet-stream", cacheControl: "0",
    });
    if (latest.error) throw latest.error;

    await pruneSnapshots(session.user.id);
    localStorage.setItem(LAST_AUTO_KEY, String(Date.now()));
    await refresh(session);
    if (!quiet) toast.success(`Backup cloud selesai (${formatCloudBytes(blob.size)}). 5 versi terakhir dipertahankan.`);
  }, [pruneSnapshots, refresh, session]);

  useEffect(() => {
    if (!session || !autoBackup || !cloudBridge()) return;
    const maybe = async () => {
      if (Date.now() - Number(localStorage.getItem(LAST_AUTO_KEY) || 0) < AUTO_INTERVAL_MS || busy) return;
      try { await upload(true); } catch { /* opportunistic */ }
    };
    const first = window.setTimeout(() => void maybe(), 8_000);
    const interval = window.setInterval(() => void maybe(), 30 * 60 * 1000);
    return () => { clearTimeout(first); clearInterval(interval); };
  }, [autoBackup, busy, session, upload]);

  const login = useCallback(async () => {
    setBusy("login");
    try {
      const native = /(?:^|\s)FurinaAndroid\//.test(navigator.userAgent) && Boolean(cloudBridge());
      const callback = new URL("/backup-auth", window.location.origin); if (native) callback.searchParams.set("native", "1");
      const { data, error } = await backupSupabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: callback.toString(), skipBrowserRedirect: native } });
      if (error) throw error;
      if (native) { if (!data.url) throw new Error("Google OAuth URL tidak tersedia."); cloudBridge()!.openExternal(data.url); return; }
      if (data.url) window.location.assign(data.url);
    } catch (error) { setBusy(null); toast.error(error instanceof Error ? error.message : "Login Google gagal"); }
  }, []);

  const logout = useCallback(async () => {
    setBusy("logout"); const { error } = await backupSupabase.auth.signOut(); setBusy(null);
    error ? toast.error(error.message) : toast.success("Akun Google dilepas dari Furina");
  }, []);

  const backup = useCallback(async () => {
    setBusy("backup"); try { await upload(false); } catch (error) { toast.error(error instanceof Error ? error.message : "Backup cloud gagal"); } finally { setBusy(null); }
  }, [upload]);

  const restore = useCallback(async () => {
    if (!session || !confirm("Pulihkan backup cloud terbaru? Data lokal Furina saat ini akan diganti. Recovery key pada perangkat ini harus cocok.")) return;
    setBusy("restore");
    try {
      const storage = backupSupabase.storage.from(BUCKET);
      let download = await storage.download(`${session.user.id}/${FILE_NAME}`);
      if (download.error) {
        const { data: files } = await storage.list(session.user.id, {
          limit: SNAPSHOT_RETENTION,
          sortBy: { column: "created_at", order: "desc" },
        });
        const fallback = files?.find((item) => isSnapshotName(item.name));
        if (!fallback) throw download.error;
        download = await storage.download(`${session.user.id}/${fallback.name}`);
      }
      if (download.error || !download.data) throw download.error || new Error("Backup cloud tidak ditemukan");
      await transfer.current!.restore(await blobToBase64(download.data));
      toast.success("Backup cloud dipulihkan. Memori dan percakapan sudah kembali.");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Restore cloud gagal"); } finally { setBusy(null); }
  }, [session]);

  const setAuto = (enabled: boolean) => { setAutoBackup(enabled); localStorage.setItem(AUTO_ENABLED_KEY, enabled ? "1" : "0"); };
  return { session, loadingAuth, busy, lastBackupAt, lastBackupSize, autoBackup, setAuto, login, logout, backup, restore };
}
