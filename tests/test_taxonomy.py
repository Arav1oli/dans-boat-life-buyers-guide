import json

from etl.taxonomy import aggregate_attributes, extract_video, load_profiles


def record(text: str) -> dict:
    return {
        "youtube_video_id": "video-1",
        "transcript_segments": [{"sequence": 0, "start": 12, "duration": 30, "text": text}],
    }


def by_key(observations: list[dict], key: str) -> list[dict]:
    return [item for item in observations if item["attribute_key"] == key]


def test_extracts_numeric_specs_without_merging_claimed_and_observed_speed():
    observations, _ = extract_video(record(
        "Top speed is 42 knots, we are doing 39 knots and cruise at 28 knots. "
        "The range is 240 nautical miles with two cabins and 350 horsepower."
    ))
    assert by_key(observations, "top_speed_knots")[0]["value_number"] == 42
    assert by_key(observations, "max_observed_speed_knots")[0]["value_number"] == 39
    assert by_key(observations, "cruise_speed_knots")[0]["value_number"] == 28
    assert by_key(observations, "range_nm")[0]["value_number"] == 240
    assert by_key(observations, "cabins")[0]["value_number"] == 2
    assert by_key(observations, "engine_power_hp")[0]["value_number"] == 350


def test_keeps_explicit_absence_and_optional_equipment_qualified():
    observations, _ = extract_video(record(
        "This layout does not have the generator. "
        "You can option a hydraulic swim platform and it does have air conditioning downstairs."
    ))
    generator = by_key(observations, "generator")[0]
    platform = by_key(observations, "hydraulic_swim_platform")[0]
    aircon = by_key(observations, "air_conditioning")[0]
    assert generator["value_boolean"] is False
    assert platform["value_boolean"] is True
    assert platform["qualifier"] == "optional"
    assert aircon["value_boolean"] is True


def test_missing_feature_is_unknown_not_false():
    observations, _ = extract_video(record("There is a comfortable helm and a wide aft deck."))
    assert not by_key(observations, "generator")
    assert not by_key(observations, "hydraulic_swim_platform")


def test_conflicting_configurations_are_not_forced_to_boolean():
    observations = [
        {
            "attribute_key": "crew_cabin",
            "value_key": "primary",
            "value_type": "boolean",
            "value_boolean": True,
            "value_number": None,
            "value_text": None,
            "unit": None,
            "video_id": "a",
            "start_seconds": 1,
            "confidence": 0.95,
        },
        {
            "attribute_key": "crew_cabin",
            "value_key": "primary",
            "value_type": "boolean",
            "value_boolean": False,
            "value_number": None,
            "value_text": None,
            "unit": None,
            "video_id": "b",
            "start_seconds": 2,
            "confidence": 0.95,
        },
    ]
    value = aggregate_attributes(observations)[0]
    assert value["value_boolean"] is None
    assert value["value_text"] == "configuration-dependent"


def test_companion_model_labels_collapse_to_one_canonical_boat(tmp_path):
    base = {
        "description": "",
        "youtube_url": "https://youtube.example/video",
        "view_count": 1,
        "comment_count": 1,
        "transcript_segments": [{"sequence": 0, "start": 0, "duration": 10, "text": "This is a sports cruiser."}],
    }
    first = {
        **base,
        "youtube_video_id": "one",
        "title": "Riviera 58 Sports Motor Yacht",
        "playlists": [{"video_type": "walkthrough"}],
        "boat_identity": {
            "make": "Riviera",
            "model": "58 SPORTS MOTOR YACHT",
            "full_name": "Riviera 58 Sports Motor Yacht",
            "length_feet": 58,
            "confidence": 0.95,
            "method": "test",
        },
    }
    second = {
        **base,
        "youtube_video_id": "two",
        "title": "Riviera 58 SMY",
        "playlists": [{"video_type": "test_drive"}],
        "boat_identity": {
            "make": "Riviera",
            "model": "58 SMY",
            "full_name": "Riviera 58 SMY",
            "length_feet": 58,
            "confidence": 0.96,
            "method": "test",
        },
    }
    (tmp_path / "one.json").write_text(json.dumps(first))
    (tmp_path / "two.json").write_text(json.dumps(second))
    profiles = load_profiles(tmp_path)
    assert len(profiles) == 1
    assert len(profiles[0]["videos"]) == 2
    assert profiles[0]["canonical_key"] == "riviera 58 smy"
