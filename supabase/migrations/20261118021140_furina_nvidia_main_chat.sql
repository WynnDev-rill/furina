alter table public.furina_ai_preferences
  add column if not exists chat_provider text not null default 'gemini'
    check (chat_provider in ('gemini', 'nvidia')),
  add column if not exists use_nvidia_chat boolean not null default false;

create table public.furina_nvidia_chat_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_value text not null,
  fingerprint text not null,
  suffix text not null check (length(suffix) = 4),
  enabled boolean not null default true,
  invalid boolean not null default false,
  created_at timestamptz not null default now(),
  unique(user_id, fingerprint)
);
create table public.furina_nvidia_chat_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  active_model text,
  active_key_id uuid references public.furina_nvidia_chat_keys(id) on delete set null,
  cooldowns jsonb not null default '{}'::jsonb,
  last_notice text,
  updated_at timestamptz not null default now()
);
alter table public.furina_nvidia_chat_keys enable row level security;
alter table public.furina_nvidia_chat_state enable row level security;
revoke all on public.furina_nvidia_chat_keys, public.furina_nvidia_chat_state
  from public, anon, authenticated;
grant select, insert, update, delete on public.furina_nvidia_chat_keys, public.furina_nvidia_chat_state
  to service_role;

create or replace function public.save_furina_nvidia_chat_state(
  owner_id uuid, model_id text, key_id uuid, blocked_until jsonb, notice text
) returns void language plpgsql set search_path = ''
as $$
begin
  if key_id is not null and not exists (
    select 1 from public.furina_nvidia_chat_keys
    where id = key_id and user_id = owner_id and enabled and not invalid
  ) then key_id := null; end if;
  insert into public.furina_nvidia_chat_state as current_state
    (user_id, active_model, active_key_id, cooldowns, last_notice)
  values (owner_id, model_id, key_id, blocked_until, notice)
  on conflict (user_id) do update set
    active_model = coalesce(excluded.active_model, current_state.active_model),
    active_key_id = case when excluded.active_model is not null then excluded.active_key_id
      else current_state.active_key_id end,
    cooldowns = (
      select coalesce(jsonb_object_agg(item.key, item.until), '{}'::jsonb)
      from (
        select entries.key, max(entries.value::text::double precision) as until
        from (
          select * from jsonb_each(current_state.cooldowns)
          union all select * from jsonb_each(excluded.cooldowns)
        ) entries
        where jsonb_typeof(entries.value) = 'number'
        group by entries.key
        having max(entries.value::text::double precision) > extract(epoch from now()) * 1000
        order by max(entries.value::text::double precision) desc limit 256
      ) item
    ),
    last_notice = excluded.last_notice,
    updated_at = now();
end;
$$;
revoke all on function public.save_furina_nvidia_chat_state(uuid,text,uuid,jsonb,text)
  from public, anon, authenticated;
grant execute on function public.save_furina_nvidia_chat_state(uuid,text,uuid,jsonb,text)
  to service_role;

alter table public.furina_chat_usage drop constraint furina_chat_usage_provider_check;
alter table public.furina_chat_usage add constraint furina_chat_usage_provider_check
  check (provider in ('lovable', 'gemini', 'nvidia'));
