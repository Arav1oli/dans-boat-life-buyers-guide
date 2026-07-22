from etl.evidence import extract_claims, mission_profile
from etl.transcript_fallback import collapse_tandem_repeats, parse_markdown


def test_transcript_evidence_keeps_timestamp_and_dans_words():
    item = {
        "youtube_video_id": "demo",
        "title": "Demo boat",
        "transcript_segments": [
            {"start": 10, "duration": 3, "text": "Now let's look inside."},
            {"start": 13, "duration": 4, "text": "The enclosed wheelhouse gives proper weather protection."},
            {"start": 17, "duration": 3, "text": "That matters when the day turns."},
        ],
    }
    claims = extract_claims(item)
    weather = [claim for claim in claims if claim["topic"] == "weather_protection"]
    assert weather
    assert weather[0]["start_seconds"] == 10
    assert "proper weather protection" in weather[0]["evidence_text"]
    assert "exploring" in weather[0]["missions"]


def test_mission_profile_counts_distinct_evidence_topics():
    claims = [
        {"topic": "weather_protection", "missions": ["exploring"]},
        {"topic": "weather_protection", "missions": ["exploring"]},
        {"topic": "range_efficiency", "missions": ["exploring"]},
    ]
    profile = mission_profile(claims)
    assert profile["exploring"]["topics"] == ["range_efficiency", "weather_protection"]
    assert profile["exploring"]["fit_signal"] == 0.4


def test_fallback_parser_preserves_timestamps_and_removes_exact_caption_repeats():
    markdown = """# Transcript\n\n## Transcript\n[0:03] this boat is fun this boat is fun this boat is fun\n\n[0:10] offshore capability matters offshore capability matters\n---\nfooter"""
    segments = parse_markdown(markdown)
    assert segments[0] == {"sequence": 0, "start": 3, "duration": 7, "text": "this boat is fun"}
    assert segments[1]["text"] == "offshore capability matters"
    assert collapse_tandem_repeats("very very useful useful") == "very useful"
