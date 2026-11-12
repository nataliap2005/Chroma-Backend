-- Borrador de migración: revisar con el equipo antes de ejecutar.
-- No toca las tablas de auth, perfiles ni resultados de Natalia.
create table if not exists public.catalog_products (
  id text primary key,
  nombre text not null,
  marca text not null,
  categoria text not null,
  tono text not null default '',
  color_hex text,
  precio_cop integer not null check (precio_cop >= 0),
  imagen text,
  tienda text,
  tienda_url text,
  subtono text,
  acabado text,
  calidad text,
  fuente text,
  updated_at timestamptz not null default now()
);
create index if not exists catalog_products_category_idx on public.catalog_products(categoria);
create index if not exists catalog_products_brand_idx on public.catalog_products(marca);
alter table public.catalog_products enable row level security;
-- Solo lectura pública. Escritura únicamente desde rol administrador en infraestructura segura.
create policy "catalogo_publico_lectura" on public.catalog_products
  for select to anon, authenticated using (true);
grant select on public.catalog_products to anon, authenticated;
revoke insert, update, delete on public.catalog_products from anon, authenticated;
