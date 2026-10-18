CREATE TABLE IF NOT EXISTS day2_vod_assets (
    vod_id text PRIMARY KEY,
    source_path text NOT NULL UNIQUE,
    object_key text NOT NULL UNIQUE,
    stream_path text NOT NULL,
    match_id text,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    etag text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS day2_vod_match_idx ON day2_vod_assets(match_id, created_at DESC);
