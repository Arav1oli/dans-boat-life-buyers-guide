from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "guide" / "data" / "boats.json"


MISSION_DETAIL_VALUES = {
    "family": {"protected-family-days", "easy-water-access", "family-weekends", "room-for-friends"},
    "fishing": {"offshore-fishing", "coastal-fishing", "walkaround-fishing", "short-handed-fishing"},
    "watersports": {"water-access", "social-anchor", "all-weather-active", "fast-day-runs"},
    "exploring": {"all-weather-exploring", "range-autonomy", "short-handed-exploring", "weekend-exploring"},
    "mixed-use": {"protection-balance", "mixed-water-access", "overnight-option", "social-space"},
}


def load_boats() -> list[dict[str, Any]]:
    return json.loads(DATA_PATH.read_text())


def _selected(answers: dict[str, Any], key: str) -> str | None:
    value = answers.get(key)
    if isinstance(value, dict):
        selected = value.get("value")
        return str(selected) if selected is not None else None
    return str(value) if value is not None else None


def normalise_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Remove answers that are no longer active after an earlier answer changes."""
    normalised = dict(answers)
    if _selected(normalised, "overnight") == "none":
        for key in ("sleeping_people", "overnight_duration", "overnight_facilities"):
            normalised.pop(key, None)
    priority = _selected(normalised, "priority")
    detail = _selected(normalised, "mission_detail")
    if detail and detail not in MISSION_DETAIL_VALUES.get(priority or "", set()):
        normalised.pop("mission_detail", None)
    return normalised


def _transcript_tags(boat: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [item for item in boat.get("transcript_attributes", []) if item["key"] == key]


def _transcript_tag(boat: dict[str, Any], key: str, value_key: str = "primary") -> dict[str, Any] | None:
    return next((item for item in _transcript_tags(boat, key) if item.get("value_key", "primary") == value_key), None)


def _positive_transcript_tag(boat: dict[str, Any], key: str, confidence: float = 0.82) -> bool:
    tag = _transcript_tag(boat, key)
    return bool(tag and tag.get("value_boolean") is True and float(tag.get("confidence") or 0) >= confidence)


def _numeric_transcript_tag(boat: dict[str, Any], key: str, confidence: float = 0.88) -> float | None:
    tag = _transcript_tag(boat, key)
    if not tag or tag.get("value_number") is None or float(tag.get("confidence") or 0) < confidence:
        return None
    return float(tag["value_number"])


def _category(boat: dict[str, Any], key: str, confidence: float = 0.90) -> bool:
    return any(item["key"] == key and float(item.get("confidence") or 0) >= confidence for item in boat.get("candidate_categories", []))


def _access_signal(boat: dict[str, Any]) -> bool:
    return any(
        _positive_transcript_tag(boat, key, 0.90)
        for key in ("hydraulic_swim_platform", "folding_balconies", "beach_club", "side_boarding_door")
    ) or _category(boat, "luxury-med-day-boat")


def _control_signal(boat: dict[str, Any]) -> bool:
    return any(
        _positive_transcript_tag(boat, key, 0.90)
        for key in ("joystick_control", "dynamic_positioning", "bow_thruster", "stern_thruster")
    )


def _range_signal(boat: dict[str, Any]) -> bool:
    return _positive_transcript_tag(boat, "long_range_suitable", 0.88) or (
        _positive_transcript_tag(boat, "generator", 0.90) and _positive_transcript_tag(boat, "galley", 0.88)
    )


def _speed_signal(boat: dict[str, Any]) -> bool:
    speed = _numeric_transcript_tag(boat, "max_observed_speed_knots") or _numeric_transcript_tag(boat, "top_speed_knots")
    return bool(speed and 28 <= speed <= 80)


def _mission_detail_match(boat: dict[str, Any], detail: str | None) -> tuple[bool, str]:
    features = boat["features"]
    helm = features["helm"]
    use = features["use"]
    rules: dict[str, tuple[bool, str]] = {
        "protected-family-days": (helm in {"protected", "enclosed"}, "Protection for regular family days"),
        "easy-water-access": (_access_signal(boat), "Transcript-backed access to the water"),
        "family-weekends": (features["berths"] >= 2, "Practical family weekending capability"),
        "room-for-friends": (features["day_capacity"] >= 8, "Capacity for a larger regular group"),
        "offshore-fishing": ("offshore" in use and "fishing" in features["priorities"], "Offshore capability with a fishing mission"),
        "coastal-fishing": ("fishing" in features["priorities"], "A practical coastal fishing mission"),
        "walkaround-fishing": (_positive_transcript_tag(boat, "walkaround_decks", 0.88) or _category(boat, "centre-console"), "Dan discusses practical walkaround movement"),
        "short-handed-fishing": (_control_signal(boat), "Controls suited to short-handed manoeuvring"),
        "water-access": (_access_signal(boat), "Transcript-backed water access"),
        "social-anchor": (features["day_capacity"] >= 9 or _positive_transcript_tag(boat, "folding_balconies", 0.90), "Room for social days at anchor"),
        "all-weather-active": (helm in {"protected", "enclosed"}, "Weather protection without giving up active use"),
        "fast-day-runs": (_speed_signal(boat), "Dan's test evidence supports fast day runs"),
        "all-weather-exploring": (helm in {"protected", "enclosed"} and "offshore" in use, "Protected helm and open-water capability"),
        "range-autonomy": (_range_signal(boat), "Transcript evidence supports greater range or autonomy"),
        "short-handed-exploring": (_control_signal(boat), "Controls support short-handed exploring"),
        "weekend-exploring": (features["berths"] >= 2, "Overnight capability for weekend exploring"),
        "protection-balance": (helm in {"protected", "enclosed"}, "A useful balance of protection and day use"),
        "mixed-water-access": (_access_signal(boat), "Good water access for mixed use"),
        "overnight-option": (features["berths"] >= 2, "Keeps overnight trips available"),
        "social-space": (features["day_capacity"] >= 9 or _positive_transcript_tag(boat, "folding_balconies", 0.90), "A stronger social-space fit"),
    }
    return rules.get(detail or "", (True, "Matches the way you described the mission"))


def score_boats(answers: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    answers = normalise_answers(answers)
    scored: list[dict[str, Any]] = []
    overnight = _selected(answers, "overnight")
    sleeping_value = _selected(answers, "sleeping_people")
    sleeping_people = int(sleeping_value) if sleeping_value and sleeping_value.isdigit() else 0
    overnight_duration = _selected(answers, "overnight_duration")
    overnight_facilities = _selected(answers, "overnight_facilities")
    helm = _selected(answers, "helm")
    storage = _selected(answers, "storage")
    water = _selected(answers, "water")
    priority = _selected(answers, "priority")
    mission_detail = _selected(answers, "mission_detail")
    length = _selected(answers, "length")
    people_value = _selected(answers, "people")
    people = int(people_value) if people_value and people_value.isdigit() else 0

    for boat in load_boats():
        features = boat["features"]
        exclusions: list[str] = []
        if people and people > features["day_capacity"]:
            exclusions.append("Below your normal day-party requirement")
        if overnight == "required" and features["berths"] < 2:
            exclusions.append("No reliable overnight accommodation")
        if sleeping_people and features["berths"] < sleeping_people:
            exclusions.append("Not enough sleeping berths for your overnight party")
        if overnight_duration == "extended" and not _range_signal(boat):
            exclusions.append("No reliable transcript evidence for extended autonomy")
        if overnight_facilities == "galley" and not _positive_transcript_tag(boat, "galley", 0.88):
            exclusions.append("A galley is not confirmed in Dan's transcript")
        if overnight_facilities == "shower" and not _positive_transcript_tag(boat, "separate_shower", 0.90):
            exclusions.append("A separate shower is not confirmed in Dan's transcript")
        if storage == "trailer" and not features["trailerable"]:
            exclusions.append("Not realistically trailerable")
        if helm == "enclosed" and features["helm"] != "enclosed":
            exclusions.append("Does not provide the enclosed helm you selected")
        if helm == "protected" and features["helm"] == "open":
            exclusions.append("Does not provide the weather protection you selected")
        if helm == "open" and features["helm"] == "enclosed":
            exclusions.append("The helm is more enclosed than the open layout you selected")
        if water == "offshore" and "offshore" not in features["use"]:
            exclusions.append("Not supported by current evidence for regular offshore use")
        if water == "coastal" and not any(value in features["use"] for value in ("coastal", "offshore")):
            exclusions.append("Not supported by current evidence for regular coastal use")
        if priority and priority != "mixed-use" and priority not in features["priorities"]:
            exclusions.append("The editorial mission profile does not support your main use")
        if priority == "mixed-use" and len(features["priorities"]) < 2:
            exclusions.append("Too specialised for the mixed mission you selected")
        detail_match, detail_reason = _mission_detail_match(boat, mission_detail)
        if mission_detail and not detail_match:
            exclusions.append("Does not meet the specific mission fork you selected")
        if length and length != "unspecified":
            low, high = map(float, length.split("-"))
            if boat["length_feet"] < low - 4 or boat["length_feet"] > high + 4:
                exclusions.append("Too far outside your practical length range")
        if exclusions:
            continue

        earned = 0.0
        possible = 0.0
        reasons: list[str] = []

        def award(points: float, fraction: float, reason: str | None = None) -> None:
            nonlocal earned, possible
            possible += points
            earned += points * max(0.0, min(fraction, 1.0))
            if reason and fraction >= 0.72:
                reasons.append(reason)

        if people:
            award(8, 1 if features["day_capacity"] >= people else 0, f"Carries your usual day party of {people}")
        if overnight:
            if overnight == "none":
                award(12, 1 if features["berths"] == 0 else 0.38, "A purposeful day-boat layout" if features["berths"] == 0 else None)
            elif overnight == "optional":
                award(12, 1 if features["berths"] >= max(sleeping_people, 2) else 0.25, "Keeps occasional overnighting open")
            else:
                award(12, 1, "Provides the overnight capability you require")
        if sleeping_people:
            award(16, 1, f"Provides sleeping capacity for {sleeping_people}")
        if overnight_duration:
            duration_fit = 1 if overnight_duration in {"occasional", "weekend"} else (1 if _range_signal(boat) else 0)
            award(9, duration_fit, "Transcript evidence supports longer stays" if overnight_duration == "extended" else "Suits the trip length you selected")
        if overnight_facilities:
            facility_fit = {
                "basic": features["berths"] >= 2,
                "galley": _positive_transcript_tag(boat, "galley", 0.88),
                "shower": _positive_transcript_tag(boat, "separate_shower", 0.90),
            }.get(overnight_facilities, True)
            facility_reason = {"basic": "A practical berth without unnecessary systems", "galley": "Dan confirms a galley aboard", "shower": "Dan confirms a separate shower"}.get(overnight_facilities)
            award(10, 1 if facility_fit else 0, facility_reason)
        if helm:
            helm_fraction = 1 if features["helm"] == helm else (0.82 if helm == "protected" and features["helm"] == "enclosed" else 0.68)
            award(13, helm_fraction, f"Matches your {helm.replace('-', ' ')} helm requirement")
        if water:
            water_fit = 1 if water in features["use"] else (0.78 if water == "sheltered" else 0)
            award(14, water_fit, f"Evidence supports the {water} use you selected")
        if priority:
            mission_fit = 1 if priority in features["priorities"] else (0.88 if priority == "mixed-use" else 0)
            award(15, mission_fit, f"Editorial mission profile supports {priority.replace('-', ' ')}")
        if mission_detail:
            award(13, 1 if detail_match else 0, detail_reason)
        if storage:
            storage_fit = 1 if storage != "trailer" or features["trailerable"] else 0
            award(8, storage_fit, "Fits the trailering requirement" if storage == "trailer" else "Compatible with the storage plan you selected")
        if length and length != "unspecified":
            low, high = map(float, length.split("-"))
            exact = low <= boat["length_feet"] <= high
            award(11, 1 if exact else 0.55, "Falls inside your preferred length range" if exact else "A nearby size worth comparing")

        fit = earned / possible if possible else 0.5
        evidence = float(boat["evidence_confidence"])
        audience = float(boat["audience_percentile"])
        market = float(boat.get("market_percentile") or 0.5)
        # Buyer choices now control 82% of the result. Audience and sales data
        # only separate boats that already meet the buyer's actual brief.
        final = fit * 0.82 + evidence * 0.10 + audience * 0.04 + market * 0.04
        preferred_reasons = []
        if mission_detail:
            preferred_reasons.append(detail_reason)
        if sleeping_people:
            preferred_reasons.append(f"Provides sleeping capacity for {sleeping_people}")
        if overnight_facilities:
            preferred_reasons.append({"basic": "A practical berth without unnecessary systems", "galley": "Dan confirms a galley aboard", "shower": "Dan confirms a separate shower"}[overnight_facilities])
        if water:
            preferred_reasons.append(f"Evidence supports the {water} use you selected")
        match_reasons = list(dict.fromkeys(preferred_reasons + reasons))[:4]
        scored.append({
            **boat,
            "total_score": round(final, 5),
            "score_breakdown": {
                "use_case_fit": round(fit, 4),
                "evidence": evidence,
                "audience": audience,
                "market": market,
            },
            "match_reasons": match_reasons,
        })

    scored.sort(key=lambda item: item["total_score"], reverse=True)
    return scored[:limit]
