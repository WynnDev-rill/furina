create table if not exists public.furina_ai_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  use_gemini boolean not null default false
);
create table if not exists public.furina_gemini_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_value text not null,
  fingerprint text not null,
  suffix text not null check (length(suffix) = 4),
  invalid boolean not null default false,
  created_at timestamptz not null default now(),
  unique(user_id, fingerprint)
);
create table if not exists public.furina_chat_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  day date not null,
  provider text not null check (provider in ('lovable','gemini')),
  requests bigint not null default 0,
  tokens bigint not null default 0,
  primary key (user_id, day, provider)
);

alter table public.furina_ai_preferences enable row level security;
alter table public.furina_gemini_keys enable row level security;
alter table public.furina_chat_usage enable row level security;
revoke all on public.furina_ai_preferences, public.furina_gemini_keys, public.furina_chat_usage
  from public, anon, authenticated;
grant select, insert, update, delete on public.furina_ai_preferences, public.furina_gemini_keys, public.furina_chat_usage
  to service_role;

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
    if (select count(*) from public.furina_gemini_keys where user_id = owner_id) >= 5 then return 'full'; end if;
    insert into public.furina_gemini_keys(user_id,encrypted_value,fingerprint,suffix)
      values(owner_id,secret_box,key_fingerprint,key_suffix);
  end if;
  insert into public.furina_ai_preferences(user_id,use_gemini) values(owner_id,true)
  on conflict(user_id) do update set use_gemini = true;
  return 'saved';
end;
$$;

create or replace function public.record_furina_chat_usage(
  owner_id uuid, usage_provider text, total_tokens integer
) returns void language sql set search_path = ''
as $$
  insert into public.furina_chat_usage as t(user_id, day, provider, requests, tokens)
  values(owner_id, (pg_catalog.now() at time zone 'Asia/Jakarta')::date, usage_provider, 1, greatest(0, total_tokens))
  on conflict (user_id, day, provider)
    do update set requests = t.requests + 1, tokens = t.tokens + excluded.tokens;
$$;

revoke all on function public.save_furina_gemini_key(uuid,text,text,text),
  public.record_furina_chat_usage(uuid,text,integer) from public, anon, authenticated;
grant execute on function public.save_furina_gemini_key(uuid,text,text,text),
  public.record_furina_chat_usage(uuid,text,integer) to service_role;
