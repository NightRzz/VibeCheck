ALTER TABLE sentiments
    ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_sentiments_external_id'
    ) THEN
        ALTER TABLE sentiments
            ADD CONSTRAINT uq_sentiments_external_id UNIQUE (external_id);
    END IF;
END
$$;
