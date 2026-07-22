CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status text NOT NULL DEFAULT 'running',
  discovered_count integer NOT NULL DEFAULT 0,
  imported_count integer NOT NULL DEFAULT 0,
  failed_count integer NOT NULL DEFAULT 0,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS source_playlists (
  youtube_playlist_id text PRIMARY KEY,
  title text NOT NULL,
  video_type text NOT NULL CHECK (video_type IN ('walkthrough', 'test_drive')),
  source_url text NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_videos (
  youtube_video_id text PRIMARY KEY,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  youtube_url text NOT NULL,
  thumbnail_url text,
  duration_seconds integer,
  published_at timestamptz,
  location_text text,
  recording_country_code char(2),
  view_count bigint,
  like_count bigint,
  comment_count bigint,
  make text,
  model text,
  full_name text,
  length_feet numeric(6,2),
  identity_confidence numeric(4,3),
  identity_method text,
  identity_review_status text NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT make_model_together CHECK ((make IS NULL AND model IS NULL) OR (make IS NOT NULL AND model IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS playlist_videos (
  youtube_playlist_id text NOT NULL REFERENCES source_playlists(youtube_playlist_id) ON DELETE CASCADE,
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  playlist_position integer NOT NULL,
  PRIMARY KEY (youtube_playlist_id, youtube_video_id)
);

CREATE TABLE IF NOT EXISTS video_metric_snapshots (
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  captured_at timestamptz NOT NULL DEFAULT now(),
  view_count bigint,
  like_count bigint,
  comment_count bigint,
  PRIMARY KEY (youtube_video_id, captured_at)
);

CREATE TABLE IF NOT EXISTS video_transcripts (
  youtube_video_id text PRIMARY KEY REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  language text NOT NULL,
  source text NOT NULL,
  is_generated boolean NOT NULL DEFAULT true,
  full_text text NOT NULL,
  checksum text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', full_text)) STORED
);

CREATE INDEX IF NOT EXISTS video_transcripts_search_idx ON video_transcripts USING gin(search_vector);

CREATE TABLE IF NOT EXISTS transcript_segments (
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  sequence integer NOT NULL,
  start_seconds numeric(10,3) NOT NULL,
  duration_seconds numeric(10,3) NOT NULL,
  segment_text text NOT NULL,
  PRIMARY KEY (youtube_video_id, sequence)
);

CREATE INDEX IF NOT EXISTS transcript_segments_video_time_idx ON transcript_segments(youtube_video_id, start_seconds);

CREATE TABLE IF NOT EXISTS video_comments (
  youtube_comment_id text PRIMARY KEY,
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  relevance_rank integer NOT NULL,
  comment_text text NOT NULL,
  like_count integer NOT NULL DEFAULT 0,
  reply_count integer NOT NULL DEFAULT 0,
  published_at timestamptz,
  engagement_tags text[] NOT NULL DEFAULT '{}',
  fetched_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS video_comments_video_rank_idx ON video_comments(youtube_video_id, relevance_rank);

CREATE TABLE IF NOT EXISTS boats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  make text NOT NULL,
  model text NOT NULL,
  full_name text NOT NULL,
  length_feet numeric(6,2),
  category text NOT NULL DEFAULT 'power',
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_confidence numeric(4,3) NOT NULL DEFAULT 0,
  editorial_status text NOT NULL DEFAULT 'pending',
  UNIQUE (make, model)
);

CREATE TABLE IF NOT EXISTS boat_categories (
  category_key text PRIMARY KEY,
  display_name text NOT NULL UNIQUE,
  description text NOT NULL,
  launch_order integer NOT NULL,
  is_live boolean NOT NULL DEFAULT false
);

INSERT INTO boat_categories (category_key, display_name, description, launch_order, is_live) VALUES
  ('adventure', 'Adventure Boats', 'Versatile, weather-capable power boats suited to purposeful day trips and exploring.', 1, true),
  ('fast-explorer', 'Fast Explorers', 'Longer-range explorer layouts with higher passage speed.', 2, false),
  ('sport-yacht', 'Sport Yachts', 'Performance-led yachts balancing accommodation and social use.', 3, false),
  ('luxury-rib', 'Luxury RIBs', 'Premium rigid-inflatable boats for performance and practical day use.', 4, false),
  ('luxury-med-day-boat', 'Luxury Med Day Boats', 'Open luxury day boats focused on swimming, social space and fair-weather use.', 5, false)
ON CONFLICT (category_key) DO UPDATE SET
  display_name = excluded.display_name,
  description = excluded.description,
  launch_order = excluded.launch_order;

CREATE TABLE IF NOT EXISTS boat_category_assignments (
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  category_key text NOT NULL REFERENCES boat_categories(category_key),
  confidence numeric(4,3) NOT NULL,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  editorial_status text NOT NULL DEFAULT 'pending',
  PRIMARY KEY (boat_id, category_key)
);

CREATE TABLE IF NOT EXISTS mission_definitions (
  mission_key text PRIMARY KEY,
  display_name text NOT NULL UNIQUE,
  description text NOT NULL,
  hard_requirements jsonb NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO mission_definitions (mission_key, display_name, description) VALUES
  ('family', 'Family time', 'Comfortable access, protection and flexible social space.'),
  ('fishing', 'Fishing', 'Practical movement, working space and access to the water.'),
  ('watersports', 'Watersports', 'Swimming access, toy handling and energetic day use.'),
  ('exploring', 'Exploring', 'Weather range, independence and purposeful coastal travel.'),
  ('mixed-use', 'Mixed use', 'A balanced brief without over-specialising the boat.')
ON CONFLICT (mission_key) DO UPDATE SET
  display_name = excluded.display_name,
  description = excluded.description;

CREATE TABLE IF NOT EXISTS boat_mission_profiles (
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  mission_key text NOT NULL REFERENCES mission_definitions(mission_key),
  fit_score numeric(5,4) NOT NULL CHECK (fit_score BETWEEN 0 AND 1),
  evidence_claim_ids uuid[] NOT NULL DEFAULT '{}',
  explanation text NOT NULL,
  editorial_status text NOT NULL DEFAULT 'pending',
  PRIMARY KEY (boat_id, mission_key)
);

CREATE TABLE IF NOT EXISTS boat_aliases (
  alias text PRIMARY KEY,
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS boat_videos (
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  video_type text NOT NULL CHECK (video_type IN ('walkthrough', 'test_drive')),
  match_confidence numeric(4,3) NOT NULL,
  match_method text NOT NULL,
  PRIMARY KEY (boat_id, youtube_video_id, video_type)
);

CREATE TABLE IF NOT EXISTS evidence_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  boat_id uuid REFERENCES boats(id) ON DELETE CASCADE,
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  start_seconds numeric(10,3) NOT NULL,
  end_seconds numeric(10,3),
  claim_type text NOT NULL,
  topic text NOT NULL,
  missions text[] NOT NULL DEFAULT '{}',
  evidence_text text NOT NULL,
  public_summary text,
  confidence numeric(4,3) NOT NULL,
  editorial_status text NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS evidence_claims_boat_idx ON evidence_claims(boat_id, editorial_status);

CREATE TABLE IF NOT EXISTS boat_market_metrics (
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  period_months integer NOT NULL,
  country_code char(2) NOT NULL DEFAULT 'ZZ',
  sold_count integer NOT NULL,
  median_sold_price_aud numeric(14,2),
  median_days_on_market numeric(10,2),
  regional_share numeric(8,5),
  source_refreshed_at timestamptz NOT NULL,
  PRIMARY KEY (boat_id, period_months, country_code)
);

CREATE TABLE IF NOT EXISTS guide_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  public_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
  resume_token_hash text NOT NULL,
  status text NOT NULL DEFAULT 'active',
  first_name text,
  email text,
  phone text,
  buyer_country_code char(2),
  marketing_consent boolean NOT NULL DEFAULT false,
  consent_recorded_at timestamptz,
  rule_version text NOT NULL DEFAULT 'adventure-v1',
  started_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS guide_decisions (
  id bigserial PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES guide_sessions(id) ON DELETE CASCADE,
  sequence integer NOT NULL,
  question_id text NOT NULL,
  answer_value jsonb NOT NULL,
  answer_label text NOT NULL,
  is_current boolean NOT NULL DEFAULT true,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, sequence)
);

CREATE INDEX IF NOT EXISTS guide_decisions_session_current_idx ON guide_decisions(session_id, is_current, sequence);

CREATE TABLE IF NOT EXISTS guide_results (
  id bigserial PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES guide_sessions(id) ON DELETE CASCADE,
  boat_id uuid REFERENCES boats(id) ON DELETE SET NULL,
  result_rank integer NOT NULL,
  total_score numeric(8,5) NOT NULL,
  score_breakdown jsonb NOT NULL,
  explanation jsonb NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS guide_events (
  id bigserial PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES guide_sessions(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  event_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS email_outbox (
  id bigserial PRIMARY KEY,
  session_id uuid REFERENCES guide_sessions(id) ON DELETE SET NULL,
  recipient text NOT NULL,
  subject text NOT NULL,
  text_body text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  attempts integer NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);
