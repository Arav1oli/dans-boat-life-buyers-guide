import csv
from pathlib import Path


def test_committed_tag_audits_cover_the_full_ingested_catalogue():
    long_path = Path("BOAT_TAG_AUDIT.csv")
    summary_path = Path("BOAT_TAGS_BY_BOAT.csv")
    with long_path.open(newline="", encoding="utf-8") as handle:
        long_rows = list(csv.DictReader(handle))
    with summary_path.open(newline="", encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))

    assert len(long_rows) == 2547
    assert len(summary_rows) == 209
    assert len({row["canonical_key"] for row in summary_rows}) == 209
    assert {row["tag_type"] for row in long_rows} == {"attribute", "category"}
    assert all(row["make"] and row["model"] and row["source_video_ids"] for row in summary_rows)
    assert sum(bool(row["review_flags"]) for row in summary_rows) == 104
