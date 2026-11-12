-- ============================================================
-- CHROMA APP
-- Migración 001: Perfiles y resultados de colorimetría
-- Supabase PostgreSQL
-- ============================================================

-- 1. TABLA DE PERFILES
-- auth.users es administrada por Supabase Auth.

CREATE TABLE IF NOT EXISTS public.profiles (
    user_id UUID PRIMARY KEY
        REFERENCES auth.users(id) ON DELETE CASCADE,

    display_name TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 2. TABLA DE RESULTADOS DE COLORIMETRÍA

CREATE TABLE IF NOT EXISTS public.colorimetry_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES auth.users(id) ON DELETE CASCADE,

    questionnaire_version INTEGER NOT NULL,

    answers JSONB NOT NULL,
    analysis JSONB NOT NULL,

    season TEXT NOT NULL,
    undertone TEXT NOT NULL,

    engine TEXT NOT NULL DEFAULT 'typescript-preview',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 3. ÍNDICE PARA CONSULTAR RESULTADOS POR USUARIO

CREATE INDEX IF NOT EXISTS colorimetry_results_user_created_idx
ON public.colorimetry_results (user_id, created_at DESC);


-- 4. ACTIVAR ROW LEVEL SECURITY (RLS)

ALTER TABLE public.profiles
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.colorimetry_results
ENABLE ROW LEVEL SECURITY;


-- 5. POLÍTICAS DE SEGURIDAD: PROFILES

-- Cada usuario puede consultar únicamente su perfil.

DROP POLICY IF EXISTS profile_select_own
ON public.profiles;

CREATE POLICY profile_select_own
ON public.profiles
FOR SELECT
TO authenticated
USING (
    (SELECT auth.uid()) = user_id
);


-- Cada usuario puede insertar únicamente su perfil.

DROP POLICY IF EXISTS profile_insert_own
ON public.profiles;

CREATE POLICY profile_insert_own
ON public.profiles
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT auth.uid()) = user_id
);


-- Cada usuario puede actualizar únicamente su perfil.

DROP POLICY IF EXISTS profile_update_own
ON public.profiles;

CREATE POLICY profile_update_own
ON public.profiles
FOR UPDATE
TO authenticated
USING (
    (SELECT auth.uid()) = user_id
)
WITH CHECK (
    (SELECT auth.uid()) = user_id
);


-- 6. POLÍTICAS DE SEGURIDAD: COLORIMETRY_RESULTS

-- Consultar únicamente resultados propios.

DROP POLICY IF EXISTS results_select_own
ON public.colorimetry_results;

CREATE POLICY results_select_own
ON public.colorimetry_results
FOR SELECT
TO authenticated
USING (
    (SELECT auth.uid()) = user_id
);


-- Guardar únicamente resultados propios.

DROP POLICY IF EXISTS results_insert_own
ON public.colorimetry_results;

CREATE POLICY results_insert_own
ON public.colorimetry_results
FOR INSERT
TO authenticated
WITH CHECK (
    (SELECT auth.uid()) = user_id
);


-- No se crean políticas UPDATE o DELETE para resultados.
-- Los usuarios no podrán modificar ni eliminar sus resultados
-- mediante la API con sus permisos habituales.


-- 7. FUNCIÓN PARA CREAR PERFILES AUTOMÁTICAMENTE

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN

    INSERT INTO public.profiles (
        user_id,
        display_name
    )
    VALUES (
        NEW.id,
        NEW.raw_user_meta_data ->> 'display_name'
    )
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;

END;
$$;


-- 8. TRIGGER DE REGISTRO DE USUARIOS

DROP TRIGGER IF EXISTS on_auth_user_created
ON auth.users;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_user();


-- 9. SEGURIDAD DE LA FUNCIÓN

-- Impedir su ejecución directa desde los roles cliente.

REVOKE EXECUTE ON FUNCTION public.handle_new_user()
FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION public.handle_new_user()
FROM anon, authenticated;

REVOKE EXECUTE ON FUNCTION public.handle_new_user()
FROM service_role;


-- ============================================================
-- FIN DE LA MIGRACIÓN 001 - CHROMA APP
-- ============================================================
