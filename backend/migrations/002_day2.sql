-- Phase II platform state. PostgreSQL constraints are the concurrency boundary for replay safety.
CREATE TABLE IF NOT EXISTS day2_stream_keys (
    stream_key text PRIMARY KEY,
    player_id text NOT NULL REFERENCES ref_players(player_id),
    label text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'revoked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS day2_one_active_stream_key
    ON day2_stream_keys(player_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS day2_costream_sessions (
    session_id text PRIMARY KEY,
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS day2_qr_mappings (
    entity_id text PRIMARY KEY,
    entity_type text NOT NULL,
    short_code text NOT NULL UNIQUE,
    scan_count bigint NOT NULL DEFAULT 0 CHECK (scan_count >= 0)
);

CREATE TABLE IF NOT EXISTS day2_qr_scan_buckets (
    entity_id text NOT NULL REFERENCES day2_qr_mappings(entity_id) ON DELETE CASCADE,
    device_family text NOT NULL CHECK (device_family IN ('mobile', 'desktop')),
    utc_bucket timestamptz NOT NULL,
    scans bigint NOT NULL DEFAULT 0 CHECK (scans >= 0),
    PRIMARY KEY (entity_id, device_family, utc_bucket)
);

CREATE TABLE IF NOT EXISTS day2_guest_tokens (
    guest_token text PRIMARY KEY,
    user_id text,
    valid boolean NOT NULL DEFAULT true,
    merged boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS day2_carts (
    user_id text PRIMARY KEY,
    currency text NOT NULL DEFAULT 'PKR'
);

CREATE TABLE IF NOT EXISTS day2_cart_items (
    user_id text NOT NULL REFERENCES day2_carts(user_id) ON DELETE CASCADE,
    variant_id text NOT NULL REFERENCES variants(variant_id),
    quantity integer NOT NULL CHECK (quantity >= 1),
    PRIMARY KEY (user_id, variant_id)
);

CREATE TABLE IF NOT EXISTS day2_merge_receipts (
    guest_token text PRIMARY KEY REFERENCES day2_guest_tokens(guest_token),
    registered_user_id text NOT NULL,
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS day2_moderation_messages (
    chat_room_id text NOT NULL,
    message_id text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_room_id, message_id)
);

CREATE TABLE IF NOT EXISTS day2_sanctions (
    chat_room_id text NOT NULL,
    user_id text NOT NULL,
    sanction text NOT NULL CHECK (sanction IN ('kicked', 'muted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_room_id, user_id, sanction)
);

CREATE TABLE IF NOT EXISTS day2_dlq (
    id bigserial PRIMARY KEY,
    event jsonb NOT NULL,
    attempts integer NOT NULL DEFAULT 3,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS day2_match_state (
    match_id text PRIMARY KEY,
    status text NOT NULL,
    score_home integer NOT NULL DEFAULT 0,
    score_away integer NOT NULL DEFAULT 0
);
