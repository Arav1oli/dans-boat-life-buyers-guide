ALTER TABLE boats ADD COLUMN IF NOT EXISTS canonical_key text;

CREATE UNIQUE INDEX IF NOT EXISTS boats_canonical_key_idx
  ON boats(canonical_key)
  WHERE canonical_key IS NOT NULL;

ALTER TABLE boat_categories ADD COLUMN IF NOT EXISTS family text NOT NULL DEFAULT 'Editorial category';
ALTER TABLE boat_categories ADD COLUMN IF NOT EXISTS definition_status text NOT NULL DEFAULT 'candidate';

UPDATE boat_categories
SET family = 'Dan category anchor', definition_status = 'anchor'
WHERE category_key IN ('adventure', 'fast-explorer', 'sport-yacht', 'luxury-rib', 'luxury-med-day-boat');

INSERT INTO boat_categories (
  category_key, display_name, description, launch_order, is_live, family, definition_status
) VALUES
  ('power-catamaran', 'Power Catamarans', 'Twin-hull power boats, including cruising and performance cats.', 101, false, 'Transcript type', 'candidate'),
  ('centre-console', 'Centre Consoles', 'Open boats organised around a central helm console.', 102, false, 'Transcript type', 'candidate'),
  ('walkaround-day-boat', 'Walkaround Day Boats', 'Day boats with easy movement around the helm and social areas.', 103, false, 'Transcript type', 'candidate'),
  ('sports-cruiser', 'Sports Cruisers', 'Fast planing cruisers with cockpit social space and overnight accommodation.', 104, false, 'Transcript type', 'candidate'),
  ('express-cruiser', 'Express Cruisers', 'Single-level or coupe-style cruisers designed for fast coastal use.', 105, false, 'Transcript type', 'candidate'),
  ('flybridge-motor-yacht', 'Flybridge Motor Yachts', 'Motor yachts with a second, elevated helm and social deck.', 106, false, 'Transcript type', 'candidate'),
  ('pilothouse-crossover', 'Pilothouse / All-weather Crossovers', 'Enclosed-helm boats balancing protection, deck access and practical year-round use.', 107, false, 'Transcript type', 'candidate'),
  ('explorer-expedition', 'Explorer / Expedition Yachts', 'Long-range displacement or semi-displacement yachts designed for extended travel.', 108, false, 'Transcript type', 'candidate'),
  ('offshore-fishing', 'Offshore Fishing Boats', 'Boats whose working layout and capability are explicitly framed around offshore fishing.', 109, false, 'Transcript type', 'candidate'),
  ('bowrider-runabout', 'Bowriders / Runabouts', 'Open day boats with forward seating and short-trip social use.', 110, false, 'Transcript type', 'candidate'),
  ('weekender-commuter', 'Weekenders / Commuters', 'Compact practical cruisers for short stays, commuting and mixed day use.', 111, false, 'Transcript type', 'candidate'),
  ('chase-tender', 'Chase Boats / Yacht Tenders', 'High-capability tenders and chase boats supporting a larger yacht or resort mission.', 112, false, 'Transcript type', 'candidate'),
  ('lobster-downeast', 'Lobster / Downeast Cruisers', 'Traditional workboat-influenced cruisers with efficient, protected layouts.', 113, false, 'Transcript type', 'candidate'),
  ('amphibious', 'Amphibious Boats', 'Boats with integrated land-running or beach-launch capability.', 114, false, 'Transcript type', 'candidate'),
  ('superyacht', 'Superyachts', 'Large crewed yachts with superyacht-scale accommodation and systems.', 115, false, 'Transcript type', 'candidate')
ON CONFLICT (category_key) DO UPDATE SET
  display_name = excluded.display_name,
  description = excluded.description,
  family = excluded.family,
  definition_status = excluded.definition_status;

CREATE TABLE IF NOT EXISTS boat_attribute_definitions (
  attribute_key text PRIMARY KEY,
  attribute_group text NOT NULL,
  display_name text NOT NULL UNIQUE,
  value_type text NOT NULL CHECK (value_type IN ('number', 'boolean', 'enum', 'text')),
  canonical_unit text,
  description text NOT NULL,
  decision_use text NOT NULL,
  editorial_status text NOT NULL DEFAULT 'candidate',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS boat_attribute_values (
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  attribute_key text NOT NULL REFERENCES boat_attribute_definitions(attribute_key) ON DELETE CASCADE,
  value_key text NOT NULL DEFAULT 'primary',
  value_number numeric,
  value_boolean boolean,
  value_text text,
  unit text,
  value_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  evidence_count integer NOT NULL DEFAULT 0,
  editorial_status text NOT NULL DEFAULT 'candidate',
  calculated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (boat_id, attribute_key, value_key),
  CONSTRAINT boat_attribute_value_present CHECK (
    value_number IS NOT NULL OR value_boolean IS NOT NULL OR value_text IS NOT NULL
  )
);

CREATE INDEX IF NOT EXISTS boat_attribute_values_lookup_idx
  ON boat_attribute_values(attribute_key, value_number, value_boolean, value_text);

CREATE TABLE IF NOT EXISTS boat_attribute_evidence (
  id bigserial PRIMARY KEY,
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  attribute_key text NOT NULL REFERENCES boat_attribute_definitions(attribute_key) ON DELETE CASCADE,
  value_key text NOT NULL DEFAULT 'primary',
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  transcript_sequence integer NOT NULL,
  start_seconds numeric(10,3) NOT NULL,
  evidence_text text NOT NULL,
  value_number numeric,
  value_boolean boolean,
  value_text text,
  unit text,
  qualifier text NOT NULL DEFAULT 'observed',
  confidence numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  extraction_method text NOT NULL,
  editorial_status text NOT NULL DEFAULT 'candidate',
  UNIQUE (boat_id, attribute_key, value_key, youtube_video_id, transcript_sequence, extraction_method)
);

CREATE INDEX IF NOT EXISTS boat_attribute_evidence_boat_idx
  ON boat_attribute_evidence(boat_id, attribute_key, start_seconds);

CREATE TABLE IF NOT EXISTS boat_category_evidence (
  id bigserial PRIMARY KEY,
  boat_id uuid NOT NULL REFERENCES boats(id) ON DELETE CASCADE,
  category_key text NOT NULL REFERENCES boat_categories(category_key) ON DELETE CASCADE,
  youtube_video_id text NOT NULL REFERENCES source_videos(youtube_video_id) ON DELETE CASCADE,
  transcript_sequence integer NOT NULL,
  start_seconds numeric(10,3) NOT NULL,
  evidence_text text NOT NULL,
  confidence numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  extraction_method text NOT NULL,
  editorial_status text NOT NULL DEFAULT 'candidate',
  UNIQUE (boat_id, category_key, youtube_video_id, transcript_sequence, extraction_method)
);

CREATE INDEX IF NOT EXISTS boat_category_evidence_boat_idx
  ON boat_category_evidence(boat_id, category_key, start_seconds);
