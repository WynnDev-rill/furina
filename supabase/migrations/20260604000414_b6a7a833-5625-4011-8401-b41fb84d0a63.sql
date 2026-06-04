
ALTER TABLE public.memories
  ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'fact';

ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS image_url text,
  ADD COLUMN IF NOT EXISTS sticker_id text;

CREATE INDEX IF NOT EXISTS memories_user_char_kind_idx
  ON public.memories(user_id, character_id, kind);
