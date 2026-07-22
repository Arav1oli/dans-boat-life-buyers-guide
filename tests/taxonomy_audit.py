from collections import Counter

from etl.taxonomy import ATTRIBUTE_DEFINITIONS, CATEGORY_DEFINITIONS, NUMERIC_RANGES, load_profiles


def main() -> None:
    profiles = load_profiles("data/raw/youtube")
    assert len(profiles) == 209
    assert sum(len(profile["videos"]) for profile in profiles) == 398
    assert sum(profile["transcript_segments"] for profile in profiles) == 53177
    assert all(profile["make"] and profile["model"] and profile["length_feet"] for profile in profiles)
    assert all(any(value["attribute_key"] == "length_feet" for value in profile["attributes"]) for profile in profiles)

    attribute_keys = {definition.key for definition in ATTRIBUTE_DEFINITIONS}
    category_keys = {definition.key for definition in CATEGORY_DEFINITIONS}
    attribute_counts = Counter()
    category_counts = Counter()
    for profile in profiles:
        for value in profile["attributes"]:
            assert value["attribute_key"] in attribute_keys
            assert 0 <= value["confidence"] <= 1
            attribute_counts[value["attribute_key"]] += 1
            if value["value_number"] is not None and value["attribute_key"] in NUMERIC_RANGES:
                low, high = NUMERIC_RANGES[value["attribute_key"]]
                assert low <= value["value_number"] <= high
        for category in profile["categories"]:
            assert category["category_key"] in category_keys
            assert category["evidence"]
            assert 0 <= category["confidence"] <= 1
            category_counts[category["category_key"]] += 1

    assert len(ATTRIBUTE_DEFINITIONS) == 51
    assert len(CATEGORY_DEFINITIONS) == 20
    assert attribute_counts["drive_type"] >= 150
    assert attribute_counts["max_observed_speed_knots"] >= 85
    assert category_counts["walkaround-day-boat"] >= 90
    print({
        "canonical_boats": len(profiles),
        "source_videos": sum(len(profile["videos"]) for profile in profiles),
        "transcript_segments": sum(profile["transcript_segments"] for profile in profiles),
        "attribute_values": sum(attribute_counts.values()),
        "category_assignments": sum(category_counts.values()),
    })


if __name__ == "__main__":
    main()
