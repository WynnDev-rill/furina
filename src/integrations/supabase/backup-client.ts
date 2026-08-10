import { createClient } from "@supabase/supabase-js";

const backupUrl = import.meta.env.VITE_FURINA_BACKUP_SUPABASE_URL;
const backupKey = import.meta.env.VITE_FURINA_BACKUP_SUPABASE_PUBLISHABLE_KEY;

if (!backupUrl || !backupKey) {
  throw new Error("Furina cloud backup is not configured.");
}

export const backupSupabase = createClient(backupUrl, backupKey, {
  auth: {
    persistSession: typeof window !== "undefined",
    autoRefreshToken: typeof window !== "undefined",
    detectSessionInUrl: false,
    flowType: "pkce",
    storageKey: "furina:cloud-auth",
    storage: typeof window !== "undefined" ? window.localStorage : undefined,
  },
});
