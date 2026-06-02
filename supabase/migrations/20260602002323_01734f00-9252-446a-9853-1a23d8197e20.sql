
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS audio_url TEXT,
  ADD COLUMN IF NOT EXISTS audio_emotion TEXT;

INSERT INTO storage.buckets (id, name, public)
VALUES ('voice-samples', 'voice-samples', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Users read own voice samples"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'voice-samples' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users upload own voice samples"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'voice-samples' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users delete own voice samples"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'voice-samples' AND auth.uid()::text = (storage.foldername(name))[1]);
