alter table public.memories
  add column if not exists merged_into uuid,
  add column if not exists dedup_checked_at timestamptz;

create index if not exists memories_merge_active_idx
  on public.memories(user_id, dedup_checked_at, created_at)
  where merged_into is null and not saved and not compressed;

-- Serialize against a user correction, forgetting, or another merge.
create or replace function public.merge_furina_memories(
  owner_id uuid, canonical_id uuid, snapshots jsonb, merged_content text,
  merged_embedding extensions.vector
) returns boolean language plpgsql set search_path = ''
as $$
declare
  boundary timestamptz;
  enabled boolean;
  source_ids uuid[];
begin
  if jsonb_typeof(snapshots) is distinct from 'array' then return false; end if;
  if jsonb_array_length(snapshots) not between 2 and 3
      or char_length(merged_content) not between 1 and 800 then return false; end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 91241));
  select s.history_after, s.use_history into boundary, enabled
    from public.furina_memory_settings s where s.user_id = owner_id for share;
  if enabled is false then return false; end if;
  select array_agg(distinct p.id) into source_ids
    from jsonb_to_recordset(snapshots) p(id uuid, content text, kind text, occurred_at timestamptz)
    join public.memories m on m.id = p.id
    where m.user_id = owner_id and m.character_id = 'furina'
      and not m.saved and not m.compressed and m.merged_into is null
      and m.kind in ('fact', 'preference', 'relation', 'episodic', 'summary')
      and m.content = p.content and m.kind = p.kind
      and m.occurred_at is not distinct from p.occurred_at
      and (boundary is null or m.created_at > boundary);
  if coalesce(cardinality(source_ids), 0) <> jsonb_array_length(snapshots)
      or not (canonical_id = any(source_ids)) then return false; end if;
  if (select count(distinct m.kind) from public.memories m where m.id = any(source_ids)) <> 1
      or exists (
        select 1 from public.memories a join public.memories b on b.id = canonical_id
        where a.id = any(source_ids) and a.occurred_at is distinct from b.occurred_at
      ) then return false; end if;
  update public.memories m
    set merged_into = canonical_id
    where m.user_id = owner_id and m.character_id = 'furina' and m.id <> canonical_id
      and (m.id = any(source_ids) or m.merged_into = any(source_ids));
  update public.memories m
    set content = merged_content, embedding = merged_embedding,
      importance = (select max(s.importance) from public.memories s where s.id = any(source_ids)),
      dedup_checked_at = pg_catalog.clock_timestamp()
    where m.id = canonical_id;
  return true;
end;
$$;

create or replace function public.claim_furina_memory_scan(owner_id uuid)
returns table (id uuid, content text, kind text, occurred_at timestamptz, embedding extensions.vector)
language plpgsql set search_path = ''
as $$
declare
  boundary timestamptz;
  enabled boolean;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 91241));
  select s.history_after, s.use_history into boundary, enabled from public.furina_memory_settings s
    where s.user_id = owner_id for share;
  if enabled is false or exists (
    select 1 from public.memories m where m.user_id = owner_id and m.character_id = 'furina'
      and m.dedup_checked_at > pg_catalog.now() - interval '10 minutes'
  ) then return; end if;
  return query update public.memories m set dedup_checked_at = pg_catalog.clock_timestamp()
    where m.id = (
      select a.id from public.memories a where a.user_id = owner_id and a.character_id = 'furina'
        and a.merged_into is null and not a.saved and not a.compressed
        and a.kind in ('fact','preference','relation','episodic','summary')
        and a.content not like '[Ringkasan otomatis]:%'
        and (boundary is null or a.created_at > boundary)
        and (a.dedup_checked_at is null or a.dedup_checked_at < pg_catalog.now() - interval '7 days')
      order by a.dedup_checked_at nulls first, a.created_at, a.id limit 1
    ) returning m.id, m.content, m.kind, m.occurred_at, m.embedding;
end;
$$;

revoke all on function public.merge_furina_memories(uuid,uuid,jsonb,text,extensions.vector),
  public.claim_furina_memory_scan(uuid) from public, anon, authenticated;
grant execute on function public.merge_furina_memories(uuid,uuid,jsonb,text,extensions.vector),
  public.claim_furina_memory_scan(uuid) to service_role;

create or replace function public.forget_furina_memory(owner_id uuid, memory_id uuid)
returns boolean language plpgsql set search_path = ''
as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner_id::text, 91241));
  delete from public.memories m
    where m.user_id = owner_id and m.character_id = 'furina'
      and (memory_id is null or m.id = memory_id or m.merged_into = memory_id);
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
    and m.merged_into is null
    and 1 - (m.embedding <=> query_vec) >= 0.28
  order by (1 - (m.embedding <=> query_vec)) * 0.8
    + (m.importance::float / 10) * 0.15 + case when m.saved then 0.05 else 0 end desc
  limit least(40, greatest(1, row_count));
$$;
revoke all on function public.find_furina_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  from public, anon, authenticated;
grant execute on function public.find_furina_memories(uuid,extensions.vector,boolean,boolean,timestamptz,integer)
  to service_role;

