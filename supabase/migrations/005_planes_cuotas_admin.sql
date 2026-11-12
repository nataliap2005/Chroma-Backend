-- Planes Free, Plus y Premium: marcas por plan, cuotas mensuales y administración.
-- Ejecutar una vez en Supabase: SQL Editor → pegar este archivo → Run (se puede repetir sin dañar nada).
-- Cuotas por mes (hoja 05 PLANES del modelo financiero):
--   Free: 10 consultas al traductor y 4 looks · Plus: 100 y 60 · Premium: 300 y 180.
-- Marcas: Free = Vogue, Maybelline, L'Oréal Paris, Max Factor y Clinique; Plus suma Essence; Premium suma Estée Lauder.
--
-- Primera administradora (una sola vez, con el correo de la cuenta):
--   insert into public.user_plans(user_id, is_admin)
--   select id, true from auth.users where email = 'CORREO_DE_LA_ADMIN'
--   on conflict (user_id) do update set is_admin = true;

-- Plan de cada usuaria (sin fila = Free). Solo lo cambia una administradora.
create table if not exists public.user_plans (
  user_id uuid primary key references auth.users(id) on delete cascade,
  plan text not null default 'free' check (plan in ('free', 'plus', 'premium')),
  is_admin boolean not null default false,
  updated_at timestamptz not null default now()
);

-- Uso del mes (mes de Colombia, 'AAAA-MM')
create table if not exists public.usage_monthly (
  user_id uuid not null references auth.users(id) on delete cascade,
  mes text not null check (mes ~ '^[0-9]{4}-[0-9]{2}$'),
  traductor integer not null default 0,
  looks integer not null default 0,
  primary key (user_id, mes)
);

-- Plan desde el que se ve cada marca (marca sin fila = Free)
create table if not exists public.brand_plans (
  marca text primary key,
  plan text not null check (plan in ('free', 'plus', 'premium'))
);
insert into public.brand_plans(marca, plan) values ('Essence', 'plus'), ('Estée Lauder', 'premium')
on conflict (marca) do nothing;

alter table public.user_plans enable row level security;
alter table public.usage_monthly enable row level security;
alter table public.brand_plans enable row level security;

drop policy if exists "plan_propio" on public.user_plans;
create policy "plan_propio" on public.user_plans for select to authenticated using (user_id = auth.uid());
drop policy if exists "uso_propio" on public.usage_monthly;
create policy "uso_propio" on public.usage_monthly for select to authenticated using (user_id = auth.uid());
drop policy if exists "marcas_publicas" on public.brand_plans;
create policy "marcas_publicas" on public.brand_plans for select to anon, authenticated using (true);

-- Nadie cambia su plan ni su uso desde la app: solo las funciones de abajo.
revoke all on public.user_plans, public.usage_monthly, public.brand_plans from anon, authenticated;
grant select on public.user_plans, public.usage_monthly to authenticated;
grant select on public.brand_plans to anon, authenticated;

create or replace function public.plan_limit(p_plan text, p_tipo text)
returns integer language sql immutable set search_path = public, pg_temp as $$
  select case p_plan
    when 'premium' then case p_tipo when 'traductor' then 300 else 180 end
    when 'plus' then case p_tipo when 'traductor' then 100 else 60 end
    else case p_tipo when 'traductor' then 10 else 4 end
  end;
$$;

create or replace function public.chroma_month() returns text language sql stable as $$
  select to_char(now() at time zone 'America/Bogota', 'YYYY-MM');
$$;

-- Plan, uso del mes y marcas por plan de quien llama (sin sesión: Free, sin uso).
create or replace function public.my_plan()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid();
  v_plan text := 'free';
  v_admin boolean := false;
  v_mes text := public.chroma_month();
  v_trad integer := 0;
  v_looks integer := 0;
