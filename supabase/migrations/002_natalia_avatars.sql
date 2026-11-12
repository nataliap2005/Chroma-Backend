-- Ejecutar en Supabase SQL Editor después de 001_natalia_profiles_results.sql.
-- Bucket privado: cada usuario podrá subir y leer solo su propia foto.
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS avatar_path TEXT;

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('avatars', 'avatars', false, 2097152, ARRAY['image/jpeg','image/png','image/webp'])
ON CONFLICT (id) DO UPDATE
SET public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS chroma_avatar_select_own ON storage.objects;
CREATE POLICY chroma_avatar_select_own ON storage.objects
FOR SELECT TO authenticated
USING (bucket_id = 'avatars' AND (storage.foldername(name))[1] = (select auth.uid())::text);

DROP POLICY IF EXISTS chroma_avatar_insert_own ON storage.objects;
CREATE POLICY chroma_avatar_insert_own ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'avatars' AND (storage.foldername(name))[1] = (select auth.uid())::text
  AND name = (select auth.uid())::text || '/avatar');

DROP POLICY IF EXISTS chroma_avatar_update_own ON storage.objects;
CREATE POLICY chroma_avatar_update_own ON storage.objects
FOR UPDATE TO authenticated
USING (bucket_id = 'avatars' AND (storage.foldername(name))[1] = (select auth.uid())::text)
WITH CHECK (bucket_id = 'avatars' AND name = (select auth.uid())::text || '/avatar');

-- No se habilita acceso público ni borrado desde el cliente.
