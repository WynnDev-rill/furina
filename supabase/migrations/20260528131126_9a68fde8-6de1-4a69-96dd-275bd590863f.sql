create extension if not exists vector;

create table public.memories (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index memories_embedding_idx on public.memories using hnsw (embedding vector_cosine_ops);

grant select, insert, update, delete on public.memories to anon;
grant select, insert, update, delete on public.memories to authenticated;
grant all on public.memories to service_role;

alter table public.memories enable row level security;

create policy "Public can read memories" on public.memories for select using (true);
create policy "Public can insert memories" on public.memories for insert with check (true);
create policy "Public can delete memories" on public.memories for delete using (true);

create or replace function public.match_memories(query_embedding vector(1536), match_count int default 5)
returns table (id uuid, content text, similarity float)
language sql stable
as $$
  select m.id, m.content, 1 - (m.embedding <=> query_embedding) as similarity
  from public.memories m
  order by m.embedding <=> query_embedding
  limit match_count;
$$;

grant execute on function public.match_memories(vector, int) to anon, authenticated, service_role;