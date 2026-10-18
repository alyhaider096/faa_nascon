-- Stateless JWTs carry this version. Privacy erasure increments it so every
-- token issued before erasure is rejected without retaining a token blacklist.
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version bigint NOT NULL DEFAULT 0;
