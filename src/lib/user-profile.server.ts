import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { ageInstructions, birthdayContext, localCalendar } from "./birth-date";

export async function loadBirthProfile(userId: string) {
  const { data, error } = await supabaseAdmin
    .from("furina_user_profile")
    .select("birth_date,greeted_year")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export async function saveBirthProfile(userId: string, birthDate: string | null) {
  const { error } = await supabaseAdmin
    .from("furina_user_profile")
    .upsert({ user_id: userId, birth_date: birthDate });
  if (error) throw error;
}

export async function claimBirthday(userId: string, birthDate: string, year: number) {
  const { data, error } = await supabaseAdmin
    .from("furina_user_profile")
    .update({ greeted_year: year })
    .eq("user_id", userId)
    .eq("birth_date", birthDate)
    .or(`greeted_year.is.null,greeted_year.lt.${year}`)
    .select("user_id")
    .maybeSingle();
  return !error && !!data;
}

export async function profileContext(userId: string, timezone?: string) {
  const profile = await loadBirthProfile(userId).catch(() => null);
  const birthday = profile?.birth_date
    ? birthdayContext(profile.birth_date, localCalendar(new Date(), timezone))
    : null;
  const age = birthday?.age;
  const group =
    age === undefined ? "belum diketahui" : age < 13 ? "anak" : age < 18 ? "remaja" : "dewasa";
  return {
    profile,
    birthday,
    prompt:
      "\n\nAKSES DAN KONTEKS USIA: " + ageInstructions(age) + " Kelompok usia: " + group + ".",
  };
}
