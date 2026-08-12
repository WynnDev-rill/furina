import { createClient } from "@supabase/supabase-js";

// These are public client credentials, not secrets. Keeping a checked-in fallback makes
// Google Backup resilient when a Vercel environment variable is missing or a deployment
// is recreated. Production env values can still override them normally.
const DEFAULT_BACKUP_URL = "https://fxebamfwewsvtscrbwxk.supabase.co";
const DEFAULT_BACKUP_PUBLISHABLE_KEY = "sb_publishable_c81UMY86mgZXNuvM5hB4Ng_RroHC9Kc";

const backupUrl = import.meta.env.VITE_FURINA_BACKUP_SUPABASE_URL || DEFAULT_BACKUP_URL;
const backupKey = import.meta.env.VITE_FURINA_BACKUP_SUPABASE_PUBLISHABLE_KEY || DEFAULT_BACKUP_PUBLISHABLE_KEY;

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
