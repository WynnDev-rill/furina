create index if not exists furina_active_memory_text_idx on public.memories using gin
  (to_tsvector('simple'::regconfig, content))
  where character_id = 'furina' and kind <> 'self' and merged_into is null;
create index if not exists furina_chat_message_text_idx on public.messages using gin
  (to_tsvector('simple'::regconfig, content))
  where role in ('user', 'assistant');
create index if not exists furina_message_owner_time_idx on public.messages (user_id, created_at desc);

create or replace function public.recall_furina_text(
  owner_id uuid, search_terms text[], include_saved boolean, include_history boolean,
  overview boolean, history_day date, timezone_name text,
  active_thread uuid, thread_window_since timestamptz
)
returns table (id uuid, source text, content text, occurred_at timestamptz)
language sql stable set search_path = ''
as $$
  with policy as (
    select include_saved and coalesce(s.use_saved, true) as saved_on,
      include_history and coalesce(s.use_history, true) as history_on,
      s.history_after as cutoff
    from (select 1) as base left join public.furina_memory_settings s on s.user_id = owner_id
  ), words as (
    select to_tsquery('simple'::regconfig, string_agg(quote_literal(word), ' | ')) as query
    from unnest(tsvector_to_array(to_tsvector('simple'::regconfig, array_to_string(search_terms, ' ')))) as word
  ), days as (
    select history_day::timestamp at time zone coalesce(
      (select name from pg_catalog.pg_timezone_names where name = timezone_name), 'Asia/Jakarta') as start_at,
      (history_day + 1)::timestamp at time zone coalesce(
      (select name from pg_catalog.pg_timezone_names where name = timezone_name), 'Asia/Jakarta') as end_at
    where history_day is not null
  ), saved_notes as (
    select m.id, 'saved'::text as source, left(m.content, 800) as content, m.occurred_at
    from public.memories m cross join policy p cross join words w
    where m.user_id = owner_id and p.saved_on and m.saved
      and m.character_id = 'furina' and m.kind <> 'self' and m.merged_into is null
      and (overview or to_tsvector('simple'::regconfig, m.content) @@ w.query)
    order by ts_rank_cd(to_tsvector('simple'::regconfig, m.content), w.query, 32) desc nulls last,
      m.importance desc, m.created_at desc, m.id
    limit 6
  ), learned_notes as (
    select m.id, 'learned'::text as source, left(m.content, 650) as content, m.occurred_at
    from public.memories m cross join policy p cross join words w
    where m.user_id = owner_id and p.history_on and not m.saved and not m.compressed
      and m.character_id = 'furina' and m.kind <> 'self' and m.merged_into is null
      and (p.cutoff is null or m.created_at > p.cutoff)
      and to_tsvector('simple'::regconfig, m.content) @@ w.query
    order by ts_rank_cd(to_tsvector('simple'::regconfig, m.content), w.query, 32) desc,
      m.importance desc, m.created_at desc, m.id
    limit 6
  ), matching_chats as (
    select m.id, m.role as source,
      left(ts_headline('simple'::regconfig, left(m.content, 24000), w.query,
        'StartSel=,StopSel=,MaxFragments=2,MaxWords=26,MinWords=12'), 620) as content,
      m.created_at as occurred_at
    from public.messages m
    join public.conversations c on c.id = m.conversation_id and c.user_id = m.user_id
    cross join policy p cross join words w left join days d on true
    where p.history_on and m.user_id = owner_id and c.character_id = 'furina'
      and m.role in ('user', 'assistant') and m.status not in ('failed', 'sending')
      and (p.cutoff is null or m.created_at > p.cutoff)
      and (m.conversation_id is distinct from active_thread or thread_window_since is null or m.created_at < thread_window_since)
      and (d.start_at is null or (m.created_at >= d.start_at and m.created_at < d.end_at))
      and to_tsvector('simple'::regconfig, m.content) @@ w.query
    order by ts_rank_cd(to_tsvector('simple'::regconfig, m.content), w.query, 32)
      * case when m.role = 'user' then 1.25 else 1 end desc, m.created_at desc, m.id
    limit 4
  ), dated_chats as (
    select m.id, m.role as source, left(m.content, 620) as content, m.created_at as occurred_at
    from public.messages m
    join public.conversations c on c.id = m.conversation_id and c.user_id = m.user_id
    cross join policy p cross join days d cross join words w
    where p.history_on and m.user_id = owner_id and c.character_id = 'furina'
      and m.role = 'user' and m.status not in ('failed', 'sending')
      and (p.cutoff is null or m.created_at > p.cutoff)
      and (m.conversation_id is distinct from active_thread or thread_window_since is null or m.created_at < thread_window_since)
      and m.created_at >= d.start_at and m.created_at < d.end_at
      and w.query is null
    order by m.created_at desc, m.id
    limit 6
  )
  select * from saved_notes union all select * from learned_notes
  union all select * from matching_chats union all select * from dated_chats;
$$;

revoke all on function public.recall_furina_text(uuid,text[],boolean,boolean,boolean,date,text,uuid,timestamptz)
  from public, anon, authenticated;
grant execute on function public.recall_furina_text(uuid,text[],boolean,boolean,boolean,date,text,uuid,timestamptz)
  to service_role;
