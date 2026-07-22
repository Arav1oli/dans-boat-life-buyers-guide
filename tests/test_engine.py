from backend.engine import normalise_answers, score_boats


def answers(**values):
    return {key: {"value": value, "label": str(value)} for key, value in values.items()}


def test_trailer_requirement_excludes_non_trailerable_boats():
    results = score_boats(answers(storage="trailer"), limit=50)
    assert results
    assert all(boat["features"]["trailerable"] for boat in results)


def test_enclosed_helm_is_a_hard_requirement():
    results = score_boats(answers(helm="enclosed"), limit=50)
    assert results
    assert all(boat["features"]["helm"] == "enclosed" for boat in results)


def test_offshore_requirement_does_not_publish_coastal_only_boats():
    results = score_boats(answers(water="offshore"), limit=50)
    assert results
    assert all("offshore" in boat["features"]["use"] for boat in results)


def test_required_overnighting_has_at_least_two_berths():
    results = score_boats(answers(overnight="required"), limit=50)
    assert results
    assert all(boat["features"]["berths"] >= 2 for boat in results)


def test_length_preference_excludes_boats_more_than_four_feet_away():
    results = score_boats(answers(length="20-29"), limit=50)
    assert results
    assert all(16 <= boat["length_feet"] <= 33 for boat in results)
    in_range = [boat for boat in results if 20 <= boat["length_feet"] <= 29]
    assert in_range
    assert all("Falls inside your preferred length range" in boat["match_reasons"] for boat in in_range)


def test_results_include_evidence_links_and_scoring_breakdown():
    results = score_boats(answers(water="offshore", priority="exploring"))
    assert 0 < len(results) <= 5
    for boat in results:
        assert boat["make"] and boat["model"] and boat["length_feet"]
        assert boat["videos"]
        assert boat["transcript_attributes"]
        assert set(boat["score_breakdown"]) == {"use_case_fit", "evidence", "audience", "market"}


def test_day_party_and_sleeping_party_are_separate_hard_requirements():
    results = score_boats(answers(people="8", overnight="required", sleeping_people="4"), limit=50)
    assert results
    assert all(boat["features"]["day_capacity"] >= 8 for boat in results)
    assert all(boat["features"]["berths"] >= 4 for boat in results)


def test_required_overnight_facilities_must_be_confirmed_in_dans_transcript():
    results = score_boats(answers(overnight="required", sleeping_people="2", overnight_facilities="galley"), limit=50)
    assert results
    for boat in results:
        galley = next(item for item in boat["transcript_attributes"] if item["key"] == "galley")
        assert galley["value_boolean"] is True
        assert galley["confidence"] >= 0.88
        assert "Dan confirms a galley aboard" in boat["match_reasons"]


def test_specific_mission_fork_changes_the_shortlist():
    common = dict(water="coastal", people="4", overnight="none", helm="protected", storage="marina", length="30-34")
    family = score_boats(answers(**common, priority="family", mission_detail="protected-family-days"))
    fishing = score_boats(answers(**common, priority="fishing", mission_detail="coastal-fishing"))
    assert family and fishing
    assert [boat["full_name"] for boat in family] != [boat["full_name"] for boat in fishing]
    assert all("family" in boat["features"]["priorities"] for boat in family)
    assert all("fishing" in boat["features"]["priorities"] for boat in fishing)


def test_popularity_cannot_bypass_a_hard_requirement():
    results = score_boats(answers(storage="trailer", helm="enclosed", sleeping_people="2"), limit=50)
    assert results
    assert all(boat["features"]["trailerable"] for boat in results)
    assert all(boat["features"]["helm"] == "enclosed" for boat in results)
    assert all(boat["features"]["berths"] >= 2 for boat in results)


def test_inactive_overnight_answers_are_removed_after_day_use_edit():
    values = answers(overnight="none", sleeping_people="6", overnight_duration="extended", overnight_facilities="shower")
    normalised = normalise_answers(values)
    assert set(normalised) == {"overnight"}
