-- Runs once on first initialization of the Postgres data directory.
-- Enables the pgvector extension so embedding columns are available to the app.
CREATE EXTENSION IF NOT EXISTS vector;
