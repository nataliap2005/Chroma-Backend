-- Catálogo administrable, fotos de productos, opiniones para administradoras y pagos con Wompi.
-- Ejecutar DESPUÉS de la 004 (usa public.is_chroma_admin y public.user_plans).
-- Supabase → SQL Editor → pegar este archivo → Run. Se puede repetir sin dañar nada.
-- Luego ejecutar 006_catalogo_inicial.sql para cargar los 688 productos iniciales.

-- 1. Catálogo -------------------------------------------------------------------------
-- Mismas columnas que data/productos_mvp.csv del backend, más "activo" y fechas.
create table if not exists public.catalog_products (
  id text primary key check (id ~ '^CH-[0-9]{3,5}$'),
  nombre text not null check (char_length(nombre) between 1 and 160),
  marca text not null check (char_length(marca) between 1 and 80),
  categoria text not null check (categoria in ('Base', 'Corrector', 'Rubor', 'Bronzer', 'Iluminador', 'Labial', 'Sombras')),
  tono text not null default '',
  profundidad text not null default '',
  subtono text not null default '',
  acabado text not null default '',
  color_hex text not null check (color_hex ~ '^#[0-9A-Fa-f]{6}$'),
  precio_cop integer not null check (precio_cop >= 0),
  tipos_piel text not null default '',
  estacion text not null default '',
  descripcion text not null default '',
  imagen text not null default '',
  nivel text not null default 'B',
  calidad text not null default 'ok',
  fuente text not null default '',
  precio_fuente text not null default '',
  tienda text not null default '',
  tienda_url text not null default '',
  enlace_tipo text not null default 'producto',
  panes text not null default '',
  origen_color text not null default 'oficial',
  activo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- Si la tabla ya existía con menos columnas, se completan.
alter table public.catalog_products add column if not exists profundidad text not null default '';
alter table public.catalog_products add column if not exists tipos_piel text not null default '';
alter table public.catalog_products add column if not exists estacion text not null default '';
alter table public.catalog_products add column if not exists descripcion text not null default '';
alter table public.catalog_products add column if not exists nivel text not null default 'B';
alter table public.catalog_products add column if not exists precio_fuente text not null default '';
alter table public.catalog_products add column if not exists enlace_tipo text not null default 'producto';
alter table public.catalog_products add column if not exists panes text not null default '';
alter table public.catalog_products add column if not exists origen_color text not null default 'oficial';
alter table public.catalog_products add column if not exists activo boolean not null default true;
alter table public.catalog_products add column if not exists created_at timestamptz not null default now();

create index if not exists catalog_products_category_idx on public.catalog_products(categoria);
create index if not exists catalog_products_brand_idx on public.catalog_products(marca);

-- Ids nuevos para productos creados desde la app (los iniciales llegan hasta CH-7574).
create sequence if not exists public.catalog_product_seq start 8001;
alter table public.catalog_products alter column id set default ('CH-' || nextval('public.catalog_product_seq'));

create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;
drop trigger if exists catalog_products_touch on public.catalog_products;
create trigger catalog_products_touch before update on public.catalog_products
  for each row execute function public.touch_updated_at();

alter table public.catalog_products enable row level security;
drop policy if exists "catalogo_publico_lectura" on public.catalog_products;
drop policy if exists "catalogo_lectura" on public.catalog_products;
create policy "catalogo_lectura" on public.catalog_products for select to anon
  using (activo);
drop policy if exists "catalogo_lectura_cuentas" on public.catalog_products;
create policy "catalogo_lectura_cuentas" on public.catalog_products for select to authenticated
  using (activo or public.is_chroma_admin());  -- las administradoras también ven los desactivados
drop policy if exists "catalogo_admin_escritura" on public.catalog_products;
create policy "catalogo_admin_escritura" on public.catalog_products for all to authenticated
  using (public.is_chroma_admin()) with check (public.is_chroma_admin());
revoke all on public.catalog_products from anon, authenticated;
grant select on public.catalog_products to anon, authenticated;
grant insert, update, delete on public.catalog_products to authenticated;  -- la política deja solo a administradoras
grant usage on sequence public.catalog_product_seq to authenticated;

-- 2. Fotos de productos: bucket público de lectura; solo administradoras suben o borran ---------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('product-images', 'product-images', true, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = true, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "fotos_productos_lectura" on storage.objects;
create policy "fotos_productos_lectura" on storage.objects for select to anon, authenticated
  using (bucket_id = 'product-images');
drop policy if exists "fotos_productos_admin_insert" on storage.objects;
create policy "fotos_productos_admin_insert" on storage.objects for insert to authenticated
  with check (bucket_id = 'product-images' and public.is_chroma_admin());
drop policy if exists "fotos_productos_admin_update" on storage.objects;
create policy "fotos_productos_admin_update" on storage.objects for update to authenticated
  using (bucket_id = 'product-images' and public.is_chroma_admin());
drop policy if exists "fotos_productos_admin_delete" on storage.objects;
create policy "fotos_productos_admin_delete" on storage.objects for delete to authenticated
  using (bucket_id = 'product-images' and public.is_chroma_admin());

-- 3. Lo que dicen las usuarias: opiniones sobre los tonos, para administradoras -----------------
create or replace function public.admin_list_feedback()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'email', u.email, 'nombre', p.display_name, 'product_id', f.product_id,
      'producto', c.nombre, 'marca', c.marca, 'tono', c.tono,
      'tono_resultado', f.tono_resultado, 'motivo_tono', f.motivo_tono, 'forma_evaluacion', f.forma_evaluacion,
      'comment', f.comment, 'confidence_before', f.confidence_before, 'confidence_after', f.confidence_after,
      'created_at', f.created_at) order by f.created_at desc)
    from public.tone_feedback f
    join auth.users u on u.id = f.user_id
    left join public.profiles p on p.user_id = f.user_id
    left join public.catalog_products c on c.id = f.product_id), '[]'::jsonb);
