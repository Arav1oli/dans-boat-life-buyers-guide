from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from etl.taxonomy import ATTRIBUTE_DEFINITIONS, CATEGORY_DEFINITIONS, load_profiles


def sync_definitions(database: psycopg.Connection) -> None:
    for definition in ATTRIBUTE_DEFINITIONS:
        database.execute(
            """
            INSERT INTO boat_attribute_definitions (
              attribute_key, attribute_group, display_name, value_type, canonical_unit,
              description, decision_use, editorial_status, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'candidate', now())
            ON CONFLICT (attribute_key) DO UPDATE SET
              attribute_group = excluded.attribute_group,
              display_name = excluded.display_name,
              value_type = excluded.value_type,
              canonical_unit = excluded.canonical_unit,
              description = excluded.description,
              decision_use = excluded.decision_use,
              updated_at = now()
            """,
            (
                definition.key,
                definition.group,
                definition.label,
                definition.value_type,
                definition.unit,
                definition.description,
                definition.decision_use,
            ),
        )
    for index, definition in enumerate(CATEGORY_DEFINITIONS, 1):
        database.execute(
            """
            INSERT INTO boat_categories (
              category_key, display_name, description, launch_order, is_live, family, definition_status
            ) VALUES (%s, %s, %s, %s, false, %s, %s)
            ON CONFLICT (category_key) DO UPDATE SET
              display_name = excluded.display_name,
              description = excluded.description,
              family = excluded.family,
              definition_status = excluded.definition_status
            """,
            (
                definition.key,
                definition.label,
                definition.description,
                index if definition.status == "anchor" else 100 + index,
                definition.family,
                definition.status,
            ),
        )


