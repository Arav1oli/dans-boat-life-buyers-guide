from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from etl.evidence import COMPILED, extract_claims
from etl.matcher import normalise
from etl.sales import model_summary, readonly_connection


def percentile(value: float, population: list[float]) -> float:
    if not population:
        return 0.5
    return round(sum(item <= value for item in population) / len(population), 4)


def identity_is_explicit(boat: dict, item: dict) -> bool:
    source = normalise(f"{item.get('title', '')} {item.get('description', '')[:600]}")
    compact_source = re.sub(r"[^a-z0-9]", "", source)
    compact_make = re.sub(r"[^a-z0-9]", "", normalise(boat["make"]))
    compact_model = re.sub(r"[^a-z0-9]", "", normalise(boat["model"]))
    # Builders are inconsistent about spaces in model names (for example,
    # "900 ST" versus "900ST").  A compact, ordered match is still explicit
    # while avoiding fuzzy identity inference at the publication gate.
    if compact_make in compact_source and compact_model in compact_source:
        return True
    make_tokens = normalise(boat["make"]).split()
    model_tokens = normalise(boat["model"]).split()
    significant_model = [token for token in model_tokens if any(char.isdigit() for char in token)]
    return all(token in source.split() for token in make_tokens) and bool(significant_model) and all(token in source.split() for token in significant_model)


def short_excerpt(text: str, topic: str, words: int = 18) -> str:
    """Keep the matched phrase in a short, verbatim, transcript excerpt."""
    match = next((pattern.search(text) for pattern in COMPILED[topic] if pattern.search(text)), None)
    spans = list(re.finditer(r"\S+", text))
    if not spans:
        return ""
    focus = match.start() if match else 0
    focus_index = next((index for index, token in enumerate(spans) if token.end() >= focus), 0)
    start = max(focus_index - 4, 0)
    end = min(start + words, len(spans))
    excerpt = " ".join(token.group(0) for token in spans[start:end])
    return ("…" if start else "") + excerpt + ("…" if end < len(spans) else "")


def claim_quality(claim: dict) -> float:
    """Prefer specific assessments over intros while keeping selection deterministic."""
    text = claim["evidence_text"].lower()
    assessment_cues = (
        "comfortable", "compromise", "dry ride", "efficient", "excellent", "feels",
        "fuel", "good", "great", "handles", "practical", "protected", "responsive",
        "rough", "safe", "smooth", "stable", "works", "wouldn't", "won't",
    )
    filler_cues = ("i'm just going", "my name is", "subscribe", "thanks for watching", "welcome to", "we're going to")
    score = sum(1.0 for cue in assessment_cues if cue in text)
    score -= sum(2.0 for cue in filler_cues if cue in text)
    score += min(len(re.findall(r"\b\d+(?:\.\d+)?\b", text)), 2) * 0.25
    score += min(float(claim["start_seconds"]) / 600.0, 1.0) * 0.35
    if len(text.split()) < 12:
        score -= 3.0
    return score


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and enrich the editorial Adventure Boat launch catalogue")
    parser.add_argument("--raw", default="data/raw/youtube")
    parser.add_argument("--boats", default="guide/data/boats.json")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--report", default="data/reports/guide-catalog-validation.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    raw = {path.stem: json.loads(path.read_text()) for path in Path(args.raw).glob("*.json")}
    boats = json.loads(Path(args.boats).read_text())
    all_views = [math.log1p(item.get("view_count") or 0) for item in raw.values()]
    all_comments = [math.log1p(item.get("comment_count") or 0) for item in raw.values()]
    failures = []
    sold_counts = []

    with readonly_connection(args.sales_db) as sales:
        for boat in boats:
            global_market = model_summary(sales, boat["make"], boat["model"], 120)
            au_market = model_summary(sales, boat["make"], boat["model"], 120, "AU")
            sold_count = int(global_market[0] or 0)
            sold_counts.append(sold_count)
            boat["market"] = {
                "period_months": 120,
                "global_sold_count": sold_count,
                "median_sold_price_aud": global_market[1],
                "average_days_on_market": global_market[2],
                "australia_sold_count": int(au_market[0] or 0),
                "price_basis": "sold_price_aud",
            }

            video_items = []
            for video in boat["videos"]:
                item = raw.get(video["id"])
                if not item:
                    failures.append({"boat": boat["full_name"], "video_id": video["id"], "reason": "video not captured"})
                    continue
                expected_type = "test_drive" if video["type"].lower().startswith("test") else "walkthrough"
                actual_types = {membership["video_type"] for membership in item["playlists"]}
                if expected_type not in actual_types:
                    failures.append({"boat": boat["full_name"], "video_id": video["id"], "reason": f"not in {expected_type} playlist"})
                if not identity_is_explicit(boat, item):
                    failures.append({"boat": boat["full_name"], "video_id": video["id"], "reason": "make/model not explicit in title or description"})
                if not item.get("transcript_segments"):
                    failures.append({"boat": boat["full_name"], "video_id": video["id"], "reason": "transcript unavailable"})
                video["title"] = item.get("title") or video.get("title")
                video_items.append(item)

            if video_items:
                view_signal = sum(math.log1p(item.get("view_count") or 0) for item in video_items) / len(video_items)
                comment_signal = sum(math.log1p(item.get("comment_count") or 0) for item in video_items) / len(video_items)
                boat["audience_percentile"] = round(
                    percentile(view_signal, all_views) * 0.8 + percentile(comment_signal, all_comments) * 0.2,
                    4,
                )
                boat["engagement"] = {
                    "views": sum(item.get("view_count") or 0 for item in video_items),
                    "comments": sum(item.get("comment_count") or 0 for item in video_items),
                    "top_comments_captured": sum(len(item.get("comments") or []) for item in video_items),
                }
                claims = [claim for item in video_items for claim in extract_claims(item)]
                priorities = set(boat["features"]["priorities"])
                relevant = [claim for claim in claims if priorities.intersection(claim["missions"])] or claims
                selected = []
                seen_topics = set()
                seen_videos = set()
                for claim in sorted(relevant, key=lambda row: (-claim_quality(row), row["start_seconds"])):
                    if claim["topic"] in seen_topics or claim["youtube_video_id"] in seen_videos:
                        continue
                    seen_topics.add(claim["topic"])
                    seen_videos.add(claim["youtube_video_id"])
                    selected.append({
                        "topic": claim["topic"],
                        "start_seconds": round(claim["start_seconds"]),
                        "excerpt": short_excerpt(claim["evidence_text"], claim["topic"]),
                        "video_id": claim["youtube_video_id"],
                        "url": f"https://www.youtube.com/watch?v={claim['youtube_video_id']}&t={round(claim['start_seconds'])}s",
                    })
                    if len(selected) == 2:
                        break
                boat["evidence"] = selected
                boat["evidence_confidence"] = round(min(0.65 + len(selected) * 0.06 + (0.08 if len(video_items) >= 2 else 0), 0.97), 3)

    for boat, sold_count in zip(boats, sold_counts):
        boat["market_percentile"] = percentile(sold_count, sold_counts) if sold_count else 0.2

    report = {
        "candidate_boats": len(boats),
        "source_videos": sum(len(boat["videos"]) for boat in boats),
        "publishable_boats": len(boats) - len({failure["boat"] for failure in failures}),
        "failures": failures,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    if args.write:
        if failures:
            raise SystemExit(f"Refusing to publish: {len(failures)} catalogue validation failures")
        Path(args.boats).write_text(json.dumps(boats, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