end;
$$;
revoke all on function public.admin_list_feedback() from public, anon;
grant execute on function public.admin_list_feedback() to authenticated;

-- 4. Pagos con Wompi -------------------------------------------------------------------
-- El backend crea el pago (PENDING) y lo confirma con el evento de Wompi, usando la clave
-- service_role que SOLO vive en el servidor. Las usuarias solo pueden leer sus propios pagos.
create table if not exists public.payments (
  reference text primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null check (plan in ('plus', 'premium')),
  amount_in_cents bigint not null check (amount_in_cents > 0),
  currency text not null default 'COP',
  status text not null default 'PENDING' check (status in ('PENDING', 'APPROVED', 'DECLINED', 'VOIDED', 'ERROR')),
  wompi_transaction_id text,
  payment_method text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists payments_user_idx on public.payments(user_id, created_at desc);
drop trigger if exists payments_touch on public.payments;
create trigger payments_touch before update on public.payments
  for each row execute function public.touch_updated_at();

alter table public.payments enable row level security;
drop policy if exists "pagos_propios" on public.payments;
create policy "pagos_propios" on public.payments for select to authenticated
  using (user_id = auth.uid() or public.is_chroma_admin());
revoke all on public.payments from anon, authenticated;
grant select on public.payments to authenticated;

-- 5. Vencimiento del plan pagado ----------------------------------------------------------
-- Un pago aprobado da 30 días del plan. Al vencer, la usuaria vuelve a Free sin que nadie haga nada.
-- Un plan asignado por una administradora no vence (plan_expires_at = null).
alter table public.user_plans add column if not exists plan_expires_at timestamptz;

create or replace function public.effective_plan(p_uid uuid)
returns text language sql stable security definer set search_path = public, pg_temp as $$
  select coalesce((
    select case when up.plan_expires_at is not null and up.plan_expires_at < now() then 'free' else up.plan end
    from public.user_plans up where up.user_id = p_uid), 'free');
$$;
revoke all on function public.effective_plan(uuid) from public, anon, authenticated;

-- Pago aprobado: suma 30 días al plan (desde hoy o desde el vencimiento actual si sigue vigente).
-- Solo la llama el backend con service_role.
create or replace function public.apply_payment(p_reference text, p_status text, p_transaction_id text, p_method text)
returns jsonb language plpgsql volatile security definer set search_path = public, pg_temp as $$
declare
  v_pay public.payments%rowtype;
  v_hasta timestamptz;
begin
  select * into v_pay from public.payments where reference = p_reference for update;
  if not found then raise sqlstate 'PT404' using message = 'Pago desconocido.'; end if;
  if v_pay.status = 'APPROVED' then  -- Wompi puede repetir el evento: no se suma dos veces
    return jsonb_build_object('reference', p_reference, 'status', v_pay.status, 'repetido', true);
  end if;
  update public.payments set status = p_status, wompi_transaction_id = p_transaction_id, payment_method = p_method
    where reference = p_reference;
  if p_status = 'APPROVED' then
    select greatest(now(), coalesce(case when up.plan = v_pay.plan then up.plan_expires_at end, now())) + interval '30 days'
      into v_hasta from public.user_plans up where up.user_id = v_pay.user_id;
    v_hasta := coalesce(v_hasta, now() + interval '30 days');
    insert into public.user_plans(user_id, plan, plan_expires_at, updated_at)
    values (v_pay.user_id, v_pay.plan, v_hasta, now())
    on conflict (user_id) do update set plan = excluded.plan, plan_expires_at = excluded.plan_expires_at, updated_at = now();
  end if;
  return jsonb_build_object('reference', p_reference, 'status', p_status, 'user_id', v_pay.user_id,
                            'plan', v_pay.plan, 'hasta', v_hasta, 'repetido', false);
end;
$$;
revoke all on function public.apply_payment(text, text, text, text) from public, anon, authenticated;
grant execute on function public.apply_payment(text, text, text, text) to service_role;

-- my_plan, consume_quota, admin_set_plan y admin_list_users usan el plan vigente.
create or replace function public.my_plan()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid();
  v_plan text := 'free';
  v_admin boolean := false;
  v_hasta timestamptz;
  v_mes text := public.chroma_month();
  v_trad integer := 0;
  v_looks integer := 0;
begin
  if v_uid is not null then
    v_plan := public.effective_plan(v_uid);
    select coalesce(up.is_admin, false), case when v_plan <> 'free' then up.plan_expires_at end
      into v_admin, v_hasta from public.user_plans up where up.user_id = v_uid;
    v_admin := coalesce(v_admin, false);
    select u.traductor, u.looks into v_trad, v_looks from public.usage_monthly u where u.user_id = v_uid and u.mes = v_mes;
  end if;
  return jsonb_build_object(
    'plan', v_plan,
    'nombre', initcap(v_plan),
    'mes', v_mes,
    'sesion', v_uid is not null,
    'is_admin', v_admin,
    'vence', v_hasta,
    'traductor', jsonb_build_object('usadas', coalesce(v_trad, 0), 'limite', public.plan_limit(v_plan, 'traductor')),
    'looks', jsonb_build_object('usados', coalesce(v_looks, 0), 'limite', public.plan_limit(v_plan, 'looks')),
    'marcas', coalesce((select jsonb_object_agg(b.marca, b.plan) from public.brand_plans b), '{}'::jsonb)
  );
end;
$$;

create or replace function public.consume_quota(p_tipo text)
returns jsonb language plpgsql volatile security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid();
  v_plan text;
  v_mes text := public.chroma_month();
  v_usado integer;
  v_limite integer;
begin
  if v_uid is null then
    raise sqlstate 'PT401' using message = 'Inicia sesión en la pestaña Cuenta para usar el traductor y el asesor.';
  end if;
  if p_tipo not in ('traductor', 'looks') then
    raise sqlstate 'PT400' using message = 'Tipo de consulta desconocido.';
  end if;
  v_plan := public.effective_plan(v_uid);
  v_limite := public.plan_limit(v_plan, p_tipo);
  insert into public.usage_monthly(user_id, mes) values (v_uid, v_mes) on conflict (user_id, mes) do nothing;
  select case p_tipo when 'traductor' then u.traductor else u.looks end into v_usado
    from public.usage_monthly u where u.user_id = v_uid and u.mes = v_mes for update;
  if v_usado >= v_limite then
    raise sqlstate 'PT429' using message = format('Ya usaste %s de tu plan %s este mes.%s',
      case p_tipo when 'traductor' then v_limite || ' consultas al traductor' else v_limite || ' looks' end,
      initcap(v_plan), case when v_plan = 'premium' then '' else ' Cambia a un plan superior para seguir.' end);
  end if;
  update public.usage_monthly u set
    traductor = u.traductor + (p_tipo = 'traductor')::int,
    looks = u.looks + (p_tipo = 'looks')::int
  where u.user_id = v_uid and u.mes = v_mes;
  return public.my_plan();
end;
$$;

-- Plan elegido por una administradora: no vence.
create or replace function public.admin_set_plan(p_user uuid, p_plan text, p_is_admin boolean default null)
returns void language plpgsql volatile security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  if p_plan not in ('free', 'plus', 'premium') then raise sqlstate 'PT400' using message = 'Plan inválido.'; end if;
  if p_user = auth.uid() and p_is_admin is false then
    raise sqlstate 'PT400' using message = 'No puedes quitarte a ti misma el rol de administradora.';
  end if;
  insert into public.user_plans(user_id, plan, is_admin, plan_expires_at, updated_at)
  values (p_user, p_plan, coalesce(p_is_admin, false), null, now())
  on conflict (user_id) do update set
    plan_expires_at = case when public.user_plans.plan = excluded.plan then public.user_plans.plan_expires_at end,
    plan = excluded.plan,
    is_admin = coalesce(p_is_admin, public.user_plans.is_admin), updated_at = now();
end;
$$;

-- La lista de usuarias muestra el plan vigente y cuándo vence.
create or replace function public.admin_list_users()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'user_id', u.id, 'email', u.email, 'nombre', p.display_name,
      'plan', public.effective_plan(u.id), 'vence', up.plan_expires_at, 'is_admin', coalesce(up.is_admin, false),
      'creada', u.created_at, 'ultimo_ingreso', u.last_sign_in_at,
      'tiene_test', exists (select 1 from public.colorimetry_results r where r.user_id = u.id),
      'pagos', (select count(*) from public.payments pay where pay.user_id = u.id and pay.status = 'APPROVED'),
      'traductor', coalesce(m.traductor, 0), 'looks', coalesce(m.looks, 0)) order by u.created_at desc)
    from auth.users u
    left join public.profiles p on p.user_id = u.id
    left join public.user_plans up on up.user_id = u.id
    left join public.usage_monthly m on m.user_id = u.id and m.mes = public.chroma_month()), '[]'::jsonb);
end;
$$;

revoke all on function public.my_plan(), public.consume_quota(text), public.admin_list_users(),
  public.admin_set_plan(uuid, text, boolean) from public, anon;
grant execute on function public.my_plan() to anon, authenticated;
grant execute on function public.consume_quota(text), public.admin_list_users(), public.admin_set_plan(uuid, text, boolean) to authenticated;
