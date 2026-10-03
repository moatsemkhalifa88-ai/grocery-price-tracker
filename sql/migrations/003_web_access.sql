-- 003 — read-only role for the public web dashboard.
-- The Next.js app connects (server-side only) as web_reader and can read ONLY
-- the dbt marts. Give it a password once, by hand:
--     ALTER ROLE web_reader WITH LOGIN PASSWORD '<strong password>';

CREATE SCHEMA IF NOT EXISTS marts;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_reader') THEN
        CREATE ROLE web_reader NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA marts, analytics TO web_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA marts, analytics TO web_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO web_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO web_reader;
REVOKE ALL ON SCHEMA core, ingest FROM web_reader;
ALTER ROLE web_reader SET statement_timeout = '8s';
