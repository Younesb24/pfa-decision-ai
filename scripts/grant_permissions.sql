-- Run this as postgres superuser in pgAdmin Query Tool on pfa_olist database
-- Grants all permissions to pfa user on all schemas

GRANT ALL ON SCHEMA bronze TO pfa;
GRANT ALL ON SCHEMA silver TO pfa;
GRANT ALL ON SCHEMA gold TO pfa;
GRANT ALL ON SCHEMA audit TO pfa;
GRANT ALL ON SCHEMA public TO pfa;

-- Allow pfa to create tables in these schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA bronze GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA silver GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT ALL ON TABLES TO pfa;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO pfa;

-- Also make pfa own these schemas (simplest fix)
ALTER SCHEMA bronze OWNER TO pfa;
ALTER SCHEMA silver OWNER TO pfa;
ALTER SCHEMA gold OWNER TO pfa;
ALTER SCHEMA audit OWNER TO pfa;
