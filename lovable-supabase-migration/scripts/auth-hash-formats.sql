-- Counts Supabase Auth users per password hash format. Prints only the format name
-- and a count, never hash values.
--
-- Usage (read-only):
--   psql "$SOURCE_DATABASE_URL" -X -f auth-hash-formats.sql
--
-- On Lovable Cloud, run it against a scratch local PostgreSQL restored from the
-- database export. Treat that export as a secret and delete the scratch database after.
-- Confirm the target auth library can verify every format listed (see data-security.md).

\set ON_ERROR_STOP on

SELECT
  CASE
    WHEN encrypted_password IS NULL OR encrypted_password = '' THEN 'none (OAuth, magic link or OTP only)'
    WHEN encrypted_password ~ '^\$2[aby]\$' THEN 'bcrypt'
    WHEN encrypted_password LIKE '$argon2id$%' THEN 'argon2id'
    WHEN encrypted_password LIKE '$argon2i$%' THEN 'argon2i'
    WHEN encrypted_password LIKE '$fbscrypt$%' THEN 'firebase scrypt'
    ELSE 'other: $' || split_part(encrypted_password, '$', 2) || '$'
  END AS hash_format,
  count(*) AS users
FROM auth.users
GROUP BY 1
ORDER BY 2 DESC;
