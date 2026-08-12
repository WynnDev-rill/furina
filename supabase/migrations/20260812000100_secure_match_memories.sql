-- FUR-ENG-031: SECURITY DEFINER must never trust a caller-supplied user id.
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
  WHERE auth.uid() IS NOT NULL
    AND auth.uid() = match_user_id
    AND m.user_id = auth.uid()
    AND m.character_id = match_character_id
    AND (include_compressed OR m.compressed = false)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

REVOKE ALL ON FUNCTION public.match_memories(vector, uuid, text, integer, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer, boolean) TO authenticated;
