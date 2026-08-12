import { useCallback, useEffect, useMemo, useState } from "react";
import { backupSupabase } from "@/integrations/supabase/backup-client";
import {
  clearPendingCloudUpload,
  consumePendingCloudRestore,
  decodeBase64ToBytes,
  encodeBytesToBase64,
  getPendingCloudUpload,
} from "@/lib/cloud-backup-transfer";

const BUCKET = "furina-backups";
const LATEST_FILE = "latest.furina";
const SNAPSHOT_PREFIX = "Furina-cloud-";
const SNAPSHOT_RETENTION = 5;

export type FurinaCloudBackupState = {
  signedIn: boolean;
  email: string;
  latestUpdatedAt: string;
  busy: boolean;
  message: string;
};

function isSnapshotName(name: string) {
  return name.startsWith(SNAPSHOT_PREFIX) && name.endsWith(".furina");
}

export function useFurinaCloudBackup() {
  const [state, setState] = useState<FurinaCloudBackupState>({
    signedIn: false,
    email: "",
    latestUpdatedAt: "",
    busy: false,
    message: "",
  });

  const refresh = useCallback(async () => {
    const { data: authData } = await backupSupabase.auth.getUser();
    const user = authData.user;
    if (!user) {
      setState((prev) => ({ ...prev, signedIn: false, email: "", latestUpdatedAt: "" }));
      return;
    }
    const { data } = await backupSupabase.storage.from(BUCKET).list(user.id, {
      limit: 16,
      sortBy: { column: "updated_at", order: "desc" },
    });
    const latest = data?.find((item) => item.name === LATEST_FILE)
      || data?.find((item) => isSnapshotName(item.name));
    setState((prev) => ({
      ...prev,
      signedIn: true,
      email: user.email || "",
      latestUpdatedAt: latest?.updated_at || latest?.created_at || "",
    }));
  }, []);

  useEffect(() => {
    void refresh();
    const { data } = backupSupabase.auth.onAuthStateChange(() => void refresh());
    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const signIn = useCallback(async () => {
    setState((prev) => ({ ...prev, busy: true, message: "Membuka login Google…" }));
    const native = typeof navigator !== "undefined" && navigator.userAgent.includes("FurinaAndroid/");
    const callback = new URL("/backup-auth", window.location.origin);
    if (native) callback.searchParams.set("native", "1");
    const { error } = await backupSupabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: callback.toString(), skipBrowserRedirect: false },
    });
    if (error) setState((prev) => ({ ...prev, busy: false, message: error.message }));
  }, []);

  const signOut = useCallback(async () => {
    await backupSupabase.auth.signOut();
    setState((prev) => ({ ...prev, message: "Keluar dari Google Backup." }));
    await refresh();
  }, [refresh]);

  const pruneSnapshots = useCallback(async (userId: string) => {
    const { data, error } = await backupSupabase.storage.from(BUCKET).list(userId, {
      limit: 32,
      sortBy: { column: "created_at", order: "desc" },
    });
    if (error || !data) return;
    const snapshots = data.filter((item) => isSnapshotName(item.name));
    const stale = snapshots.slice(SNAPSHOT_RETENTION);
    if (stale.length) {
      await backupSupabase.storage.from(BUCKET).remove(stale.map((item) => `${userId}/${item.name}`));
    }
  }, []);

  const uploadPending = useCallback(async () => {
    const pending = getPendingCloudUpload();
    if (!pending) return;
    const { data: authData } = await backupSupabase.auth.getUser();
    const user = authData.user;
    if (!user) {
      setState((prev) => ({ ...prev, message: "Login Google diperlukan untuk cloud backup." }));
      return;
    }

    setState((prev) => ({ ...prev, busy: true, message: "Mengunggah backup terenkripsi…" }));
    try {
      const bytes = decodeBase64ToBytes(pending.base64);
      const blob = new Blob([bytes], { type: "application/octet-stream" });
      const safeName = isSnapshotName(pending.fileName)
        ? pending.fileName
        : `${SNAPSHOT_PREFIX}${Date.now()}.furina`;
      const storage = backupSupabase.storage.from(BUCKET);

      const versioned = await storage.upload(`${user.id}/${safeName}`, blob, {
        upsert: false,
        contentType: "application/octet-stream",
      });
      if (versioned.error && !versioned.error.message.toLowerCase().includes("already exists")) {
        throw versioned.error;
      }

      const latest = await storage.upload(`${user.id}/${LATEST_FILE}`, blob, {
        upsert: true,
        contentType: "application/octet-stream",
      });
      if (latest.error) throw latest.error;

      await pruneSnapshots(user.id);
      clearPendingCloudUpload();
      setState((prev) => ({ ...prev, busy: false, message: "Cloud backup selesai. 5 versi terakhir dipertahankan." }));
      await refresh();
    } catch (error) {
      setState((prev) => ({ ...prev, busy: false, message: error instanceof Error ? error.message : String(error) }));
    }
  }, [pruneSnapshots, refresh]);

  const restoreLatest = useCallback(async () => {
    const { data: authData } = await backupSupabase.auth.getUser();
    const user = authData.user;
    if (!user) {
      setState((prev) => ({ ...prev, message: "Login Google diperlukan untuk restore cloud." }));
      return;
    }
    setState((prev) => ({ ...prev, busy: true, message: "Mengunduh backup terenkripsi…" }));
    try {
      const storage = backupSupabase.storage.from(BUCKET);
      let download = await storage.download(`${user.id}/${LATEST_FILE}`);
      if (download.error) {
        const { data: files } = await storage.list(user.id, {
          limit: SNAPSHOT_RETENTION,
          sortBy: { column: "created_at", order: "desc" },
        });
        const fallback = files?.find((item) => isSnapshotName(item.name));
        if (!fallback) throw download.error;
        download = await storage.download(`${user.id}/${fallback.name}`);
      }
      if (download.error || !download.data) throw download.error || new Error("Backup cloud tidak ditemukan");
      const buffer = new Uint8Array(await download.data.arrayBuffer());
      const base64 = encodeBytesToBase64(buffer);
      window.localStorage.setItem("furina:cloud:restore", JSON.stringify({ base64, updatedAt: Date.now() }));
      consumePendingCloudRestore();
      setState((prev) => ({ ...prev, busy: false, message: "Backup cloud siap direstore di Android." }));
    } catch (error) {
      setState((prev) => ({ ...prev, busy: false, message: error instanceof Error ? error.message : String(error) }));
    }
  }, []);

  const available = useMemo(() => typeof window !== "undefined", []);

  return { state, available, signIn, signOut, refresh, uploadPending, restoreLatest };
}
