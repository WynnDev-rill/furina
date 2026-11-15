alter table public.memories add column if not exists saved boolean not null default false;
-- Legacy guest UUIDs have no auth.users row. Keep account cleanup on the trigger below.
alter table public.memories drop constraint if exists memories_user_id_fkey;

create table if not exists public.furina_memory_settings (
  user_id uuid primary key,
  use_saved boolean not null default true,
  use_history boolean not null default true,
  history_after timestamptz
);
alter table public.furina_memory_settings enable row level security;
revoke all on public.furina_memory_settings from public, anon, authenticated;
grant select, insert, update, delete on public.furina_memory_settings to service_role;

create or replace function public.delete_furina_memory_settings_for_account()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  delete from public.furina_memory_settings where user_id = old.id;
  delete from public.memories where user_id = old.id;
  return old;
end;
$$;
revoke all on function public.delete_furina_memory_settings_for_account() from public, anon, authenticated;
drop trigger if exists furina_memory_settings_account_deleted on auth.users;
create trigger furina_memory_settings_account_deleted
after delete on auth.users for each row
execute function public.delete_furina_memory_settings_for_account();

-- The older learned context has no complete provenance. Advancing the cutoff
-- prevents all of those derivations from being used again, including aggregates.
create or replace function public.forget_furina_memory(owner_id uuid, memory_id uuid)
returns boolean language plpgsql set search_path = ''
as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 91241));
  delete from public.memories m
    where m.user_id = owner_id and m.character_id = 'furina'
      and (memory_id is null or m.id = memory_id);
  if memory_id is not null and not found then return false; end if;
  insert into public.furina_memory_settings(user_id, history_after)
    values(owner_id, pg_catalog.clock_timestamp())
    on conflict (user_id) do update set history_after = excluded.history_after;
  return true;
end;
$$;
revoke all on function public.forget_furina_memory(uuid,uuid) from public, anon, authenticated;
grant execute on function public.forget_furina_memory(uuid,uuid) to service_role;

create or replace function public.find_furina_memories(
  owner_id uuid, query_vec extensions.vector, use_saved boolean, use_history boolean,
  since_time timestamptz, row_count integer
)
returns table (id uuid, content text, kind text, saved boolean, similarity double precision, occurred_at timestamptz)
language sql stable set search_path = public, extensions, pg_temp
as $$
  select m.id, m.content, m.kind, m.saved, 1 - (m.embedding <=> query_vec), m.occurred_at
  from public.memories m
  where m.user_id = owner_id and m.character_id = 'furina'
    and ((m.saved and use_saved) or
      (not m.saved and use_history and not m.compressed and
        (since_time is null or m.created_at > since_time)))
    and m.kind <> 'self'
    and 1 - (m.embedding <=> query_vec) >= 0.28
  order by (1 - (m.embedding <=> query_vec)) * 0.8
    + (m.importance::float / 10) * 0.15 + case when m.saved then 0.05 else 0 end desc
  limit least(40, greatest(1, row_count));
$$;
revoke all on function public.find_furina_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  from public, anon, authenticated;
grant execute on function public.find_furina_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  to service_role;

create or replace function public.commit_furina_compaction(
  owner_id uuid, source_ids uuid[], summary_text text, summary_embedding text
) returns boolean
language plpgsql set search_path = public, extensions, pg_temp
as $$
declare
  marked integer;
  boundary timestamptz;
begin
  if cardinality(source_ids) not between 5 and 30 then return false; end if;
  perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 91241));
  if exists (select 1 from public.furina_memory_settings s
      where s.user_id = owner_id and not s.use_history) then
    return false;
  end if;
  select s.history_after into boundary from public.furina_memory_settings s where s.user_id = owner_id;
  if (select count(*) from public.memories where id = any(source_ids)
      and user_id = owner_id and character_id = 'furina' and not compressed
      and not saved and kind <> 'self' and (boundary is null or created_at > boundary)) <> cardinality(source_ids) then return false; end if;
  update public.memories set compressed = true where id = any(source_ids)
    and user_id = owner_id and character_id = 'furina' and not compressed and not saved;
  get diagnostics marked = row_count;
  if marked <> cardinality(source_ids) then raise exception 'Memory sources changed concurrently'; end if;
  insert into public.memories (user_id, character_id, kind, content, embedding, importance, source_memory_ids)
    values (owner_id, 'furina', 'summary', summary_text, summary_embedding::extensions.vector, 6, source_ids);
  return true;
end;
$$;
revoke all on function public.commit_furina_compaction(uuid,uuid[],text,text)
  from public, anon, authenticated;
grant execute on function public.commit_furina_compaction(uuid,uuid[],text,text) to service_role;

create or replace function public.correct_furina_memory(
  owner_id uuid, memory_id uuid, new_content text, new_embedding extensions.vector
)
returns boolean language plpgsql set search_path = ''
as $$
declare previous text;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 91241));
  select m.content into previous from public.memories m
    where m.id = memory_id and m.user_id = owner_id and m.character_id = 'furina'
    for update;
  if not found then return false; end if;

  update public.memories m set content = new_content, embedding = new_embedding,
    saved = true, compressed = false, source_memory_ids = null
    where m.id = memory_id;
  if previous is distinct from new_content then
    insert into public.furina_memory_settings(user_id, history_after)
      values(owner_id, pg_catalog.clock_timestamp())
      on conflict (user_id) do update set history_after = excluded.history_after;
  end if;
  return true;
end;
$$;
revoke all on function public.correct_furina_memory(uuid,uuid,text,extensions.vector)
  from public, anon, authenticated;
grant execute on function public.correct_furina_memory(uuid,uuid,text,extensions.vector)
  to service_role;
