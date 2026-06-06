ALTER TABLE public.memories ADD COLUMN IF NOT EXISTS emotion text;

CREATE TABLE IF NOT EXISTS public.entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  character_id text NOT NULL DEFAULT 'furina',
  name text NOT NULL,
  name_normalized text NOT NULL,
  type text NOT NULL DEFAULT 'person',
  aliases text[] DEFAULT '{}',
  notes text,
  mention_count int NOT NULL DEFAULT 1,
  last_mentioned_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, character_id, name_normalized)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entities TO authenticated;
GRANT ALL ON public.entities TO service_role;
ALTER TABLE public.entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own entities" ON public.entities FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.entity_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  from_entity uuid NOT NULL REFERENCES public.entities(id) ON DELETE CASCADE,
  to_entity uuid NOT NULL REFERENCES public.entities(id) ON DELETE CASCADE,
  label text NOT NULL,
  strength int NOT NULL DEFAULT 5,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entity_relations TO authenticated;
GRANT ALL ON public.entity_relations TO service_role;
ALTER TABLE public.entity_relations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own relations" ON public.entity_relations FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP TABLE IF EXISTS public.user_stickers;