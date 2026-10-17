-- PostgreSQL 16 schema fragment. Host owns migration ordering and reset.
CREATE TABLE IF NOT EXISTS domain_sports (
    id VARCHAR(64) PRIMARY KEY, config JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_leagues (
    id VARCHAR(64) PRIMARY KEY,
    sport_id VARCHAR(64) NOT NULL REFERENCES domain_sports(id), config JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_matches (
    id VARCHAR(64) PRIMARY KEY,
    sport_id VARCHAR(64) NOT NULL REFERENCES domain_sports(id),
    league_id VARCHAR(64) REFERENCES domain_leagues(id),
    home VARCHAR(64) NOT NULL, away VARCHAR(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_events (
    id VARCHAR(64) PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL REFERENCES domain_matches(id),
    sequence INTEGER NOT NULL, type VARCHAR(32) NOT NULL,
    payload JSON NOT NULL, request JSON NOT NULL, signature VARCHAR(64) NOT NULL,
    UNIQUE(match_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_domain_events_match_id ON domain_events(match_id);
CREATE TABLE IF NOT EXISTS domain_settings (id VARCHAR(64) PRIMARY KEY, value JSON NOT NULL);
CREATE TABLE IF NOT EXISTS domain_outbox (id VARCHAR(64) PRIMARY KEY, payload JSON NOT NULL);
CREATE TABLE IF NOT EXISTS domain_competitions (
    id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, config JSON NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_domain_competitions_tenant_id ON domain_competitions(tenant_id);
CREATE TABLE IF NOT EXISTS domain_scheduled_matches (
    id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, config JSON NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_domain_scheduled_matches_tenant_id ON domain_scheduled_matches(tenant_id);
