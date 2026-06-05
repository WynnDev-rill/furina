
REVOKE EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer, boolean) FROM anon, authenticated, public;
GRANT EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer, boolean) TO service_role;
