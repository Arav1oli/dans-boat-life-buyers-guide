from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

import psycopg

from etl.ingest import store_postgres
from etl.matcher import NON_BOAT_OUTLIERS, SalesCatalogue, pair_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Import already captured YouTube evidence without making network requests")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), required=False)
    parser.add_argument("--report", default="data/reports/postgres-import.json")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    paths = sorted(Path(args.input).glob("*.json"))
    catalogue = SalesCatalogue(args.sales_db)
    report = {
        "saved_records": len(paths),
        "imported": 0,
        "failed": [],
        "identity_complete": 0,
        "non_boat_outliers": 0,
        "transcripts": 0,
        "comments": 0,
        "pairs": {},
    }
    # Disabling client-side prepared statements also keeps the importer
    # compatible with the lightweight PGlite wire server used in integration QA.
    with psycopg.connect(args.database_url, prepare_threshold=None) as connection:
        for index, path in enumerate(paths, 1):
            item = json.loads(path.read_text())
            video_id = item["youtube_video_id"]
            identity = catalogue.match(item["title"], item.get("description") or "", video_id)
            item["boat_identity"] = asdict(identity)
            path.write_text(json.dumps(item, ensure_ascii=False))
            try:
                store_postgres(connection, item, identity)
                connection.commit()
            except Exception as exc:
                connection.rollback()
                report["failed"].append({"video_id": video_id, "error": f"{type(exc).__name__}: {exc}"})
                continue
            report["imported"] += 1
            report["transcripts"] += int(bool(item.get("transcript_segments")))
            report["comments"] += len(item.get("comments") or [])
            if video_id in NON_BOAT_OUTLIERS:
                report["non_boat_outliers"] += 1
            elif identity.make and identity.model and identity.length_feet is not None:
                report["identity_complete"] += 1
            key = pair_key(identity)
            if key:
                report["pairs"].setdefault(key, []).append({
                    "video_id": video_id,
                    "types": [membership["video_type"] for membership in item["playlists"]],
                })
            if index % 25 == 0 or index == len(paths):
                print(f"[{index}/{len(paths)}] imported", flush=True)

    report["paired_models"] = sum(
        1
        for videos in report["pairs"].values()
        if {video_type for video in videos for video_type in video["types"]} >= {"walkthrough", "test_drive"}
    )
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "pairs"}, indent=2))


if __name__ == "__main__":
    main()
