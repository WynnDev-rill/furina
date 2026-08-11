-- Public-readiness hardening: the original memories migration granted anon
-- broad CRUD/read access. Client publishable keys are intentionally public,
-- so authorization must be enforced by RLS instead of secrecy of the key.

ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.memories FROM anon;

DROP POLICY IF EXISTS "Public can read memories" ON public.memories;
DROP POLICY IF EXISTS "Public can insert memories" ON public.memories;
DROP POLICY IF EXISTS "Public can delete memories" ON public.memories;
DROP POLICY IF EXISTS "Users read own memories" ON public.memories;
DROP POLICY IF EXISTS "Users insert own memories" ON public.memories;
DROP POLICY IF EXISTS "Users update own memories" ON public.memories;
DROP POLICY IF EXISTS "Users delete own memories" ON public.memories;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.memories TO authenticated;
GRANT ALL ON public.memories TO service_role;

CREATE POLICY "Users read own memories"
ON public.memories FOR SELECT TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users insert own memories"
ON public.memories FOR INSERT TO authenticated
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own memories"
ON public.memories FOR UPDATE TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users delete own memories"
ON public.memories FOR DELETE TO authenticated
USING (auth.uid() = user_id);

-- The current five-argument match_memories function is a server-only RPC.
-- Keep it inaccessible to client/public roles even if an earlier migration
-- or manual grant reintroduced EXECUTE privileges.
DO $$
BEGIN
  IF to_regprocedure('public.match_memories(extensions.vector,uuid,text,integer,boolean)') IS NOT NULL THEN
    REVOKE EXECUTE ON FUNCTION public.match_memories(extensions.vector, uuid, text, integer, boolean)
      FROM PUBLIC, anon, authenticated;
    GRANT EXECUTE ON FUNCTION public.match_memories(extensions.vector, uuid, text, integer, boolean)
      TO service_role;
  END IF;
END
$$;
