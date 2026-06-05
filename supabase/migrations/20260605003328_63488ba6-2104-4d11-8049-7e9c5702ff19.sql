
-- Stickers bucket: user hanya boleh CRUD file di folder {user_id}/
DROP POLICY IF EXISTS "Stickers user CRUD own" ON storage.objects;
CREATE POLICY "Stickers user CRUD own" ON storage.objects
  FOR ALL TO authenticated
  USING (bucket_id = 'stickers' AND (storage.foldername(name))[1] = auth.uid()::text)
  WITH CHECK (bucket_id = 'stickers' AND (storage.foldername(name))[1] = auth.uid()::text);

-- Voice samples bucket: same pattern (might already exist; idempotent)
DROP POLICY IF EXISTS "Voice samples user CRUD own" ON storage.objects;
CREATE POLICY "Voice samples user CRUD own" ON storage.objects
  FOR ALL TO authenticated
  USING (bucket_id = 'voice-samples' AND (storage.foldername(name))[1] = auth.uid()::text)
  WITH CHECK (bucket_id = 'voice-samples' AND (storage.foldername(name))[1] = auth.uid()::text);
