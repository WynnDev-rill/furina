create index if not exists furina_conversation_owner_recent_idx
  on public.conversations (user_id, updated_at desc) where character_id = 'furina';
create index if not exists furina_message_thread_recent_idx
  on public.messages (conversation_id, created_at desc) where role in ('user', 'assistant');

create or replace function public.recall_furina_recent(
  owner_id uuid, search_terms text[], excluded_thread uuid
)
returns table (thread_id uuid, title text, last_at timestamptz, turns jsonb)
language sql stable set search_path = ''
as $$
  with allowed as (
    select greatest(now() - interval '72 hours', s.history_after) as after_at,
      s.history_after as privacy_cutoff
    from (select 1) as stub
    left join public.furina_memory_settings s on s.user_id = owner_id
    where coalesce(s.use_history, true)
  ), words as (
    select to_tsquery('simple'::regconfig, string_agg(quote_literal(word), ' | ')) as query
    from unnest(tsvector_to_array(to_tsvector('simple'::regconfig, array_to_string(search_terms, ' ')))) as word
  ), candidate_threads as (
    select c.id, c.title, c.updated_at
    from public.conversations c cross join allowed a
    where c.user_id = owner_id and c.character_id = 'furina'
      and c.id is distinct from excluded_thread and c.updated_at > a.after_at
    order by c.updated_at desc, c.id
    limit 16
  ), ranked as (
    select c.id, case when a.privacy_cutoff is null then left(c.title, 100) else '' end as safe_title,
      evidence.latest,
      case when w.query is null then 0 else
        coalesce(ts_rank_cd(to_tsvector('simple'::regconfig, evidence.user_text), w.query), 0)
        + case when a.privacy_cutoff is null then
          coalesce(ts_rank_cd(to_tsvector('simple'::regconfig, c.title), w.query), 0) else 0 end
      end as score,
      w.query
    from candidate_threads c cross join allowed a cross join words w
    cross join lateral (
      select max(m.created_at) as latest, string_agg(left(m.content, 480), ' ') as user_text
      from (
        select original.created_at, original.content
        from public.messages original
        where original.conversation_id = c.id and original.user_id = owner_id
          and original.role = 'user' and original.status not in ('failed', 'sending')
          and original.created_at > a.after_at and length(btrim(original.content)) >= 14
          and original.content ~ '[[:alpha:]]+[[:space:]]+[[:alpha:]]'
        order by original.created_at desc, original.id
        limit 6
      ) m
    ) evidence
    where evidence.latest is not null
  )
  select r.id, r.safe_title, r.latest, snippets.turns
  from (
    select id, safe_title, latest, score
    from ranked
    where query is null or score > 0
    order by score desc, latest desc, id
    limit 2
  ) r cross join allowed a
  cross join lateral (
    select jsonb_agg(
      jsonb_build_object('role', item.role, 'text', left(item.content, 420), 'at', item.created_at)
      order by item.created_at, item.id
    ) as turns
    from (
      select m.id, m.role, m.content, m.created_at
      from public.messages m
      where m.conversation_id = r.id and m.user_id = owner_id
        and m.role in ('user', 'assistant') and m.status not in ('failed', 'sending')
        and m.created_at > a.after_at and length(btrim(m.content)) > 0
      order by m.created_at desc, m.id
      limit 4
    ) item
  ) snippets
  order by r.score desc, r.latest desc, r.id;
$$;

revoke all on function public.recall_furina_recent(uuid,text[],uuid)
  from public, anon, authenticated;
grant execute on function public.recall_furina_recent(uuid,text[],uuid)
  to service_role;
