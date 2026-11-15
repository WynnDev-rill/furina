import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { defaultMemoryPolicy } from "./memory-policy";

export async function readMemoryPolicy(userId: string) {
  const { data, error } = await supabaseAdmin
    .from("furina_memory_settings")
    .select("use_saved,use_history,history_after")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw error;
  return data ?? defaultMemoryPolicy;
}

export const unavailableMemoryPolicy = {
  use_saved: false,
  use_history: false,
  history_after: null,
};
