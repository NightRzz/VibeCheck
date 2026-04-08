CREATE TABLE IF NOT EXISTS tracked_videos (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(32) NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE sentiments
    ADD COLUMN IF NOT EXISTS video_id VARCHAR(32);

ALTER TABLE sentiments
    ADD COLUMN IF NOT EXISTS author VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_sentiments_video_id
    ON sentiments (video_id);

CREATE INDEX IF NOT EXISTS ix_tracked_videos_video_id
    ON tracked_videos (video_id);

CREATE INDEX IF NOT EXISTS ix_tracked_videos_is_active
    ON tracked_videos (is_active);