def merge_duplicate_boat(database: psycopg.Connection, target_id: str, duplicate_id: str) -> None:
    database.execute(
        """
        INSERT INTO boat_videos (
          boat_id, youtube_video_id, video_type, match_confidence, match_method
        )
        SELECT %s, youtube_video_id, video_type, match_confidence, match_method
        FROM boat_videos WHERE boat_id = %s
        ON CONFLICT (boat_id, youtube_video_id, video_type) DO UPDATE SET
          match_confidence = greatest(boat_videos.match_confidence, excluded.match_confidence)
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_videos WHERE boat_id = %s", (duplicate_id,))
    database.execute("UPDATE evidence_claims SET boat_id = %s WHERE boat_id = %s", (target_id, duplicate_id))
    database.execute("UPDATE guide_results SET boat_id = %s WHERE boat_id = %s", (target_id, duplicate_id))
    database.execute("UPDATE boat_aliases SET boat_id = %s WHERE boat_id = %s", (target_id, duplicate_id))

    database.execute(
        """
        INSERT INTO boat_category_assignments (
          boat_id, category_key, confidence, evidence, editorial_status
        )
        SELECT %s, category_key, confidence, evidence, editorial_status
        FROM boat_category_assignments WHERE boat_id = %s
        ON CONFLICT (boat_id, category_key) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_category_assignments WHERE boat_id = %s", (duplicate_id,))
    database.execute(
        """
        INSERT INTO boat_mission_profiles (
          boat_id, mission_key, fit_score, evidence_claim_ids, explanation, editorial_status
        )
        SELECT %s, mission_key, fit_score, evidence_claim_ids, explanation, editorial_status
        FROM boat_mission_profiles WHERE boat_id = %s
        ON CONFLICT (boat_id, mission_key) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_mission_profiles WHERE boat_id = %s", (duplicate_id,))
    database.execute(
        """
        INSERT INTO boat_market_metrics (
          boat_id, period_months, country_code, sold_count, median_sold_price_aud,
          median_days_on_market, regional_share, source_refreshed_at
        )
        SELECT %s, period_months, country_code, sold_count, median_sold_price_aud,
          median_days_on_market, regional_share, source_refreshed_at
        FROM boat_market_metrics WHERE boat_id = %s
        ON CONFLICT (boat_id, period_months, country_code) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_market_metrics WHERE boat_id = %s", (duplicate_id,))
    database.execute(
        """
        INSERT INTO boat_attribute_values (
          boat_id, attribute_key, value_key, value_number, value_boolean, value_text,
          unit, value_detail, confidence, evidence_count, editorial_status, calculated_at
        )
        SELECT %s, attribute_key, value_key, value_number, value_boolean, value_text,
          unit, value_detail, confidence, evidence_count, editorial_status, calculated_at
        FROM boat_attribute_values WHERE boat_id = %s
        ON CONFLICT (boat_id, attribute_key, value_key) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_attribute_values WHERE boat_id = %s", (duplicate_id,))
    database.execute(
        """
        INSERT INTO boat_attribute_evidence (
          boat_id, attribute_key, value_key, youtube_video_id, transcript_sequence,
          start_seconds, evidence_text, value_number, value_boolean, value_text, unit,
          qualifier, confidence, extraction_method, editorial_status
        )
        SELECT %s, attribute_key, value_key, youtube_video_id, transcript_sequence,
          start_seconds, evidence_text, value_number, value_boolean, value_text, unit,
          qualifier, confidence, extraction_method, editorial_status
        FROM boat_attribute_evidence WHERE boat_id = %s
        ON CONFLICT (
          boat_id, attribute_key, value_key, youtube_video_id, transcript_sequence, extraction_method
        ) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_attribute_evidence WHERE boat_id = %s", (duplicate_id,))
    database.execute(
        """
        INSERT INTO boat_category_evidence (
          boat_id, category_key, youtube_video_id, transcript_sequence,
          start_seconds, evidence_text, confidence, extraction_method, editorial_status
        )
        SELECT %s, category_key, youtube_video_id, transcript_sequence,
          start_seconds, evidence_text, confidence, extraction_method, editorial_status
        FROM boat_category_evidence WHERE boat_id = %s
        ON CONFLICT (
          boat_id, category_key, youtube_video_id, transcript_sequence, extraction_method
        ) DO NOTHING
        """,
        (target_id, duplicate_id),
    )
    database.execute("DELETE FROM boat_category_evidence WHERE boat_id = %s", (duplicate_id,))
    database.execute("DELETE FROM boats WHERE id = %s", (duplicate_id,))


def upsert_boat(database: psycopg.Connection, profile: dict) -> str:
    video_ids = [video["id"] for video in profile["videos"]]
    rows = database.execute(
        """
        SELECT DISTINCT
          b.id,
          b.editorial_status,
          CASE WHEN b.editorial_status = 'published' THEN 0 ELSE 1 END AS editorial_priority
        FROM boats b
        LEFT JOIN boat_videos bv ON bv.boat_id = b.id
        WHERE b.canonical_key = %s
           OR (
             lower(trim(b.make)) = lower(trim(%s))
             AND lower(trim(b.model)) = lower(trim(%s))
           )
           OR bv.youtube_video_id = ANY(%s)
        ORDER BY editorial_priority, b.id
        """,
        (profile["canonical_key"], profile["make"], profile["model"], video_ids),
    ).fetchall()
    if rows:
        boat_id = rows[0][0]
        target_status = rows[0][1]
        for duplicate_id, _, _ in rows[1:]:
            merge_duplicate_boat(database, boat_id, duplicate_id)
        update_names = target_status != "published"
        database.execute(
            """
            UPDATE boats
            SET canonical_key = %s,
                make = CASE WHEN %s THEN %s ELSE make END,
                model = CASE WHEN %s THEN %s ELSE model END,
                full_name = CASE WHEN %s THEN %s ELSE full_name END,
                length_feet = %s,
                evidence_confidence = greatest(evidence_confidence, %s),
                editorial_status = CASE
                  WHEN editorial_status = 'published' THEN editorial_status
                  ELSE 'evidence_ready'
                END
            WHERE id = %s
            """,
            (
                profile["canonical_key"],
                update_names,
                profile["make"],
                update_names,
                profile["model"],
                update_names,
                profile["full_name"],
                profile["length_feet"],
                profile["identity_confidence"],
                boat_id,
            ),
        )
        return str(boat_id)
    return str(database.execute(
        """
        INSERT INTO boats (
          canonical_key, make, model, full_name, length_feet, category,
          evidence_confidence, editorial_status
        ) VALUES (%s, %s, %s, %s, %s, 'power', %s, 'evidence_ready')
        RETURNING id
        """,
        (
            profile["canonical_key"],
            profile["make"],
            profile["model"],
            profile["full_name"],
            profile["length_feet"],
            profile["identity_confidence"],
        ),
    ).fetchone()[0])


def import_profile(database: psycopg.Connection, profile: dict, report: dict) -> None:
    boat_id = upsert_boat(database, profile)
    video_ids = []
    for video in profile["videos"]:
        video_ids.append(video["id"])
        for video_type in video["types"]:
            database.execute(
                """
                INSERT INTO boat_videos (
                  boat_id, youtube_video_id, video_type, match_confidence, match_method
                ) VALUES (%s, %s, %s, %s, 'canonical_make_model')
                ON CONFLICT (boat_id, youtube_video_id, video_type) DO UPDATE SET
                  match_confidence = excluded.match_confidence,
                  match_method = excluded.match_method
                """,
                (boat_id, video["id"], video_type, profile["identity_confidence"]),
            )
            report["video_links"] += 1
    database.execute(
        "UPDATE evidence_claims SET boat_id = %s WHERE youtube_video_id = ANY(%s)",
        (boat_id, video_ids),
    )

    database.execute(
        "DELETE FROM boat_attribute_evidence WHERE boat_id = %s AND editorial_status = 'candidate'",
        (boat_id,),
    )
    database.execute(
        "DELETE FROM boat_attribute_values WHERE boat_id = %s AND editorial_status = 'candidate'",
        (boat_id,),
    )
    for attribute in profile["attributes"]:
        related = [
            item
            for item in profile["attribute_evidence"]
            if item["attribute_key"] == attribute["attribute_key"]
            and (attribute["value_key"] == "primary" or item["value_key"] == attribute["value_key"])
        ]
        database.execute(
            """
            INSERT INTO boat_attribute_values (
              boat_id, attribute_key, value_key, value_number, value_boolean, value_text,
              unit, value_detail, confidence, evidence_count, editorial_status, calculated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'candidate', now())
            ON CONFLICT (boat_id, attribute_key, value_key) DO UPDATE SET
              value_number = excluded.value_number,
              value_boolean = excluded.value_boolean,
              value_text = excluded.value_text,
              unit = excluded.unit,
              value_detail = excluded.value_detail,
              confidence = excluded.confidence,
              evidence_count = excluded.evidence_count,
              calculated_at = now()
            WHERE boat_attribute_values.editorial_status = 'candidate'
            """,
            (
                boat_id,
                attribute["attribute_key"],
                attribute["value_key"],
                attribute["value_number"],
                attribute["value_boolean"],
                attribute["value_text"],
                attribute["unit"],
                Jsonb(attribute["value_detail"]),
                attribute["confidence"],
                len(related),
            ),
        )
        report["attribute_values"] += 1
    for evidence in profile["attribute_evidence"]:
        database.execute(
            """
            INSERT INTO boat_attribute_evidence (
              boat_id, attribute_key, value_key, youtube_video_id, transcript_sequence,
              start_seconds, evidence_text, value_number, value_boolean, value_text, unit,
              qualifier, confidence, extraction_method, editorial_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'candidate')
            ON CONFLICT (
              boat_id, attribute_key, value_key, youtube_video_id, transcript_sequence, extraction_method
            ) DO UPDATE SET
              evidence_text = excluded.evidence_text,
              value_number = excluded.value_number,
              value_boolean = excluded.value_boolean,
              value_text = excluded.value_text,
              unit = excluded.unit,
              qualifier = excluded.qualifier,
              confidence = excluded.confidence
            WHERE boat_attribute_evidence.editorial_status = 'candidate'
            """,
            (
                boat_id,
                evidence["attribute_key"],
                evidence["value_key"],
                evidence["video_id"],
                evidence["sequence"],
                evidence["start_seconds"],
                evidence["evidence_text"],
                evidence["value_number"],
                evidence["value_boolean"],
                evidence["value_text"],
                evidence["unit"],
                evidence["qualifier"],
                evidence["confidence"],
                evidence["extraction_method"],
            ),
        )
        report["attribute_evidence"] += 1

    database.execute(
        "DELETE FROM boat_category_evidence WHERE boat_id = %s AND editorial_status = 'candidate'",
        (boat_id,),
    )
    database.execute(
        "DELETE FROM boat_category_assignments WHERE boat_id = %s AND editorial_status = 'candidate'",
        (boat_id,),
    )
    for category in profile["categories"]:
        database.execute(
            """
            INSERT INTO boat_category_assignments (
              boat_id, category_key, confidence, evidence, editorial_status
            ) VALUES (%s, %s, %s, %s, 'candidate')
            ON CONFLICT (boat_id, category_key) DO UPDATE SET
              confidence = excluded.confidence,
              evidence = excluded.evidence
            WHERE boat_category_assignments.editorial_status = 'candidate'
            """,
            (
                boat_id,
                category["category_key"],
                category["confidence"],
                Jsonb(category["evidence"]),
            ),
        )
        report["category_assignments"] += 1
    for evidence in profile["category_evidence"]:
        database.execute(
            """
            INSERT INTO boat_category_evidence (
              boat_id, category_key, youtube_video_id, transcript_sequence,
              start_seconds, evidence_text, confidence, extraction_method, editorial_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'candidate')
            ON CONFLICT (
              boat_id, category_key, youtube_video_id, transcript_sequence, extraction_method
            ) DO UPDATE SET
              evidence_text = excluded.evidence_text,
              confidence = excluded.confidence
            WHERE boat_category_evidence.editorial_status = 'candidate'
            """,
            (
                boat_id,
                evidence["category_key"],
                evidence["video_id"],
                evidence["sequence"],
                evidence["start_seconds"],
                evidence["evidence_text"],
                evidence["confidence"],
                evidence["extraction_method"],
            ),
        )
        report["category_evidence"] += 1
    report["boats"] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Import transcript-evidenced taxonomy candidates into PostgreSQL")
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--report", default="data/reports/taxonomy-import.json")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    report = {
        "boats": 0,
        "video_links": 0,
        "attribute_values": 0,
        "attribute_evidence": 0,
        "category_assignments": 0,
        "category_evidence": 0,
        "failures": [],
    }
    profiles = load_profiles(args.input)
    with psycopg.connect(args.database_url, prepare_threshold=None) as database:
        sync_definitions(database)
        database.commit()
        for index, profile in enumerate(profiles, 1):
            try:
                import_profile(database, profile, report)
                database.commit()
            except Exception as exc:
                database.rollback()
                report["failures"].append({
                    "boat": profile["full_name"],
                    "error": f"{type(exc).__name__}: {exc}",
                })
            if index % 25 == 0 or index == len(profiles):
                print(f"[{index}/{len(profiles)}] taxonomy profiles imported", flush=True)

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
