-- Run this ONCE after installing PostgreSQL locally:
-- psql -U postgres -f scripts/setup_local_postgres.sql

-- Create the project user (if not using postgres superuser)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pfa') THEN
        CREATE ROLE pfa WITH LOGIN PASSWORD 'pfa_local_2026';
    END IF;
END $$;

-- Create the database
SELECT 'CREATE DATABASE pfa_olist OWNER pfa'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'pfa_olist')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE pfa_olist TO pfa;

-- Connect to pfa_olist and run init-schemas.sql
\c pfa_olist

-- Allow pfa to create schemas
GRANT ALL ON SCHEMA public TO pfa;
ALTER USER pfa CREATEDB;

-- Now run the schema init
\i scripts/init-schemas.sql

-- Grant schema access
GRANT ALL ON SCHEMA bronze TO pfa;
GRANT ALL ON SCHEMA silver TO pfa;
GRANT ALL ON SCHEMA gold TO pfa;
GRANT ALL ON SCHEMA audit TO pfa;
GRANT ALL ON ALL TABLES IN SCHEMA bronze TO pfa;
GRANT ALL ON ALL TABLES IN SCHEMA silver TO pfa;
GRANT ALL ON ALL TABLES IN SCHEMA gold TO pfa;
GRANT ALL ON ALL TABLES IN SCHEMA audit TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA bronze GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO pfa;
