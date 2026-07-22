from backend.engine import score_boats


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


def test_length_preference_is_explainable_not_a_hard_filter():
    results = score_boats(answers(length="20-29"), limit=50)
    in_range = [boat for boat in results if 20 <= boat["length_feet"] <= 29]
    assert in_range
    assert all("Falls inside your preferred length range" in boat["match_reasons"] for boat in in_range)


def test_results_include_evidence_links_and_scoring_breakdown():
    results = score_boats(answers(water="offshore", priority="exploring"))
    assert 0 < len(results) <= 5
    for boat in results:
        assert boat["make"] and boat["model"] and boat["length_feet"]
        assert boat["videos"]
        assert set(boat["score_breakdown"]) == {"use_case_fit", "evidence", "audience", "market"}
