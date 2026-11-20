# Migraciones de Supabase

Se ejecutan en **Supabase → SQL Editor → New query → pegar → Run**, en este orden. Cada archivo se puede volver a ejecutar sin dañar nada.

| Archivo | Qué crea |
|---|---|
| `001_perfiles_resultados.sql` | Tablas `profiles` y `colorimetry_results` con RLS, y el perfil automático al registrarse |
| `002_fotos_perfil.sql` | Columna `avatar_path` y bucket privado `avatars` para la foto de perfil |
| `003_favoritos_cosmetiquera_opiniones.sql` | Tablas `favorites`, `vanity` y `tone_feedback` con RLS, y la función `alpha_panel_data()` del panel de resultados |
| `004_planes_cuotas_admin.sql` | Planes Free, Plus y Premium: plan de cada usuaria, marcas por plan, cuotas del mes y funciones de administración |
| `005_catalogo_pagos.sql` | Tabla `catalog_products` administrable, bucket público `product-images`, opiniones para administradoras, tabla `payments` y vencimiento del plan pagado (30 días) |
| `006_catalogo_inicial.sql` | Carga los 688 productos iniciales en `catalog_products` (solo agrega los que falten) |
| `007_opiniones_looks.sql` | Tabla `look_feedback` (opinión sobre los looks del asesor: si le gusta, si lo usaría y un comentario) y la función `admin_list_look_feedback()` |

`006_catalogo_inicial.sql` se genera desde `data/productos_mvp.csv`:

```bash
python scripts/export_catalog_sql.py
```

Después de cargarlo, el catálogo se administra desde la app (Cuenta → Administración → Productos) y el CSV queda como respaldo para desarrollo.

## Primera administradora

Después de la `004`, con el correo de una cuenta ya registrada en la app:

```sql
insert into public.user_plans(user_id, is_admin)
select id, true from auth.users where email = 'CORREO_DE_LA_ADMIN'
on conflict (user_id) do update set is_admin = true;
```

Las demás administradoras se nombran desde la app: Cuenta → Administración → Usuarias.

## Permisos

| Quién | Qué puede hacer |
|---|---|
| Cualquiera (sin sesión) | Leer productos activos y el plan de cada marca |
| Usuaria con sesión | Ver y cambiar solo sus datos: perfil, test, favoritos, cosmetiquera, opiniones; leer su plan y sus pagos |
| Administradora | Lo anterior, más: cambiar planes, nombrar administradoras, crear, editar u ocultar productos, subir fotos y leer las opiniones sobre tonos y looks |
| Servidor (`service_role`) | Registrar y confirmar pagos (función `apply_payment`) |

Nadie cambia su propio plan ni su uso del mes desde la app: solo las funciones de la base de datos, que verifican quién llama.
