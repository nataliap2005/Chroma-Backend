-- Opiniones sobre los looks del asesor: si le gusta, si lo usaría y un comentario.
-- Ejecutar después de la 004 (usa public.is_chroma_admin). Se puede repetir sin dañar nada.

create table if not exists public.look_feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  occasion text not null check (char_length(occasion) between 1 and 40),
  product_ids text[] not null default '{}',
  budget integer check (budget is null or budget >= 0),
  le_gusta text not null check (le_gusta in ('mucho', 'algo', 'no')),
  lo_usaria text not null check (lo_usaria in ('si', 'tal_vez', 'no')),
  comment text not null default '' check (char_length(comment) <= 500),
  created_at timestamptz not null default now()
);
create index if not exists look_feedback_created_idx on public.look_feedback(created_at desc);

-- Cada usuaria crea y ve solo sus opiniones; no se editan ni se borran desde la app.
alter table public.look_feedback enable row level security;
drop policy if exists "opiniones_looks_propias_leer" on public.look_feedback;
create policy "opiniones_looks_propias_leer" on public.look_feedback for select to authenticated
  using (user_id = auth.uid());
drop policy if exists "opiniones_looks_propias_crear" on public.look_feedback;
create policy "opiniones_looks_propias_crear" on public.look_feedback for insert to authenticated
  with check (user_id = auth.uid());
revoke all on public.look_feedback from anon, authenticated;
grant select, insert on public.look_feedback to authenticated;

-- Para administradoras: todas las opiniones sobre looks, con el correo de quien opina.
create or replace function public.admin_list_look_feedback()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'email', u.email, 'nombre', p.display_name, 'occasion', f.occasion, 'budget', f.budget,
      'productos', coalesce((select jsonb_agg(c.marca || ' · ' || c.nombre) from public.catalog_products c where c.id = any(f.product_ids)), '[]'::jsonb),
      'le_gusta', f.le_gusta, 'lo_usaria', f.lo_usaria, 'comment', f.comment, 'created_at', f.created_at)
      order by f.created_at desc)
    from public.look_feedback f
    join auth.users u on u.id = f.user_id
    left join public.profiles p on p.user_id = f.user_id), '[]'::jsonb);
end;
$$;
revoke all on function public.admin_list_look_feedback() from public, anon;
grant execute on function public.admin_list_look_feedback() to authenticated;
