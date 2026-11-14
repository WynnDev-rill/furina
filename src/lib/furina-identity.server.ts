import { getRequest } from "@tanstack/react-start/server";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { z } from "zod";

const uuid = z.string().uuid();

export async function requireGuestId(value: string) {
  const guestId = uuid.parse(value);
  // Legacy guests use a random, browser-local UUID. Never accept an account UUID
  // as a guest credential, even when a caller omits their Authorization header.
  const { data, error } = await supabaseAdmin.auth.admin.getUserById(guestId);
  if (data?.user || error?.status !== 404) throw new Error("Identitas tamu tidak valid.");
  return guestId;
}

export async function requireFurinaIdentity(value: string, accountRequired = false) {
  const header = getRequest().headers.get("authorization");
  if (!header && !accountRequired) return requireGuestId(value);
  const token = header?.match(/^Bearer (\S+)$/i)?.[1];
  if (!token) throw new Error("Login diperlukan.");
  const { data, error } = await supabaseAdmin.auth.getUser(token);
  if (error || data.user?.id !== value) throw new Error("Sesi akun tidak valid.");
  return data.user.id;
}
