from collections import Counter
from itertools import product

from backend.engine import MISSION_DETAIL_VALUES, score_boats


def answers(**values):
    return {key: {"value": value, "label": str(value)} for key, value in values.items()}


def test_meaningful_answer_combinations_do_not_collapse_to_the_same_boats():
    appearances = Counter()
    top_winners = Counter()
    shortlist_signatures = set()
    nonempty = 0

    combinations = product(
        MISSION_DETAIL_VALUES,
        ("sheltered", "coastal", "offshore"),
        ("none", "required"),
        ("open", "protected", "enclosed"),
        ("trailer", "marina"),
        ("20-29", "30-34", "35-39", "40-50"),
    )
    for priority, water, overnight, helm, storage, length in combinations:
        for detail in MISSION_DETAIL_VALUES[priority]:
            values = {
                "priority": priority, "mission_detail": detail, "water": water,
                "overnight": overnight, "people": "4", "helm": helm,
                "storage": storage, "length": length,
            }
            if overnight == "required":
                values.update(sleeping_people="2", overnight_duration="weekend", overnight_facilities="basic")
            results = score_boats(answers(**values))
            if not results:
                continue
            nonempty += 1
            names = tuple(boat["full_name"] for boat in results)
            shortlist_signatures.add(names)
            top_winners[names[0]] += 1
            appearances.update(names)

    assert nonempty > 1_000
    assert len(shortlist_signatures) >= 50
    assert len(top_winners) >= 10
    assert len(appearances) == 15
    assert top_winners.most_common(1)[0][1] / nonempty < 0.25
