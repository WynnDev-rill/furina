
-- Move vector extension out of public schema (security warning fix)
CREATE SCHEMA IF NOT EXISTS extensions;
GRANT USAGE ON SCHEMA extensions TO authenticated, service_role, anon;

-- Note: ALTER EXTENSION vector SET SCHEMA extensions; would break existing columns.
-- Safer: leave existing but grant via search_path. We add extensions to search_path for functions.

-- New columns on memories
ALTER TABLE public.memories
  ADD COLUMN IF NOT EXISTS importance INTEGER NOT NULL DEFAULT 5,
  ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS compressed BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS source_memory_ids UUID[];

-- Allow updates on memories (for edit feature)
DROP POLICY IF EXISTS "Users update own memories" ON public.memories;
CREATE POLICY "Users update own memories" ON public.memories
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Updated match function with importance + recency rerank, and compressed filter
CREATE OR REPLACE FUNCTION public.match_memories(
  query_embedding vector,
  match_user_id uuid,
  match_character_id text,
  match_count integer DEFAULT 5,
  include_compressed boolean DEFAULT false
)
RETURNS TABLE(id uuid, content text, similarity double precision, importance integer, occurred_at timestamptz, kind text)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
  SELECT m.id, m.content,
    (
      0.6 * (1 - (m.embedding <=> query_embedding))
      + 0.25 * (m.importance::float / 10.0)
      + 0.15 * GREATEST(0, 1 - EXTRACT(EPOCH FROM (now() - m.last_accessed_at)) / (60*60*24*30))
    ) AS similarity,
    m.importance,
    m.occurred_at,
    m.kind
  FROM public.memories m
  WHERE m.user_id = match_user_id
    AND m.character_id = match_character_id
    AND (include_compressed OR m.compressed = false)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

-- user_stickers table
CREATE TABLE IF NOT EXISTS public.user_stickers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  url TEXT NOT NULL,
  pack_name TEXT NOT NULL DEFAULT 'custom',
  label TEXT,
  cached_label TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_stickers TO authenticated;
GRANT ALL ON public.user_stickers TO service_role;

ALTER TABLE public.user_stickers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own stickers" ON public.user_stickers
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS user_stickers_user_id_idx ON public.user_stickers(user_id);
CREATE INDEX IF NOT EXISTS memories_user_compressed_idx ON public.memories(user_id, compressed, last_accessed_at DESC);
