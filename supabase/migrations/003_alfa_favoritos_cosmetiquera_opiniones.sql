-- Funciones del alfa: favoritos, cosmetiquera, opinión sobre el tono y panel del alfa.
-- Ejecutar una vez en Supabase: SQL Editor → pegar este archivo → Run.
-- Ejecutar después de 001_natalia_profiles_results.sql (usa public.colorimetry_results).
-- Los product_id son los del catálogo (CH-5001…); el catálogo vive en el backend, por eso no hay llave foránea.

-- Favoritos -------------------------------------------------------------------
create table if not exists public.favorites (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  product_id text not null check (product_id ~ '^CH-[0-9]{3,5}$'),
  created_at timestamptz not null default now(),
  primary key (user_id, product_id)
);

-- Cosmetiquera: productos que la usuaria ya tiene ---------------------------------
create table if not exists public.vanity (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  product_id text not null check (product_id ~ '^CH-[0-9]{3,5}$'),
  added_at timestamptz not null default now(),
  primary key (user_id, product_id)
);

-- Opinión sobre el tono (3 niveles), una por usuaria y producto ---------------------
create table if not exists public.tone_feedback (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  product_id text not null check (product_id ~ '^CH-[0-9]{3,5}$'),
  tono_resultado text not null check (tono_resultado in ('acertado', 'parcial', 'incorrecto')),
  motivo_tono text not null default ''
    check (motivo_tono in ('', 'muy_claro', 'muy_oscuro', 'muy_rosado', 'muy_amarillo', 'acabado', 'otro')),
  forma_evaluacion text not null check (forma_evaluacion in ('probado', 'pantalla')),
  comment text not null default '' check (char_length(comment) <= 250),
  confidence_before smallint check (confidence_before between 1 and 5),
  confidence_after smallint check (confidence_after between 1 and 5),
  created_at timestamptz not null default now(),
  primary key (user_id, product_id),
  -- si el tono no acertó, hay que decir qué falló; si acertó, no hay motivo
  constraint motivo_segun_resultado check (
    (tono_resultado = 'acertado' and motivo_tono = '') or (tono_resultado <> 'acertado' and motivo_tono <> ''))
);

-- Cada usuaria solo ve y cambia lo suyo -------------------------------------------
alter table public.favorites enable row level security;
alter table public.vanity enable row level security;
alter table public.tone_feedback enable row level security;

drop policy if exists "favoritos_propios" on public.favorites;
create policy "favoritos_propios" on public.favorites for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "cosmetiquera_propia" on public.vanity;
create policy "cosmetiquera_propia" on public.vanity for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "opiniones_propias" on public.tone_feedback;
create policy "opiniones_propias" on public.tone_feedback for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

revoke all on public.favorites, public.vanity, public.tone_feedback from anon;
grant select, insert, update, delete on public.favorites, public.vanity, public.tone_feedback to authenticated;

-- Panel del alfa: datos agregados, sin nombres, correos ni ids de usuarias -----------
-- El backend (POST /api/panel) hace los cálculos por categoría, marca y KR.
create or replace function public.alpha_panel_data()
returns jsonb
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  with ultimo_perfil as (
    select distinct on (user_id) user_id, undertone
    from public.colorimetry_results
    order by user_id, created_at desc
  )
  select jsonb_build_object(
    'usuarias', (select count(*) from auth.users),
    'con_perfil', (select count(*) from ultimo_perfil),
    'usuarias_con_feedback', (select count(distinct user_id) from public.tone_feedback),
    -- KR3: guardó un favorito, usó la cosmetiquera o dijo que un tono le sirvió
    'usuarias_activas', (select count(*) from (
        select user_id from public.favorites
        union select user_id from public.vanity
        union select user_id from public.tone_feedback where tono_resultado <> 'incorrecto') a),
    'evaluaciones', coalesce((
      select jsonb_agg(jsonb_build_object(
        'product_id', f.product_id, 'tono_resultado', f.tono_resultado, 'motivo_tono', f.motivo_tono,
        'forma_evaluacion', f.forma_evaluacion, 'confidence_before', f.confidence_before,
        'confidence_after', f.confidence_after, 'undertone', p.undertone))
      from public.tone_feedback f left join ultimo_perfil p on p.user_id = f.user_id), '[]'::jsonb)
  );
$$;

revoke all on function public.alpha_panel_data() from public, anon;
grant execute on function public.alpha_panel_data() to authenticated;
