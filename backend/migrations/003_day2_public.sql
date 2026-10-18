-- Production-facing Day 2 state used by Ali's public and progressive-auth surfaces.
ALTER TABLE day2_match_state
    ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS day2_match_events (
    event_id text PRIMARY KEY,
    match_id text NOT NULL REFERENCES day2_match_state(match_id) ON DELETE CASCADE,
    request_hash text NOT NULL,
    sequence bigint NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (match_id, sequence)
);

CREATE TABLE IF NOT EXISTS day2_guest_cart_items (
    guest_token text NOT NULL REFERENCES day2_guest_tokens(guest_token) ON DELETE CASCADE,
    variant_id text NOT NULL REFERENCES variants(variant_id),
    quantity integer NOT NULL CHECK (quantity >= 1),
    PRIMARY KEY (guest_token, variant_id)
);

ALTER TABLE day2_moderation_messages
    ADD COLUMN IF NOT EXISTS sequence bigserial;
CREATE UNIQUE INDEX IF NOT EXISTS day2_chat_room_sequence
    ON day2_moderation_messages(chat_room_id, sequence);

CREATE TABLE IF NOT EXISTS day2_follows (
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (entity_type IN ('player', 'club')),
    entity_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, entity_type, entity_id)
);
