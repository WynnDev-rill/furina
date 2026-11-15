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
    -- Discard only linked automatic summaries and make their remaining sources available.
    with recursive stale(id) as (
      select m.id from public.memories m
      where m.user_id = owner_id and m.character_id = 'furina' and not m.saved
        and m.source_memory_ids @> array[memory_id]
      union
      select m.id from public.memories m
      join stale s on m.source_memory_ids @> array[s.id]
      where m.user_id = owner_id and m.character_id = 'furina' and not m.saved
    ), removed as (
      delete from public.memories m where m.id in (select s.id from stale s)
      returning m.id, m.source_memory_ids
    )
    update public.memories m set compressed = false
    where m.user_id = owner_id and m.character_id = 'furina' and m.compressed
      and exists (select 1 from removed r where r.source_memory_ids @> array[m.id])
      and not exists (
        select 1 from public.memories p
        where p.user_id = owner_id and p.character_id = 'furina' and not p.compressed
          and p.source_memory_ids @> array[m.id] and p.id not in (select r.id from removed r)
      );
  end if;
  return true;
end;
$$;
revoke all on function public.correct_furina_memory(uuid,uuid,text,extensions.vector)
  from public, anon, authenticated;
grant execute on function public.correct_furina_memory(uuid,uuid,text,extensions.vector)
  to service_role;
