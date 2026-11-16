create or replace function public.save_furina_gemini_key(
  owner_id uuid, secret_box text, key_fingerprint text, key_suffix text
) returns text language plpgsql set search_path = ''
as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 7402));
  if exists(select 1 from public.furina_gemini_keys where user_id = owner_id and fingerprint = key_fingerprint) then
    update public.furina_gemini_keys set invalid = false, encrypted_value = secret_box
    where user_id = owner_id and fingerprint = key_fingerprint;
  else
    insert into public.furina_gemini_keys(user_id,encrypted_value,fingerprint,suffix)
      values(owner_id,secret_box,key_fingerprint,key_suffix);
  end if;
  return 'saved';
end;
$$;
