# Migraciones de Supabase

Se ejecutan en **Supabase → SQL Editor**, en este orden. Cada archivo se puede volver a ejecutar sin dañar nada.

| Archivo | Qué crea | Estado |
|---|---|---|
| `001_natalia_profiles_results.sql` | Tablas `profiles` y `colorimetry_results`, con RLS, y el perfil automático al registrarse | Ejecutada |
| `002_natalia_avatars.sql` | Columna `avatar_path` y bucket privado `avatars` para la foto de perfil | Ejecutada |
| `003_alfa_favoritos_cosmetiquera_opiniones.sql` | Tablas `favorites`, `vanity` y `tone_feedback`, con RLS, y la función `alpha_panel_data()` del panel del alfa | Ejecutada |
| `005_planes_cuotas_admin.sql` | Planes Free, Plus y Premium: plan de cada usuaria, marcas por plan, cuotas del mes y funciones de administración | **Falta ejecutar** |
| `004_catalog_products_borrador.sql` | Tabla del catálogo en Supabase | Borrador: no ejecutar todavía (el catálogo se lee del CSV del backend) |

Al ejecutar una migración nueva, actualiza la columna Estado.

## Primera administradora

Después de la 005, en el SQL Editor (cambia el correo por el de la cuenta):

```sql
insert into public.user_plans(user_id, is_admin)
select id, true from auth.users where email = 'CORREO_DE_LA_ADMIN'
on conflict (user_id) do update set is_admin = true;
```

Desde ahí, las demás administradoras se nombran en la app: Cuenta → Administración.
