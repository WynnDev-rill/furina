import { supabaseAdmin } from "@/integrations/supabase/client.server";

export async function recallRecentThreads(
  userId: string,
  terms: readonly string[],
  exclude?: string,
) {
  const { data, error } = await supabaseAdmin.rpc("recall_furina_recent", {
    owner_id: userId,
    search_terms: [...terms],
    excluded_thread: exclude ?? null,
  });
  if (error) throw error;
  return (data ?? []).map(({ title, turns, last_at }) => ({ title, turns, last_at }));
}
