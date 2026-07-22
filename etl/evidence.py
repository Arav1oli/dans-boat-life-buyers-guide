from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


# Transparent first-pass rules. These locate Dan's evidence; they do not invent
# conclusions. Public wording still requires an identity-complete paired boat.
TOPICS: dict[str, dict[str, Any]] = {
    "weather_protection": {
        "missions": ["exploring", "family"],
        "patterns": [r"weather protection", r"enclosed (?:helm|wheelhouse|saloon)", r"protected from", r"windshield", r"windscreen"],
    },
    "overnight_capability": {
        "missions": ["exploring", "family"],
        "patterns": [r"overnight", r"weekend(?:er|ing)?", r"double berth", r"sleep(?:ing|s)?\b", r"accommodation"],
    },
    "offshore_capability": {
        "missions": ["exploring", "fishing"],
        "patterns": [r"offshore", r"open ocean", r"rough water", r"heavy weather", r"sea keeping", r"seakeeping"],
    },
    "family_access": {
        "missions": ["family", "mixed-use"],
        "patterns": [r"family", r"kids", r"easy access", r"side door", r"walkaround", r"safe (?:access|for|walk|around)"],
    },
    "fishing_utility": {
        "missions": ["fishing"],
        "patterns": [r"fishing", r"rod holder", r"live ?well", r"bait", r"fish box", r"working cockpit"],
    },
    "watersports_access": {
        "missions": ["watersports", "family"],
        "patterns": [r"watersports?", r"wakeboard", r"water ski", r"swim platform", r"bathing platform", r"toys"],
    },
    "social_space": {
        "missions": ["family", "mixed-use"],
        "patterns": [r"entertain(?:ing|ment)", r"social space", r"seating", r"dining", r"galley", r"cockpit table"],
    },
    "handling": {
        "missions": ["exploring", "mixed-use"],
        "patterns": [r"handling", r"turning", r"(?:dry|soft|comfortable|smooth) ride", r"ride quality", r"helm response", r"maneuver", r"manoeuv", r"(?:through|into) (?:the )?(?:chop|waves|swell)"],
    },
    "range_efficiency": {
        "missions": ["exploring"],
        "patterns": [r"range", r"fuel burn", r"fuel economy", r"litres per", r"gallons per", r"cruising speed"],
    },
    "ownership_compromise": {
        "missions": ["mixed-use"],
        "patterns": [r"compromise", r"downside", r"drawback", r"worth knowing", r"keep in mind", r"not for everyone"],
    },
}

COMPILED = {
    topic: [re.compile(pattern, re.IGNORECASE) for pattern in definition["patterns"]]
    for topic, definition in TOPICS.items()
}


def extract_claims(item: dict[str, Any], max_per_topic: int = 5) -> list[dict[str, Any]]:
    segments = item.get("transcript_segments") or []
    claims: list[dict[str, Any]] = []
    topic_counts: defaultdict[str, int] = defaultdict(int)
    for index, segment in enumerate(segments):
        text = segment.get("text") or ""
        for topic, patterns in COMPILED.items():
            if topic_counts[topic] >= max_per_topic or not any(pattern.search(text) for pattern in patterns):
                continue
            # A small transcript window preserves context and a direct timestamp.
            start_index = max(index - 1, 0)
            end_index = min(index + 2, len(segments))
            window = segments[start_index:end_index]
            evidence_text = " ".join(row.get("text") or "" for row in window).strip()
            claims.append({
                "youtube_video_id": item["youtube_video_id"],
                "topic": topic,
                "missions": TOPICS[topic]["missions"],
                "start_seconds": float(window[0].get("start") or 0),
                "end_seconds": float((window[-1].get("start") or 0) + (window[-1].get("duration") or 0)),
                "evidence_text": evidence_text,
                "source_title": item.get("title") or "",
            })
            topic_counts[topic] += 1
    return claims


def mission_profile(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_mission: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        for mission in claim["missions"]:
            by_mission[mission].append(claim)
    profiles = {}
    for mission, evidence in by_mission.items():
        distinct_topics = sorted({claim["topic"] for claim in evidence})
        profiles[mission] = {
            "fit_signal": round(min(len(distinct_topics) / 5, 1), 3),
            "topics": distinct_topics,
            "evidence_count": len(evidence),
            "evidence": evidence[:8],
        }
    return profiles


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract timestamped mission evidence from saved Dan's Boat Life transcripts")
    parser.add_argument("--input", default="data/raw/youtube")
    parser.add_argument("--output", default="data/reports/transcript-evidence.json")
    args = parser.parse_args()

    videos = []
    failed = []
    for path in sorted(Path(args.input).glob("*.json")):
        item = json.loads(path.read_text())
        if not item.get("transcript_segments"):
            failed.append({"video_id": item.get("youtube_video_id"), "error": item.get("transcript_error") or "empty transcript"})
            continue
        claims = extract_claims(item)
        videos.append({
            "youtube_video_id": item["youtube_video_id"],
            "title": item.get("title"),
            "boat_identity": item.get("boat_identity"),
            "claims": claims,
            "mission_profiles": mission_profile(claims),
        })

    report = {"videos_with_transcripts": len(videos), "failed_transcripts": failed, "videos": videos}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({"videos_with_transcripts": len(videos), "failed_transcripts": len(failed), "claims": sum(len(v["claims"]) for v in videos)}, indent=2))


if __name__ == "__main__":
    main()
