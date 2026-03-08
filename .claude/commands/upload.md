# /upload — Subir resultados de investigacion a Supabase

Sube todos los resultados de investigacion local a Supabase (DB + Storage).

## Uso
- `/upload` — sube todo (datos + archivos)
- `/upload --company "nombre"` — sube una empresa especifica
- `/upload --only-data` — solo actualiza la base de datos
- `/upload --only-files` — solo sube archivos a Storage

## Que hace
1. Lee `portal/data/companies.json` y `research/progress_100.json`
2. Fusiona los datos de investigacion con los registros de empresa
3. Hace upsert en la tabla `companies` de Supabase
4. Sube logos, fotos, briefs, JSONs y ZIPs a Supabase Storage bucket `packages`
5. Actualiza `package_ready`, `logo_available`, `photo_count` en DB

## Ejecucion
```bash
py scripts/upload_to_supabase.py $ARGS
```

Donde `$ARGS` son los argumentos opcionales del usuario.

## Despues del upload
El portal en GitLab Pages mostrara automaticamente los nuevos datos:
https://willymartetirado.gitlab.io/web-factory-portal
