alter table public.messages add column if not exists reply_to jsonb;
alter table public.messages drop constraint if exists messages_reply_to_bounded;
alter table public.messages add constraint messages_reply_to_bounded
  check (reply_to is null or (jsonb_typeof(reply_to) = 'object' and octet_length(reply_to::text) <= 1800));

create table if not exists public.furina_user_profile (
  user_id uuid primary key references auth.users(id) on delete cascade,
  birth_date date,
  greeted_year integer,
  constraint birth_date_supported check (birth_date is null or birth_date >= date '1900-01-01')
);
alter table public.furina_user_profile enable row level security;
revoke all on public.furina_user_profile from public, anon, authenticated;
grant select, insert, update, delete on public.furina_user_profile to service_role;

-- A failed clone leaves no partial conversation. The caller's ordinary RLS applies.
create or replace function public.create_furina_message_branch(
  branch_id uuid, branch_title text, prefix jsonb
) returns void language plpgsql security invoker set search_path = ''
as $$
declare owner uuid := auth.uid();
begin
  if owner is null or jsonb_typeof(prefix) is distinct from 'array' then
    raise exception 'Invalid conversation branch';
  end if;
  insert into public.conversations(id,user_id,character_id,title)
    values(branch_id, owner, 'furina', branch_title);
  insert into public.messages(id,conversation_id,user_id,role,content,status,created_at,audio_url,audio_emotion,image_url,sticker_id,reply_to)
    select p.id,branch_id,owner,p.role,p.content,p.status,p.created_at,p.audio_url,p.audio_emotion,p.image_url,p.sticker_id,p.reply_to
    from jsonb_populate_recordset(null::public.messages, prefix) p;
end;
$$;
revoke all on function public.create_furina_message_branch(uuid,text,jsonb) from public, anon;
grant execute on function public.create_furina_message_branch(uuid,text,jsonb) to authenticated;
