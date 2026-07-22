from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "guide" / "data" / "boats.json"


def load_boats() -> list[dict[str, Any]]:
    return json.loads(DATA_PATH.read_text())


def _selected(answers: dict[str, Any], key: str) -> str | None:
    value = answers.get(key)
    if isinstance(value, dict):
        return value.get("value")
    return value if isinstance(value, str) else None


def score_boats(answers: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    overnight = _selected(answers, "overnight")
    helm = _selected(answers, "helm")
    storage = _selected(answers, "storage")
    water = _selected(answers, "water")
    priority = _selected(answers, "priority")
    length = _selected(answers, "length")
    people_value = _selected(answers, "people")
    people = int(people_value) if people_value and people_value.isdigit() else 4

    for boat in load_boats():
        features = boat["features"]
        exclusions: list[str] = []
        if overnight == "required" and features["berths"] < 2:
            exclusions.append("No practical overnight accommodation")
        if people > features["day_capacity"]:
            exclusions.append("Below your normal passenger requirement")
        if storage == "trailer" and not features["trailerable"]:
            exclusions.append("Not realistically trailerable")
        if helm == "enclosed" and features["helm"] != "enclosed":
            exclusions.append("Does not provide the enclosed helm you selected")
        if water == "offshore" and features["use"] not in {"offshore", "coastal-offshore"}:
            exclusions.append("Not supported by the current evidence for offshore use")
        if exclusions:
            continue

        score = 0.0
        reasons: list[str] = []
        if overnight == "required" and features["berths"] >= 2:
            score += 20
            reasons.append(f"Provides overnight accommodation for {features['berths']}")
        elif overnight == "optional" and features["berths"]:
            score += 12
            reasons.append("Keeps weekending open without making it the whole boat")
        elif overnight == "none" and features["berths"] == 0:
            score += 12
            reasons.append("Purposeful day-boat layout without unused accommodation")

        if helm and features["helm"] == helm:
            score += 14
            reasons.append(f"Matches your {helm.replace('-', ' ')} helm preference")
        if water and water in features["use"]:
            score += 18
            reasons.append(f"Evidence supports the {water} use you selected")
        if priority and priority in features["priorities"]:
            score += 18
            reasons.append(f"Strong fit for {priority.replace('-', ' ')} use")
        if storage == "trailer" and features["trailerable"]:
            score += 12
            reasons.append("Fits a trailering requirement")
        if length:
            low, high = map(float, length.split("-"))
            if low <= boat["length_feet"] <= high:
                score += 10
                reasons.append("Falls inside your preferred length range")

        evidence = float(boat["evidence_confidence"])
        audience = float(boat["audience_percentile"])
        market = float(boat.get("market_percentile") or 0.5)
        final = min(score / 92.0, 1.0) * 0.55 + evidence * 0.20 + audience * 0.15 + market * 0.10
        scored.append({
            **boat,
            "total_score": round(final, 5),
            "score_breakdown": {
                "use_case_fit": round(min(score / 92.0, 1.0), 4),
                "evidence": evidence,
                "audience": audience,
                "market": market,
            },
            "match_reasons": reasons[:3],
        })

    scored.sort(key=lambda item: item["total_score"], reverse=True)
    return scored[:limit]
