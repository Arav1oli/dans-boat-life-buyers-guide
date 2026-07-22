from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

COMPARISON_CUES = (
    "compared to", "different from", "maybe the", "remember that's", "similar to",
    "unlike", "you don't get that on", "you do not get that on",
)

ATTRIBUTE_GROUPS = {
    **{key: "dimensions" for key in ("length_feet", "beam_feet", "draft_feet", "air_draft_feet", "displacement_kg")},
    **{key: "performance" for key in ("top_speed_knots", "max_observed_speed_knots", "cruise_speed_knots", "range_nm")},
    **{key: "powertrain" for key in ("engine_power_hp", "engine_count", "drive_type")},
    **{key: "capacity" for key in ("fuel_capacity_l", "water_capacity_l")},
    **{key: "accommodation" for key in ("cabins", "berths", "heads", "galley", "separate_shower", "crew_cabin")},
    **{key: "hull" for key in ("hull_form",)},
    **{key: "mission" for key in ("offshore_capable", "trailerable", "great_loop_relevant", "overnight_capable", "family_suitable", "fishing_suitable", "watersports_suitable", "long_range_suitable")},
    **{key: "access" for key in ("hydraulic_swim_platform", "folding_balconies", "beach_club", "walkaround_decks", "side_boarding_door")},
    **{key: "weather" for key in ("enclosable_cockpit", "hardtop", "opening_sunroof")},
    **{key: "comfort" for key in ("air_conditioning",)},
    **{key: "systems" for key in ("generator", "solar", "watermaker", "gyro_stabiliser", "fin_stabilisers")},
    **{key: "handling" for key in ("joystick_control", "dynamic_positioning", "bow_thruster", "stern_thruster")},
    **{key: "storage" for key in ("tender_garage",)},
    **{key: "character" for key in ("premium_styling", "quiet_ride", "dry_ride")},
}


def display_value(tag: dict[str, Any]) -> str:
    if tag.get("value_boolean") is not None:
        return "true" if tag["value_boolean"] else "false"
    if tag.get("value_number") is not None:
        value = f"{float(tag['value_number']):g}"
        return f"{value} {tag.get('unit') or ''}".strip()
    return str(tag.get("value_text") or tag.get("value_key") or "")


def review_flags(profile: dict[str, Any], tag: dict[str, Any], value_counts: Counter) -> list[str]:
    flags = []
    key = tag["attribute_key"]
    if value_counts[key] > 1 and key in {"drive_type", "hull_form"}:
        flags.append("multiple_values_review")
    if tag.get("value_text") == "configuration-dependent":
        flags.append("configuration_dependent")
    excerpts = " ".join(item.get("evidence_text") or "" for item in tag.get("evidence", [])).lower()
    if any(cue in excerpts for cue in COMPARISON_CUES):
        flags.append("comparison_context_review")
    number = tag.get("value_number")
    length = float(profile["length_feet"])
    if key == "beam_feet" and number is not None and float(number) > length * 0.55:
        flags.append("numeric_sanity_review")
    if key == "fuel_capacity_l" and number is not None and length >= 20 and float(number) < 50:
        flags.append("numeric_sanity_review")
    if key in {"top_speed_knots", "max_observed_speed_knots"} and number is not None and float(number) < 10:
        flags.append("numeric_sanity_review")
    return sorted(set(flags))


