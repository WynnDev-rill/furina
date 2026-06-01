
REVOKE EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer) FROM anon;
REVOKE EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.match_memories(vector, uuid, text, integer) TO service_role;
