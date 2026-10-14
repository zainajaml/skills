-- Lists application database objects as sorted `kind|name|definition` lines so a
-- source and a target database can be diffed for schema-coverage.md.
--
-- Usage (read-only; never prints row data or secrets):
--   psql "$SOURCE_DATABASE_URL" -X -f schema-catalog.sql > /tmp/source-catalog.txt
--   psql "$TARGET_DATABASE_URL" -X -f schema-catalog.sql > /tmp/target-catalog.txt
--   diff /tmp/source-catalog.txt /tmp/target-catalog.txt
--
-- On Lovable Cloud there is no direct connection: restore the database export into a
-- scratch local PostgreSQL first and run this against that.
--
-- Supabase-managed schemas (auth, storage, realtime, vault, ...) and objects owned by
-- extensions are skipped, except user triggers on auth.users, which must be replaced.
-- Function and view bodies are compared by md5; inspect the source when they differ.
-- Expected differences (Supabase default extensions, retired objects, objects moved
-- to backend code) are explained in schema-coverage.md, not hidden.

\set ON_ERROR_STOP on
\pset footer off
\pset tuples_only on
\pset format unaligned
\pset fieldsep '|'

WITH ns AS (
  SELECT oid, nspname
  FROM pg_namespace
  WHERE nspname NOT IN (
      'pg_catalog', 'information_schema', 'pg_toast', 'auth', 'storage', 'realtime',
      '_realtime', 'extensions', 'graphql', 'graphql_public', 'vault', 'pgsodium',
      'pgsodium_masks', 'net', 'cron', 'pgbouncer', 'pgmq', '_analytics',
      'supabase_functions', 'supabase_migrations')
    AND nspname NOT LIKE 'pg\_temp%'
    AND nspname NOT LIKE 'pg\_toast\_temp%'
    AND nspname NOT LIKE 'supabase\_%'
),
ext_owned AS (
  SELECT classid, objid FROM pg_depend WHERE deptype = 'e'
)
SELECT kind, name, definition FROM (
  -- tables, views, materialized views, sequences, foreign tables
  SELECT CASE c.relkind
           WHEN 'r' THEN 'table' WHEN 'p' THEN 'table' WHEN 'v' THEN 'view'
           WHEN 'm' THEN 'materialized view' WHEN 'S' THEN 'sequence'
           WHEN 'f' THEN 'foreign table'
         END AS kind,
         n.nspname || '.' || c.relname AS name,
         CASE WHEN c.relkind IN ('v', 'm') THEN md5(pg_get_viewdef(c.oid)) ELSE '' END AS definition
  FROM pg_class c
  JOIN ns n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
    AND NOT EXISTS (SELECT 1 FROM ext_owned e WHERE e.classid = 'pg_class'::regclass AND e.objid = c.oid)

  UNION ALL
  -- columns with type, nullability, default, identity and generated flags
  SELECT 'column',
         n.nspname || '.' || c.relname || '.' || a.attname,
         format_type(a.atttypid, a.atttypmod)
           || CASE WHEN a.attnotnull THEN ' not null' ELSE '' END
           || coalesce(' default ' || pg_get_expr(d.adbin, d.adrelid), '')
           || CASE WHEN a.attidentity <> '' THEN ' identity ' || a.attidentity ELSE '' END
           || CASE WHEN a.attgenerated <> '' THEN ' generated' ELSE '' END
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN ns n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
    AND NOT EXISTS (SELECT 1 FROM ext_owned e WHERE e.classid = 'pg_class'::regclass AND e.objid = c.oid)

  UNION ALL
  -- primary key, foreign key, unique, check and exclusion constraints
  SELECT 'constraint',
         n.nspname || '.' || c.relname || '.' || co.conname,
         pg_get_constraintdef(co.oid)
  FROM pg_constraint co
  JOIN pg_class c ON c.oid = co.conrelid
  JOIN ns n ON n.oid = c.relnamespace

  UNION ALL
  -- indexes, including partial and expression indexes
  SELECT 'index',
         n.nspname || '.' || t.relname || '.' || i.relname,
         pg_get_indexdef(i.oid)
  FROM pg_index x
  JOIN pg_class i ON i.oid = x.indexrelid
  JOIN pg_class t ON t.oid = x.indrelid
  JOIN ns n ON n.oid = t.relnamespace
  WHERE NOT EXISTS (SELECT 1 FROM ext_owned e WHERE e.classid = 'pg_class'::regclass AND e.objid = t.oid)

  UNION ALL
  -- functions and procedures
  SELECT CASE p.prokind WHEN 'p' THEN 'procedure' ELSE 'function' END,
         n.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')',
         md5(pg_get_functiondef(p.oid))
  FROM pg_proc p
  JOIN ns n ON n.oid = p.pronamespace
  WHERE p.prokind IN ('f', 'p')
    AND NOT EXISTS (SELECT 1 FROM ext_owned e WHERE e.classid = 'pg_proc'::regclass AND e.objid = p.oid)

  UNION ALL
  -- user triggers on application tables and on auth.users
  SELECT 'trigger',
         tn.nspname || '.' || c.relname || '.' || t.tgname,
         pg_get_triggerdef(t.oid)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace tn ON tn.oid = c.relnamespace
  WHERE NOT t.tgisinternal
    AND (tn.oid IN (SELECT oid FROM ns) OR (tn.nspname = 'auth' AND c.relname = 'users'))

  UNION ALL
  -- enums, domains and standalone composite types
  SELECT CASE t.typtype WHEN 'e' THEN 'enum' WHEN 'd' THEN 'domain' ELSE 'composite type' END,
         n.nspname || '.' || t.typname,
         CASE t.typtype
           WHEN 'e' THEN (SELECT string_agg(enumlabel::text, ',' ORDER BY enumsortorder)
                          FROM pg_enum WHERE enumtypid = t.oid)
           WHEN 'd' THEN format_type(t.typbasetype, t.typtypmod)
           ELSE ''
         END
  FROM pg_type t
  JOIN ns n ON n.oid = t.typnamespace
  WHERE (t.typtype IN ('e', 'd')
         OR (t.typtype = 'c' AND (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c'))
    AND NOT EXISTS (SELECT 1 FROM ext_owned e WHERE e.classid = 'pg_type'::regclass AND e.objid = t.oid)

  UNION ALL
  -- installed extensions (versions omitted to keep the diff about presence)
  SELECT 'extension', extname::text, ''
  FROM pg_extension
  WHERE extname <> 'plpgsql'

  UNION ALL
  -- RLS policies and tables with RLS enabled
  SELECT 'policy',
         schemaname || '.' || tablename || '.' || policyname,
         permissive || ' ' || cmd || ' to ' || array_to_string(roles, ',')
           || ' using ' || coalesce(qual, '') || ' check ' || coalesce(with_check, '')
  FROM pg_policies
  WHERE schemaname IN (SELECT nspname FROM ns)

  UNION ALL
  SELECT 'rls enabled', n.nspname || '.' || c.relname, ''
  FROM pg_class c
  JOIN ns n ON n.oid = c.relnamespace
  WHERE c.relrowsecurity
) catalog
ORDER BY kind, name;

-- pg_cron jobs, only when the extension is installed
SELECT to_regclass('cron.job') IS NOT NULL AS has_cron \gset
\if :has_cron
SELECT 'cron job', coalesce(jobname, jobid::text), schedule || ' ' || command
FROM cron.job
ORDER BY 2;
\endif
