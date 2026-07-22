from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from etl.taxonomy import ATTRIBUTE_DEFINITIONS, CATEGORY_DEFINITIONS, load_profiles


def build_report(profiles: list[dict]) -> dict:
    attribute_boats = Counter()
    category_boats = Counter()
    category_evidence = Counter()
    conflicts = []
    thin_profiles = []
    for profile in profiles:
        for attribute_key in {attribute["attribute_key"] for attribute in profile["attributes"]}:
            attribute_boats[attribute_key] += 1
        for attribute in profile["attributes"]:
            if attribute["value_text"] == "configuration-dependent":
                conflicts.append({
                    "boat": profile["full_name"],
                    "attribute_key": attribute["attribute_key"],
                    "evidence": attribute["evidence"],
                })
        for category in profile["categories"]:
            category_boats[category["category_key"]] += 1
            category_evidence[category["category_key"]] += category["evidence_count"]
        if len(profile["attributes"]) <= 2:
            thin_profiles.append(profile["full_name"])

    return {
        "canonical_boats": len(profiles),
        "source_videos": sum(len(profile["videos"]) for profile in profiles),
        "transcript_segments": sum(profile["transcript_segments"] for profile in profiles),
        "attribute_definitions": len(ATTRIBUTE_DEFINITIONS),
        "category_definitions": len(CATEGORY_DEFINITIONS),
        "attribute_boat_counts": dict(attribute_boats.most_common()),
        "category_boat_counts": dict(category_boats.most_common()),
        "category_evidence_counts": dict(category_evidence.most_common()),
        "profiles_without_explicit_category": [
            profile["full_name"] for profile in profiles if not profile["categories"]
        ],
        "thin_profiles": thin_profiles,
        "configuration_conflicts": conflicts,
        "profiles": profiles,
    }


def markdown(report: dict) -> str:
    category_counts = report["category_boat_counts"]
    attribute_counts = report["attribute_boat_counts"]
    lines = [
        "# Dan's Boat Life power-boat taxonomy workshop",
        "",
        "This is a corpus-derived working paper, not a final editorial classification. Dan's five supplied category names are retained as anchors. Additional categories are candidates surfaced from the language in the completed walkthrough and test-drive transcripts.",
        "",
        "## Corpus ready for the workshop",
        "",
        f"- Canonical boats: {report['canonical_boats']}",
        f"- Source videos attached to those boats: {report['source_videos']}",
        f"- Transcript segments examined: {report['transcript_segments']:,}",
        f"- Candidate decision attributes: {report['attribute_definitions']}",
        f"- Category anchors and transcript-type candidates: {report['category_definitions']}",
        "",
        "Every tag remains candidate until editorial review. Absence of a tag means the transcript did not establish it; it does not mean the boat lacks the feature.",
        "",
        "## Category candidates",
        "",
        "| Category | Role | Boats with explicit transcript evidence | Working definition |",
        "|---|---|---:|---|",
    ]
    for definition in CATEGORY_DEFINITIONS:
        lines.append(
            f"| {definition.label} | {definition.family} | {category_counts.get(definition.key, 0)} | {definition.description} |"
        )
    lines.extend([
        "",
        "The five Dan category anchors should be resolved in the workshop as mission-led editorial categories. The transcript-type candidates can overlap them; for example, one boat may be both a Power Catamaran and an Adventure Boat.",
        "",
        "## Decision-tree data points",
        "",
        "| Group | Field | Boats currently evidenced | Why it matters |",
        "|---|---|---:|---|",
    ])
    for definition in ATTRIBUTE_DEFINITIONS:
        lines.append(
            f"| {definition.group.replace('_', ' ').title()} | {definition.label} | {attribute_counts.get(definition.key, 0)} | {definition.decision_use} |"
        )
    lines.extend([
        "",
        "## Extraction rules for editorial safety",
        "",
        "- Make, model and length must already pass the identity gate before a boat enters this catalogue.",
        "- Specifications and features are extracted from Dan's timed transcript segments, not filled from generic assumptions.",
        "- Claimed top speed and Dan's maximum observed test speed are separate fields.",
        "- Optional equipment is retained with an optional qualifier.",
        "- Conflicting positive and negative mentions become configuration-dependent instead of a forced yes/no.",
        "- Numeric values retain minimum, maximum, observation count, timestamp, source video and a short evidence excerpt.",
        "- A missing observation is unknown, never false.",
        "- Categories can overlap. The final category language and thresholds remain an editorial decision for Dan.",
        "",
        "## Suggested primary guide forks",
        "",
        "1. Day use only or overnight capability.",
        "2. Protected all-weather helm or open-air social layout.",
        "3. Coastal day range, fast passage or long-range autonomy.",
        "4. Family, fishing, watersports, entertaining or exploring mission.",
        "5. Trailerable / dry storage, marina berth or yacht-tender role.",
        "6. Shallow-water and bridge-clearance constraints.",
        "7. Outboard, sterndrive, shaft, pod, jet or alternative propulsion preference.",
        "8. Required cabins, berths and bathroom privacy.",
        "9. Water-access priorities: platform, balconies, beach club and side door.",
        "10. Handling and comfort systems: joystick, thrusters and stabilisation.",
        "",
        "The machine-readable report also lists boats with no explicit type phrase, thin attribute evidence, and configuration conflicts so they can be prioritised for manual review.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build transcript-evidenced boat taxonomy candidates")
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--output", default="data/reports/boat-taxonomy.json")
    parser.add_argument("--workshop", default="BOAT_TAXONOMY_WORKSHOP.md")
    args = parser.parse_args()

    profiles = load_profiles(args.input)
    report = build_report(profiles)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    Path(args.workshop).write_text(markdown(report))
    print(json.dumps({key: value for key, value in report.items() if key not in {"profiles", "configuration_conflicts", "profiles_without_explicit_category", "thin_profiles"}}, indent=2))
    print(json.dumps({
        "without_explicit_category": len(report["profiles_without_explicit_category"]),
        "thin_profiles": len(report["thin_profiles"]),
        "configuration_conflicts": len(report["configuration_conflicts"]),
    }, indent=2))


if __name__ == "__main__":
    main()
