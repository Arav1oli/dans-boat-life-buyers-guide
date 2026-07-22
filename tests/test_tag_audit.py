from pathlib import Path

from etl.export_tag_audit import export


def test_complete_tag_audit_can_be_reproduced(tmp_path):
    result = export(
        Path("data/reports/boat-taxonomy.json"),
        tmp_path / "long.csv",
        tmp_path / "summary.csv",
        tmp_path / "audit.md",
    )
    assert result == {"boats": 209, "source_videos": 398, "tags": 2547, "flagged_boats": 104}
    assert sum(1 for _ in (tmp_path / "summary.csv").open()) == 210
    assert sum(1 for _ in (tmp_path / "long.csv").open()) == 2548
