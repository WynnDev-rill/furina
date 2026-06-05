
-- Move vector extension to extensions schema
ALTER EXTENSION vector SET SCHEMA extensions;

-- Make sure existing search_path on functions still works
ALTER FUNCTION public.match_memories(extensions.vector, uuid, text, integer, boolean)
  SET search_path = public, extensions;
