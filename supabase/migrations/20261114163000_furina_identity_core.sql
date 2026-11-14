-- Guest IDs are legacy browser-generated UUIDs. Account IDs are verified by the server.
create table if not exists public.furina_identity_core (
  user_id uuid primary key,
  revision integer not null default 0 check (revision >= 0),
  state jsonb not null default '{}'::jsonb check (jsonb_typeof(state) = 'object' and octet_length(state::text) <= 18000)
);

alter table public.furina_identity_core enable row level security;
revoke all on public.furina_identity_core from public, anon, authenticated;
grant select, insert, update, delete on public.furina_identity_core to service_role;

-- There is deliberately no foreign key: guests have no auth.users row.
-- Remove account-owned state when Supabase deletes the account.
create or replace function public.delete_furina_identity_core_for_account()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  delete from public.furina_identity_core where user_id = old.id;
  return old;
end;
$$;
revoke all on function public.delete_furina_identity_core_for_account() from public, anon, authenticated;
drop trigger if exists furina_identity_core_account_deleted on auth.users;
create trigger furina_identity_core_account_deleted
after delete on auth.users for each row
execute function public.delete_furina_identity_core_for_account();

-- Commit summary and source markers together. Concurrent requests and sources
-- deleted by the user cannot publish a second or orphaned summary.
create or replace function public.commit_furina_compaction(
  owner_id uuid, source_ids uuid[], summary_text text, summary_embedding text
) returns boolean
language plpgsql set search_path = public, extensions, pg_temp
as $$
declare marked integer;
begin
  if cardinality(source_ids) not between 5 and 30 then return false; end if;
  perform pg_advisory_xact_lock(hashtextextended(owner_id::text, 91241));
  if (select count(*) from public.memories where id = any(source_ids)
      and user_id = owner_id and character_id = 'furina' and not compressed
      and kind <> 'self') <> cardinality(source_ids) then return false; end if;
  update public.memories set compressed = true where id = any(source_ids)
    and user_id = owner_id and character_id = 'furina' and not compressed;
  get diagnostics marked = row_count;
  if marked <> cardinality(source_ids) then
    raise exception 'Memory sources changed concurrently';
  end if;
  insert into public.memories (user_id, character_id, kind, content, embedding, importance, source_memory_ids)
    values (owner_id, 'furina', 'summary', summary_text, summary_embedding::extensions.vector, 6, source_ids);
  return true;
end;
$$;
revoke all on function public.commit_furina_compaction(uuid, uuid[], text, text) from public, anon, authenticated;
grant execute on function public.commit_furina_compaction(uuid, uuid[], text, text) to service_role;
