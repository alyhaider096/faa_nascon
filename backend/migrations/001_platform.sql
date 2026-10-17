-- Platform migration (Abdullah). Domain migrations from the scoring/standings owner are
-- added as 1xx_*.sql fragments and assembled here in filename order.

CREATE TABLE IF NOT EXISTS seed_state (
    id          integer PRIMARY KEY CHECK (id = 1),
    seed        integer NOT NULL,
    epoch       bigint  NOT NULL DEFAULT 1,
    seeded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   text PRIMARY KEY,
    name        text NOT NULL,
    branding    jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS users (
    user_id        text PRIMARY KEY,
    email          text NOT NULL UNIQUE,
    password_hash  text NOT NULL,
    role           text NOT NULL,
    display_name   text NOT NULL,
    tenant_id      text REFERENCES tenants(tenant_id),
    league_id      text,
    club_id        text,
    player_id      text
);

CREATE TABLE IF NOT EXISTS ref_leagues (
    league_id   text PRIMARY KEY,
    tenant_id   text NOT NULL REFERENCES tenants(tenant_id),
    name        text NOT NULL,
    sport_id    text
);

CREATE TABLE IF NOT EXISTS ref_clubs (
    club_id     text PRIMARY KEY,
    tenant_id   text NOT NULL REFERENCES tenants(tenant_id),
    name        text NOT NULL,
    venue       jsonb NOT NULL DEFAULT '{}'::jsonb,
    social      jsonb NOT NULL DEFAULT '{}'::jsonb,
    staff       jsonb NOT NULL DEFAULT '[]'::jsonb,
    history     jsonb NOT NULL DEFAULT '[]'::jsonb,
    branding    jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ref_players (
    player_id   text PRIMARY KEY,
    club_id     text NOT NULL REFERENCES ref_clubs(club_id),
    tenant_id   text NOT NULL REFERENCES tenants(tenant_id),
    name        text NOT NULL
);

-- Shared sport configuration table (same schema as POST /audit/v1/sports). The sports owner
-- creates mystery sports into this table; roster defaults read roster config from it.
CREATE TABLE IF NOT EXISTS sports (
    sport_id    text PRIMARY KEY,
    name        text NOT NULL,
    config      jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Store ---------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id  text PRIMARY KEY,
    tenant_id   text NOT NULL REFERENCES tenants(tenant_id),
    club_id     text,
    name        text NOT NULL,
    category    text NOT NULL DEFAULT 'apparel',
    description text NOT NULL DEFAULT '',
    active      boolean NOT NULL DEFAULT true,
    pinned_match_id text
);

CREATE TABLE IF NOT EXISTS variants (
    variant_id   text PRIMARY KEY,
    product_id   text NOT NULL REFERENCES products(product_id),
    attributes   jsonb NOT NULL DEFAULT '{}'::jsonb,
    price_minor  bigint NOT NULL CHECK (price_minor >= 0),
    currency     text NOT NULL DEFAULT 'PKR',
    stock        integer NOT NULL CHECK (stock >= 0),
    reserved     integer NOT NULL DEFAULT 0 CHECK (reserved >= 0)
);

CREATE TABLE IF NOT EXISTS price_schedule (
    id           bigserial PRIMARY KEY,
    variant_id   text NOT NULL REFERENCES variants(variant_id),
    effective_at timestamptz NOT NULL,
    price_minor  bigint NOT NULL CHECK (price_minor >= 0)
);

CREATE TABLE IF NOT EXISTS discount_codes (
    code     text PRIMARY KEY,
    percent  integer NOT NULL CHECK (percent BETWEEN 0 AND 100),
    active   boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS orders (
    order_id       text PRIMARY KEY,
    customer_id    text NOT NULL,
    request_hash   text NOT NULL,
    status         text NOT NULL,
    currency       text NOT NULL DEFAULT 'PKR',
    subtotal_minor bigint NOT NULL,
    discount_minor bigint NOT NULL,
    total_minor    bigint NOT NULL,
    response       jsonb NOT NULL,
    pdf            bytea,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id         text NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    variant_id       text NOT NULL,
    quantity         integer NOT NULL,
    unit_price_minor bigint NOT NULL,
    PRIMARY KEY (order_id, variant_id)
);

CREATE SEQUENCE IF NOT EXISTS payment_seq START 1;

-- Transactional outbox: domain events are written in the same transaction as the change and
-- published to the internal queue (Redis Streams) by the worker only after commit.
CREATE TABLE IF NOT EXISTS outbox (
    id           bigserial PRIMARY KEY,
    topic        text NOT NULL,
    payload      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX IF NOT EXISTS outbox_unpublished_idx ON outbox (id) WHERE published_at IS NULL;

-- Roster --------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roster_leagues (
    league_id          text PRIMARY KEY,
    tenant_id          text NOT NULL,
    sport_id           text NOT NULL,
    window_open        date,
    window_close       date,
    max_squad_size     integer NOT NULL,
    required_positions jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS roster_squads (
    squad_id   text PRIMARY KEY,
    league_id  text NOT NULL,
    club_id    text NOT NULL,
    tenant_id  text NOT NULL,
    name       text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS roster_squads_league_idx ON roster_squads (league_id);

CREATE TABLE IF NOT EXISTS roster_players (
    player_id         text PRIMARY KEY,
    league_id         text NOT NULL,
    name              text NOT NULL DEFAULT '',
    position          text NOT NULL,
    initial_squad_id  text,
    initial_role      text,
    squad_id          text,
    parent_squad_id   text,
    registration_type text,
    start_date        date,
    loan_end_date     date,
    role              text
);
CREATE INDEX IF NOT EXISTS roster_players_league_idx ON roster_players (league_id);
CREATE INDEX IF NOT EXISTS roster_players_squad_idx ON roster_players (squad_id);

CREATE TABLE IF NOT EXISTS roster_matches (
    match_id       text PRIMARY KEY,
    league_id      text NOT NULL,
    home_squad_id  text NOT NULL,
    away_squad_id  text NOT NULL,
    position       integer NOT NULL DEFAULT 0
);

CREATE SEQUENCE IF NOT EXISTS roster_audit_seq START 1;

CREATE TABLE IF NOT EXISTS roster_audit (
    seq            bigint PRIMARY KEY,
    audit_id       text NOT NULL UNIQUE,
    player_id      text NOT NULL,
    league_id      text NOT NULL,
    action         text NOT NULL,
    from_squad_id  text,
    to_squad_id    text,
    effective_date date NOT NULL,
    state          text NOT NULL,
    who            text NOT NULL,
    "when"         text NOT NULL,
    why            text NOT NULL
);
CREATE INDEX IF NOT EXISTS roster_audit_player_idx ON roster_audit (player_id, seq);

CREATE TABLE IF NOT EXISTS roster_requests (
    request_id  text PRIMARY KEY,
    league_id   text NOT NULL,
    body_hash   text NOT NULL,
    response    jsonb NOT NULL
);

-- Offline sync --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS offline_actions (
    device_id      text NOT NULL,
    action_id      text NOT NULL,
    action_type    text NOT NULL,
    result         jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, action_id)
);