def export(report_path: Path, long_path: Path, summary_path: Path, markdown_path: Path) -> dict[str, int]:
    report = json.loads(report_path.read_text())
    profiles = report["profiles"]
    long_rows = []
    summary_rows = []
    flag_counts = Counter()

    for profile in profiles:
        value_counts = Counter(tag["attribute_key"] for tag in profile["attributes"])
        source_ids = ";".join(video["id"] for video in profile["videos"])
        all_tags = []
        profile_flags = set()
        for category in profile["categories"]:
            evidence = category.get("evidence") or []
            long_rows.append({
                "canonical_key": profile["canonical_key"], "make": profile["make"], "model": profile["model"],
                "full_name": profile["full_name"], "length_feet": profile["length_feet"], "tag_type": "category",
                "tag_group": "category", "tag_key": category["category_key"], "tag_label": category["category_key"].replace("-", " ").title(),
                "tag_value": "true", "unit": "", "confidence": category["confidence"], "evidence_count": len(evidence),
                "source_video_ids": source_ids, "first_evidence_excerpt": evidence[0]["evidence_text"] if evidence else "", "review_flags": "",
            })
            all_tags.append(f"category:{category['category_key']}")
        for tag in profile["attributes"]:
            flags = review_flags(profile, tag, value_counts)
            flag_counts.update(flags)
            profile_flags.update(flags)
            evidence = tag.get("evidence") or []
            value = display_value(tag)
            long_rows.append({
                "canonical_key": profile["canonical_key"], "make": profile["make"], "model": profile["model"],
                "full_name": profile["full_name"], "length_feet": profile["length_feet"], "tag_type": "attribute",
                "tag_group": ATTRIBUTE_GROUPS.get(tag["attribute_key"], "other"), "tag_key": tag["attribute_key"], "tag_label": tag["attribute_key"].replace("_", " ").title(),
                "tag_value": value, "unit": tag.get("unit") or "", "confidence": tag["confidence"], "evidence_count": len(evidence),
                "source_video_ids": source_ids, "first_evidence_excerpt": evidence[0]["evidence_text"] if evidence else "", "review_flags": ";".join(flags),
            })
            all_tags.append(f"{tag['attribute_key']}={value}")
        summary_rows.append({
            "canonical_key": profile["canonical_key"], "make": profile["make"], "model": profile["model"],
            "full_name": profile["full_name"], "length_feet": profile["length_feet"], "source_video_count": len(profile["videos"]),
            "source_video_ids": source_ids, "tag_count": len(all_tags), "all_tags": " | ".join(all_tags),
            "review_flags": ";".join(sorted(profile_flags)),
        })

    long_path.parent.mkdir(parents=True, exist_ok=True)
    with long_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(long_rows[0]))
        writer.writeheader(); writer.writerows(long_rows)
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader(); writer.writerows(summary_rows)

    flagged_boats = sum(bool(row["review_flags"]) for row in summary_rows)
    lines = [
        "# Boat tag audit", "",
        "This export lists every category and attribute selected from the two power-boat playlist transcripts. Tags are evidence candidates, not hidden facts. Missing means not established in Dan's transcript, not false.", "",
        f"- Canonical boats: {len(profiles)}", f"- Source videos attached: {sum(len(profile['videos']) for profile in profiles)}",
        f"- Total selected tags: {len(long_rows)}", f"- Boats carrying at least one review flag: {flagged_boats}", "",
        "## Review flags", "",
        "| Flag | Tag rows | Meaning |", "|---|---:|---|",
        f"| comparison_context_review | {flag_counts['comparison_context_review']} | The excerpt may be comparing another boat rather than describing the subject boat. |",
        f"| multiple_values_review | {flag_counts['multiple_values_review']} | More than one drive or hull value was selected and needs configuration review. |",
        f"| numeric_sanity_review | {flag_counts['numeric_sanity_review']} | A number is possible but implausible enough to require checking against the timed excerpt. |",
        f"| configuration_dependent | {flag_counts['configuration_dependent']} | Positive and negative evidence was retained as configuration-dependent. |", "",
        "The buyer guide now avoids using flagged configuration and comparison tags as hard recommendation facts. The long-form CSV retains the timestamp evidence context for editorial review.",
    ]
    markdown_path.write_text("\n".join(lines) + "\n")
    return {"boats": len(profiles), "source_videos": sum(len(profile["videos"]) for profile in profiles), "tags": len(long_rows), "flagged_boats": flagged_boats}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export every transcript-derived boat tag with review flags")
    parser.add_argument("--input", default="data/reports/boat-taxonomy.json")
    parser.add_argument("--long", default="BOAT_TAG_AUDIT.csv")
    parser.add_argument("--summary", default="BOAT_TAGS_BY_BOAT.csv")
    parser.add_argument("--markdown", default="BOAT_TAG_AUDIT.md")
    args = parser.parse_args()
    result = export(Path(args.input), Path(args.long), Path(args.summary), Path(args.markdown))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
