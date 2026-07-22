from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from etl.sales import model_summary, readonly_connection


MARKETS = ("ZZ", "AU", "US", "GB", "NZ")
MISSIONS = ("family", "fishing", "watersports", "exploring", "mixed-use")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the validated Adventure Boat launch catalogue into PostgreSQL")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--boats", default="guide/data/boats.json")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--report", default="data/reports/launch-catalog-import.json")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    boats = json.loads(Path(args.boats).read_text())
    report = {"boats": 0, "video_links": 0, "market_rows": 0, "mission_profiles": 0, "failures": []}
    with readonly_connection(args.sales_db) as sales, psycopg.connect(args.database_url, prepare_threshold=None) as database:
        source_refreshed_at = sales.execute("SELECT MAX(sold_date) FROM sold_boats").fetchone()[0]
        if source_refreshed_at:
            source_refreshed_at = datetime.fromisoformat(source_refreshed_at).replace(tzinfo=timezone.utc)
        else:
            source_refreshed_at = datetime.now(timezone.utc)

        for boat in boats:
            try:
                boat_id = database.execute(
                    """
                    INSERT INTO boats (make, model, full_name, length_feet, category, features, evidence_confidence, editorial_status)
                    VALUES (%s, %s, %s, %s, 'power', %s, %s, 'published')
                    ON CONFLICT (make, model) DO UPDATE SET
                      full_name = excluded.full_name,
                      length_feet = excluded.length_feet,
                      features = excluded.features,
                      evidence_confidence = excluded.evidence_confidence,
                      editorial_status = 'published'
                    RETURNING id
                    """,
                    (
                        boat["make"], boat["model"], boat["full_name"], boat["length_feet"],
                        Jsonb(boat["features"]), boat["evidence_confidence"],
                    ),
                ).fetchone()[0]
                video_ids = [video["id"] for video in boat["videos"]]
                database.execute(
                    """
                    INSERT INTO boat_category_assignments (boat_id, category_key, confidence, evidence, editorial_status)
                    VALUES (%s, 'adventure', 0.950, %s, 'published')
                    ON CONFLICT (boat_id, category_key) DO UPDATE SET
                      confidence = excluded.confidence, evidence = excluded.evidence, editorial_status = 'published'
                    """,
                    (boat_id, Jsonb({"video_ids": video_ids, "catalogue": "adventure-v1"})),
                )

                for video in boat["videos"]:
                    video_type = "test_drive" if video["type"].lower().startswith("test") else "walkthrough"
                    database.execute(
                        """
                        INSERT INTO boat_videos (boat_id, youtube_video_id, video_type, match_confidence, match_method)
                        VALUES (%s, %s, %s, 0.990, 'editorial_launch_catalog')
                        ON CONFLICT (boat_id, youtube_video_id, video_type) DO UPDATE SET
                          match_confidence = excluded.match_confidence, match_method = excluded.match_method
                        """,
                        (boat_id, video["id"], video_type),
                    )
                    report["video_links"] += 1

                claims = database.execute(
                    "SELECT id, topic, missions FROM evidence_claims WHERE youtube_video_id = ANY(%s)",
                    (video_ids,),
                ).fetchall()
                for mission in MISSIONS:
                    matching = [row for row in claims if mission in (row[2] or [])]
                    topics = sorted({row[1] for row in matching})
                    priority = mission in boat["features"]["priorities"]
                    fit_score = min((0.68 if priority else 0.32) + len(topics) * 0.045, 0.95)
                    explanation = (
                        "Dan transcript topics: " + ", ".join(topic.replace("_", " ") for topic in topics)
                        if topics else "No mission-specific transcript topic published yet."
                    )
                    database.execute(
                        """
                        INSERT INTO boat_mission_profiles (
                          boat_id, mission_key, fit_score, evidence_claim_ids, explanation, editorial_status
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (boat_id, mission_key) DO UPDATE SET
                          fit_score = excluded.fit_score,
                          evidence_claim_ids = excluded.evidence_claim_ids,
                          explanation = excluded.explanation,
                          editorial_status = excluded.editorial_status
                        """,
                        (
                            boat_id, mission, fit_score, [row[0] for row in matching], explanation,
                            "published" if matching else "pending",
                        ),
                    )
                    report["mission_profiles"] += 1

                global_summary = model_summary(sales, boat["make"], boat["model"], 120)
                global_count = int(global_summary[0] or 0)
                for country_code in MARKETS:
                    summary = global_summary if country_code == "ZZ" else model_summary(
                        sales, boat["make"], boat["model"], 120, country_code
                    )
                    sold_count = int(summary[0] or 0)
                    database.execute(
                        """
                        INSERT INTO boat_market_metrics (
                          boat_id, period_months, country_code, sold_count, median_sold_price_aud,
                          median_days_on_market, regional_share, source_refreshed_at
                        ) VALUES (%s, 120, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (boat_id, period_months, country_code) DO UPDATE SET
                          sold_count = excluded.sold_count,
                          median_sold_price_aud = excluded.median_sold_price_aud,
                          median_days_on_market = excluded.median_days_on_market,
                          regional_share = excluded.regional_share,
                          source_refreshed_at = excluded.source_refreshed_at
                        """,
                        (
                            boat_id, country_code, sold_count, summary[1], summary[2],
                            (sold_count / global_count) if global_count else None, source_refreshed_at,
                        ),
                    )
                    report["market_rows"] += 1
                database.commit()
                report["boats"] += 1
            except Exception as exc:
                database.rollback()
                report["failures"].append({"boat": boat["full_name"], "error": f"{type(exc).__name__}: {exc}"})

    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
