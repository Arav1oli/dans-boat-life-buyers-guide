from __future__ import annotations

import json
import os

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]

QUERIES = {
    "source_videos": "SELECT COUNT(*) FROM source_videos",
    "identity_complete": "SELECT COUNT(*) FROM source_videos WHERE make IS NOT NULL AND model IS NOT NULL AND length_feet IS NOT NULL",
    "playlist_memberships": "SELECT COUNT(*) FROM playlist_videos",
    "transcripts": "SELECT COUNT(*) FROM video_transcripts",
    "transcript_segments": "SELECT COUNT(*) FROM transcript_segments",
    "comments": "SELECT COUNT(*) FROM video_comments",
    "evidence_claims": "SELECT COUNT(*) FROM evidence_claims",
    "published_launch_boats": "SELECT COUNT(*) FROM boats WHERE editorial_status = 'published'",
    "canonical_boats": "SELECT COUNT(*) FROM boats WHERE canonical_key IS NOT NULL",
    "uncanonicalised_boats": "SELECT COUNT(*) FROM boats WHERE canonical_key IS NULL",
    "attribute_definitions": "SELECT COUNT(*) FROM boat_attribute_definitions",
    "attribute_values": "SELECT COUNT(*) FROM boat_attribute_values",
    "attribute_evidence": "SELECT COUNT(*) FROM boat_attribute_evidence",
    "category_definitions": "SELECT COUNT(*) FROM boat_categories",
    "candidate_category_assignments": "SELECT COUNT(*) FROM boat_category_assignments WHERE editorial_status = 'candidate'",
    "category_evidence": "SELECT COUNT(*) FROM boat_category_evidence",
    "canonical_boat_video_links": "SELECT COUNT(*) FROM boat_videos",
    "adventure_assignments": "SELECT COUNT(*) FROM boat_category_assignments WHERE category_key = 'adventure' AND editorial_status = 'published'",
    "mission_profiles": "SELECT COUNT(*) FROM boat_mission_profiles",
    "market_metric_rows": "SELECT COUNT(*) FROM boat_market_metrics",
}

with psycopg.connect(DATABASE_URL, prepare_threshold=None) as connection:
    counts = {name: connection.execute(query).fetchone()[0] for name, query in QUERIES.items()}

print(json.dumps(counts, indent=2))

assert counts["source_videos"] == 401
assert counts["identity_complete"] == 398
assert counts["playlist_memberships"] == 416
assert counts["transcripts"] == 399
assert counts["transcript_segments"] > 50_000
assert counts["comments"] == 11_769
assert counts["evidence_claims"] > 4_000
assert counts["published_launch_boats"] == 15
assert counts["canonical_boats"] == 209
assert counts["uncanonicalised_boats"] == 0
assert counts["attribute_definitions"] == 51
assert counts["attribute_values"] == 2_275
assert counts["attribute_evidence"] == 4_548
assert counts["category_definitions"] == 20
assert counts["candidate_category_assignments"] == 272
assert counts["category_evidence"] == 608
assert counts["canonical_boat_video_links"] == 413
assert counts["adventure_assignments"] == 15
assert counts["mission_profiles"] == 75
assert counts["market_metric_rows"] == 75
