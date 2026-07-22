from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from etl.matcher import SalesCatalogue, pair_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile saved YouTube records to mandatory make/model/length identities")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--report", default="data/reports/identity-reconciliation.json")
    args = parser.parse_args()

    catalogue = SalesCatalogue(args.sales_db)
    groups = defaultdict(list)
    unmatched = []
    outliers = []
    low_confidence = []
    for path in sorted(Path(args.input).glob("*.json")):
        item = json.loads(path.read_text())
        identity = catalogue.match(item.get("title", ""), item.get("description", ""), item.get("youtube_video_id"))
        item["boat_identity"] = asdict(identity)
        path.write_text(json.dumps(item, ensure_ascii=False))
        key = pair_key(identity)
        record = {"video_id": item["youtube_video_id"], "title": item["title"], "identity": asdict(identity), "types": [row["video_type"] for row in item["playlists"]]}
        if identity.method == "non_boat_playlist_outlier":
            outliers.append(record)
            continue
        if not key or identity.length_feet is None:
            unmatched.append(record)
        else:
            groups[key].append(record)
            if identity.confidence < 0.84:
                low_confidence.append(record)

    paired = {}
    walkthrough_only = {}
    test_only = {}
    for key, records in groups.items():
        types = {kind for record in records for kind in record["types"]}
        if types >= {"walkthrough", "test_drive"}:
            paired[key] = records
        elif "walkthrough" in types:
            walkthrough_only[key] = records
        else:
            test_only[key] = records

    report = {
        "total_records": sum(len(records) for records in groups.values()) + len(unmatched) + len(outliers),
        "mandatory_identity_complete": sum(len(records) for records in groups.values()),
        "unmatched_or_missing_length": unmatched,
        "non_boat_playlist_outliers": outliers,
        "low_confidence": low_confidence,
        "paired_models": paired,
        "walkthrough_only": walkthrough_only,
        "test_drive_only": test_only,
    }
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2))
    print(json.dumps({
        "total_records": report["total_records"],
        "mandatory_identity_complete": report["mandatory_identity_complete"],
        "unmatched_or_missing_length": len(unmatched),
        "non_boat_playlist_outliers": len(outliers),
        "low_confidence": len(low_confidence),
        "paired_models": len(paired),
        "walkthrough_only": len(walkthrough_only),
        "test_drive_only": len(test_only),
    }, indent=2))


if __name__ == "__main__":
    main()
