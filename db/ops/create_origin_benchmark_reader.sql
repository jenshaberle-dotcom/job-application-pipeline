\set ON_ERROR_STOP on

\if :{?database_name}
\else
  \echo 'Missing psql variable database_name.'
  \quit 2
\endif

\prompt 'New password for origin_benchmark_reader: ' origin_benchmark_password

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'origin_benchmark_reader'
    ) THEN
        CREATE ROLE origin_benchmark_reader LOGIN NOINHERIT;
    END IF;
END
$$;

ALTER ROLE origin_benchmark_reader
    WITH LOGIN
    PASSWORD :'origin_benchmark_password';

ALTER ROLE origin_benchmark_reader SET default_transaction_read_only = 'on';
ALTER ROLE origin_benchmark_reader SET statement_timeout = '5min';
ALTER ROLE origin_benchmark_reader SET idle_in_transaction_session_timeout = '1min';

GRANT CONNECT ON DATABASE :"database_name" TO origin_benchmark_reader;
GRANT USAGE ON SCHEMA public TO origin_benchmark_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM origin_benchmark_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM origin_benchmark_reader;

GRANT SELECT ON TABLE
    employer_origin_source_candidates,
    market_evidence
TO origin_benchmark_reader;

\echo 'origin_benchmark_reader configured with read-only access to two tables.'
