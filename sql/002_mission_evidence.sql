ALTER TABLE evidence_claims ADD COLUMN IF NOT EXISTS missions text[] NOT NULL DEFAULT '{}';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'boat_videos'::regclass
      AND contype = 'p'
      AND pg_get_constraintdef(oid) NOT LIKE '%video_type%'
  ) THEN
    ALTER TABLE boat_videos DROP CONSTRAINT boat_videos_pkey;
    ALTER TABLE boat_videos ADD PRIMARY KEY (boat_id, youtube_video_id, video_type);
  END IF;
END
$$;