begin
  if v_uid is not null then
    select coalesce(up.plan, 'free'), coalesce(up.is_admin, false) into v_plan, v_admin
      from public.user_plans up where up.user_id = v_uid;
    v_plan := coalesce(v_plan, 'free'); v_admin := coalesce(v_admin, false);
    select u.traductor, u.looks into v_trad, v_looks from public.usage_monthly u where u.user_id = v_uid and u.mes = v_mes;
  end if;
  return jsonb_build_object(
    'plan', v_plan,
    'nombre', initcap(v_plan),
    'mes', v_mes,
    'sesion', v_uid is not null,
    'is_admin', v_admin,
    'traductor', jsonb_build_object('usadas', coalesce(v_trad, 0), 'limite', public.plan_limit(v_plan, 'traductor')),
    'looks', jsonb_build_object('usados', coalesce(v_looks, 0), 'limite', public.plan_limit(v_plan, 'looks')),
    'marcas', coalesce((select jsonb_object_agg(b.marca, b.plan) from public.brand_plans b), '{}'::jsonb)
  );
end;
$$;

-- Gasta una consulta del traductor o un look. Si no quedan, falla con estado HTTP 429.
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
  select up.plan into v_plan from public.user_plans up where up.user_id = v_uid;
  v_plan := coalesce(v_plan, 'free');
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

-- Administración ---------------------------------------------------------------
create or replace function public.is_chroma_admin()
returns boolean language sql stable security definer set search_path = public, pg_temp as $$
  select coalesce((select up.is_admin from public.user_plans up where up.user_id = auth.uid()), false);
$$;

create or replace function public.admin_list_users()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'user_id', u.id, 'email', u.email, 'nombre', p.display_name,
      'plan', coalesce(up.plan, 'free'), 'is_admin', coalesce(up.is_admin, false),
      'creada', u.created_at, 'ultimo_ingreso', u.last_sign_in_at,
      'tiene_test', exists (select 1 from public.colorimetry_results r where r.user_id = u.id),
      'traductor', coalesce(m.traductor, 0), 'looks', coalesce(m.looks, 0)) order by u.created_at desc)
    from auth.users u
    left join public.profiles p on p.user_id = u.id
    left join public.user_plans up on up.user_id = u.id
    left join public.usage_monthly m on m.user_id = u.id and m.mes = public.chroma_month()), '[]'::jsonb);
end;
$$;

create or replace function public.admin_set_plan(p_user uuid, p_plan text, p_is_admin boolean default null)
returns void language plpgsql volatile security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  if p_plan not in ('free', 'plus', 'premium') then raise sqlstate 'PT400' using message = 'Plan inválido.'; end if;
  if p_user = auth.uid() and p_is_admin is false then
    raise sqlstate 'PT400' using message = 'No puedes quitarte a ti misma el rol de administradora.';
  end if;
  insert into public.user_plans(user_id, plan, is_admin, updated_at)
  values (p_user, p_plan, coalesce(p_is_admin, false), now())
  on conflict (user_id) do update set plan = excluded.plan,
    is_admin = coalesce(p_is_admin, public.user_plans.is_admin), updated_at = now();
end;
$$;

create or replace function public.admin_set_brand_plan(p_marca text, p_plan text)
returns void language plpgsql volatile security definer set search_path = public, pg_temp as $$
begin
  if not public.is_chroma_admin() then raise sqlstate 'PT403' using message = 'Solo para administradoras.'; end if;
  if p_plan not in ('free', 'plus', 'premium') then raise sqlstate 'PT400' using message = 'Plan inválido.'; end if;
  insert into public.brand_plans(marca, plan) values (p_marca, p_plan)
  on conflict (marca) do update set plan = excluded.plan;
end;
$$;

revoke all on function public.my_plan(), public.consume_quota(text), public.is_chroma_admin(), public.admin_list_users(),
  public.admin_set_plan(uuid, text, boolean), public.admin_set_brand_plan(text, text) from public, anon;
grant execute on function public.my_plan() to anon, authenticated;
grant execute on function public.consume_quota(text), public.is_chroma_admin(), public.admin_list_users(),
  public.admin_set_plan(uuid, text, boolean), public.admin_set_brand_plan(text, text) to authenticated;
