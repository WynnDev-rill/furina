create or replace function public.match_memories(query_embedding vector(1536), match_count int default 5)
returns table (id uuid, content text, similarity float)
language sql stable
security invoker
set search_path = public
as $$
  select m.id, m.content, 1 - (m.embedding <=> query_embedding) as similarity
  from public.memories m
  order by m.embedding <=> query_embedding
  limit match_count;
$$;