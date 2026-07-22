from pathlib import Path

import pytest

from etl.matcher import SalesCatalogue, pair_key


SALES_DB = Path("/Users/adrianstock/Documents/Codex/2026-07-16/running-on-this-device-claude-is/outputs/soldboats_full_pass/soldboats_full_structured.sqlite")


@pytest.fixture(scope="module")
def catalogue():
    if not SALES_DB.exists():
        pytest.skip("read-only sold-boats catalogue is not mounted")
    return SalesCatalogue(SALES_DB)


@pytest.mark.parametrize(
    ("title", "expected_make", "model_fragment", "expected_length"),
    [
        ("The Mighty Little Explorer - Sargo 28", "Sargo", "28", 28),
        ("Jeanneau Merry Fisher 795 Sport full review", "Jeanneau", "795", 26.08),
        ("Loaded with gear! Aiata Wayfinder 38", "Aiata", "38", 38),
        ("Tesoro T50 sea trial", "Tesoro", "T50", 50),
    ],
)
def test_identity_uses_title_and_sales_catalogue(catalogue, title, expected_make, model_fragment, expected_length):
    identity = catalogue.match(title, "")
    assert identity.make == expected_make
    assert model_fragment.lower() in identity.model.lower()
    assert identity.length_feet == pytest.approx(expected_length, abs=0.05)
    assert pair_key(identity)


def test_description_can_supply_identity(catalogue):
    identity = catalogue.match("Full walkthrough", "We step aboard the Sargo 28 and inspect the whole boat.")
    assert identity.make == "Sargo"
    assert "28" in identity.model
    assert identity.length_feet == 28


@pytest.mark.parametrize(
    ("title", "full_name", "length"),
    [
        ("A Boat for Serious Boaters - The Sargo 45", "Sargo 45", 45),
        ("Buy 320 GTC NOW... or wait for 340 GTWA? Saxdor 320 GTC Walkthrough", "Saxdor 320 GTC", 32),
        ("WATCH before you buy a CENTRE CONSOLE! The Wellcraft 355", "Wellcraft 355", 35.5),
        ("2022 Nimbus C11 - Detailed WALKTHROUGH", "Nimbus C11", 40.7),
        ("2021 XO DFNDR 8 - Detailed Walkthrough", "XO DFNDR 8", 26.25),
        ("Riviera 645 SUV full walkthrough", "Riviera 645 SUV", 64.5),
        ("Iron 907 Coupe first look", "Iron 907 COUPE", 29.76),
        ("Majesty 111 sea trial", "Majesty 111", 111),
    ],
)
def test_explicit_title_model_beats_incidental_description_numbers(catalogue, title, full_name, length):
    identity = catalogue.match(title, "A competitor 43 and a 400 horsepower engine are mentioned later.")
    assert identity.full_name == full_name
    assert identity.length_feet == pytest.approx(length, abs=0.1)
