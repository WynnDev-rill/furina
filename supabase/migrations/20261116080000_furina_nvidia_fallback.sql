alter table public.furina_ai_preferences
  add column if not exists use_nvidia boolean not null default false;

create table if not exists public.furina_nvidia_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_value text not null,
  fingerprint text not null,
  suffix text not null check (length(suffix) = 4),
  invalid boolean not null default false,
  created_at timestamptz not null default now(),
  unique(user_id, fingerprint)
);
alter table public.furina_nvidia_keys enable row level security;
revoke all on public.furina_nvidia_keys from public, anon, authenticated;
grant select, insert, update, delete on public.furina_nvidia_keys to service_role;

alter table public.memories
  alter column embedding drop not null,
  add column if not exists nvidia_embedding extensions.vector(2048);

-- Keep only embeddings generated from the current content of each memory.
create or replace function public.invalidate_stale_furina_embeddings()
returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.content is distinct from old.content then
    if new.embedding::text is not distinct from old.embedding::text then new.embedding = null; end if;
    if new.nvidia_embedding::text is not distinct from old.nvidia_embedding::text then new.nvidia_embedding = null; end if;
  end if;
  return new;
end;
$$;
revoke all on function public.invalidate_stale_furina_embeddings() from public, anon, authenticated;
drop trigger if exists furina_memory_embedding_content_changed on public.memories;
create trigger furina_memory_embedding_content_changed
  before update of content on public.memories for each row
  execute function public.invalidate_stale_furina_embeddings();

create or replace function public.correct_furina_nvidia_memory(
  owner_id uuid, memory_id uuid, new_content text, new_embedding extensions.vector
)
returns boolean language plpgsql set search_path = ''
as $$
begin
  if not public.correct_furina_memory(owner_id, memory_id, new_content, null) then return false; end if;
  update public.memories set nvidia_embedding = new_embedding
    where id = memory_id and user_id = owner_id and character_id = 'furina';
  return found;
end;
$$;
revoke all on function public.correct_furina_nvidia_memory(uuid,uuid,text,extensions.vector) from public, anon, authenticated;
grant execute on function public.correct_furina_nvidia_memory(uuid,uuid,text,extensions.vector) to service_role;

create or replace function public.find_furina_nvidia_memories(
  owner_id uuid, query_vec extensions.vector, use_saved boolean, use_history boolean,
  since_time timestamptz, row_count integer
)
returns table (id uuid, content text, kind text, saved boolean, similarity double precision, occurred_at timestamptz)
language sql stable set search_path = public, extensions, pg_temp
as $$
  select m.id, m.content, m.kind, m.saved, 1 - (m.nvidia_embedding <=> query_vec), m.occurred_at
  from public.memories m
  where m.user_id = owner_id and m.character_id = 'furina'
    and ((m.saved and use_saved) or
      (not m.saved and use_history and not m.compressed and
        (since_time is null or m.created_at > since_time)))
    and m.kind <> 'self'
    and m.merged_into is null
    and 1 - (m.nvidia_embedding <=> query_vec) >= 0.28
  order by (1 - (m.nvidia_embedding <=> query_vec)) * 0.8
    + (m.importance::float / 10) * 0.15 + case when m.saved then 0.05 else 0 end desc
  limit least(40, greatest(1, row_count));
$$;
revoke all on function public.find_furina_nvidia_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  from public, anon, authenticated;
grant execute on function public.find_furina_nvidia_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  to service_role;
