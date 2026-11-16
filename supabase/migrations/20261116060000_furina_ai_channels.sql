alter table public.furina_ai_preferences
  add column if not exists lovable_chat boolean not null default true,
  add column if not exists lovable_background boolean not null default true,
  add column if not exists use_openrouter boolean not null default false,
  add column if not exists background_text_issue text,
  add column if not exists embedding_issue text;

create table if not exists public.furina_openrouter_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_value text not null,
  fingerprint text not null,
  suffix text not null check (length(suffix) = 4),
  invalid boolean not null default false,
  created_at timestamptz not null default now(),
  unique(user_id, fingerprint)
);
alter table public.furina_openrouter_keys enable row level security;
revoke all on public.furina_openrouter_keys from public, anon, authenticated;
grant select, insert, update, delete on public.furina_openrouter_keys to service_role;
