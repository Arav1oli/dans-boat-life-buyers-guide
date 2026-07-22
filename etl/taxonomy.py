from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from etl.matcher import BoatIdentity, NON_BOAT_OUTLIERS, normalise, pair_key


@dataclass(frozen=True)
class AttributeDefinition:
    key: str
    group: str
    label: str
    value_type: str
    unit: str | None
    description: str
    decision_use: str


@dataclass(frozen=True)
class CategoryDefinition:
    key: str
    label: str
    family: str
    description: str
    status: str


ATTRIBUTE_DEFINITIONS = (
    AttributeDefinition("length_feet", "dimensions", "Length", "number", "ft", "Canonical model length.", "Size, berthing and handling."),
    AttributeDefinition("beam_feet", "dimensions", "Beam", "number", "ft", "Beam stated in Dan's transcript.", "Marina, trailering and usable volume."),
    AttributeDefinition("draft_feet", "dimensions", "Draft", "number", "ft", "Water draft stated in Dan's transcript.", "Shallow water and cruising grounds."),
    AttributeDefinition("air_draft_feet", "dimensions", "Air draft", "number", "ft", "Bridge-clearance height stated in Dan's transcript.", "Great Loop and fixed-bridge routes."),
    AttributeDefinition("displacement_kg", "dimensions", "Displacement", "number", "kg", "Weight or displacement stated in Dan's transcript.", "Trailering, ride and transport."),
    AttributeDefinition("top_speed_knots", "performance", "Claimed top speed", "number", "kn", "Explicit top or maximum speed claim.", "Performance qualification."),
    AttributeDefinition("max_observed_speed_knots", "performance", "Maximum observed speed", "number", "kn", "Highest speed Dan explicitly says the boat is doing.", "Real test-drive performance, separate from brochure claims."),
    AttributeDefinition("cruise_speed_knots", "performance", "Cruise speed", "number", "kn", "Explicit cruising-speed statement.", "Passage time and efficiency."),
    AttributeDefinition("range_nm", "performance", "Range", "number", "nm", "Explicit range statement normalised to nautical miles.", "Distance, remoteness and fuel planning."),
    AttributeDefinition("engine_power_hp", "powertrain", "Engine power", "number", "hp", "Engine or total horsepower mentioned in the transcript.", "Performance and configuration comparison."),
    AttributeDefinition("engine_count", "powertrain", "Engine count", "number", "count", "Number of engines explicitly stated.", "Redundancy, cost and performance."),
    AttributeDefinition("drive_type", "powertrain", "Drive type", "enum", None, "Outboard, sterndrive, shaft, pod, jet, surface, hybrid or electric drive.", "Handling, maintenance, draft and efficiency."),
    AttributeDefinition("fuel_capacity_l", "capacity", "Fuel capacity", "number", "L", "Fuel capacity stated in the transcript.", "Range and expedition suitability."),
    AttributeDefinition("water_capacity_l", "capacity", "Fresh-water capacity", "number", "L", "Fresh-water capacity stated in the transcript.", "Overnight and remote-use autonomy."),
    AttributeDefinition("cabins", "accommodation", "Cabins", "number", "count", "Cabin count stated in the transcript.", "Overnight party size and privacy."),
    AttributeDefinition("berths", "accommodation", "Berths", "number", "count", "Sleeping berths stated in the transcript.", "Overnight capacity."),
    AttributeDefinition("heads", "accommodation", "Heads / bathrooms", "number", "count", "Heads or bathroom count stated in the transcript.", "Overnight comfort."),
    AttributeDefinition("hull_form", "hull", "Hull form", "enum", None, "Monohull, catamaran, trimaran, RIB or amphibious hull language.", "Ride, stability, beam and access."),
    AttributeDefinition("offshore_capable", "mission", "Offshore capable", "boolean", None, "Dan explicitly discusses offshore or blue-water suitability.", "Open-water mission fork."),
    AttributeDefinition("trailerable", "mission", "Trailerable", "boolean", None, "Dan explicitly discusses trailering or towing the boat.", "Storage and launch-location flexibility."),
    AttributeDefinition("great_loop_relevant", "mission", "Great Loop relevant", "boolean", None, "Dan explicitly discusses the Great Loop or bridge-clearance constraint.", "Route-specific qualification."),
    AttributeDefinition("overnight_capable", "mission", "Overnight capable", "boolean", None, "Dan explicitly discusses sleeping or overnight use.", "Day-only versus overnight fork."),
    AttributeDefinition("family_suitable", "mission", "Family suitable", "boolean", None, "Dan explicitly frames the boat for family use.", "Family mission fit."),
    AttributeDefinition("fishing_suitable", "mission", "Fishing suitable", "boolean", None, "Dan explicitly frames the boat or space for fishing.", "Fishing mission fit."),
    AttributeDefinition("watersports_suitable", "mission", "Watersports suitable", "boolean", None, "Dan explicitly mentions diving, skiing, wakeboarding or water toys.", "Active day-use mission fit."),
    AttributeDefinition("long_range_suitable", "mission", "Long-range suitable", "boolean", None, "Dan explicitly describes long-range, passage or expedition use.", "Explorer mission fit."),
    AttributeDefinition("hydraulic_swim_platform", "access", "Hydraulic swim platform", "boolean", None, "A hydraulic or submersible swim platform is discussed.", "Swimming, tender and water access."),
    AttributeDefinition("folding_balconies", "access", "Folding balconies / terraces", "boolean", None, "Opening side terraces, wings or balconies are discussed.", "At-anchor social space."),
    AttributeDefinition("beach_club", "access", "Beach club", "boolean", None, "A beach-club area is explicitly discussed.", "Swimming and Med-style day use."),
    AttributeDefinition("walkaround_decks", "access", "Walkaround decks", "boolean", None, "Walkaround circulation or full side decks are discussed.", "Crew movement, safety and fishing."),
    AttributeDefinition("side_boarding_door", "access", "Side boarding door", "boolean", None, "A side boarding, dive or hull door is discussed.", "Dock, water and accessibility use."),
    AttributeDefinition("enclosable_cockpit", "weather", "Fully enclosable cockpit", "boolean", None, "Dan discusses enclosing or sealing the cockpit from weather.", "All-weather and shoulder-season use."),
    AttributeDefinition("hardtop", "weather", "Hardtop", "boolean", None, "A hardtop or fixed overhead structure is discussed.", "Weather and sun protection."),
    AttributeDefinition("opening_sunroof", "weather", "Opening sunroof", "boolean", None, "An opening roof or sunroof is discussed.", "Open-air feel with protection."),
    AttributeDefinition("air_conditioning", "comfort", "Air conditioning", "boolean", None, "Air conditioning is explicitly discussed.", "Climate and overnight comfort."),
    AttributeDefinition("generator", "systems", "Generator", "boolean", None, "A generator or genset is explicitly discussed.", "Electrical autonomy."),
    AttributeDefinition("solar", "systems", "Solar", "boolean", None, "Solar charging or solar panels are explicitly discussed.", "Quiet electrical autonomy."),
    AttributeDefinition("watermaker", "systems", "Watermaker", "boolean", None, "A watermaker is explicitly discussed.", "Remote cruising autonomy."),
    AttributeDefinition("gyro_stabiliser", "systems", "Gyro stabiliser", "boolean", None, "A gyro, Seakeeper or Quick stabiliser is discussed.", "At-rest comfort."),
    AttributeDefinition("fin_stabilisers", "systems", "Fin stabilisers", "boolean", None, "Fin or underway stabilisers are discussed.", "Passage and at-anchor comfort."),
    AttributeDefinition("joystick_control", "handling", "Joystick control", "boolean", None, "Joystick manoeuvring is discussed.", "Low-speed confidence."),
    AttributeDefinition("dynamic_positioning", "handling", "Dynamic positioning", "boolean", None, "Skyhook, DPS or position-hold is discussed.", "Waiting, fishing and short-handed control."),
    AttributeDefinition("bow_thruster", "handling", "Bow thruster", "boolean", None, "A bow thruster is discussed.", "Docking confidence."),
    AttributeDefinition("stern_thruster", "handling", "Stern thruster", "boolean", None, "A stern thruster is discussed.", "Docking confidence."),
    AttributeDefinition("tender_garage", "storage", "Tender garage", "boolean", None, "A tender or toy garage is discussed.", "Tender and toy carrying."),
    AttributeDefinition("galley", "accommodation", "Galley", "boolean", None, "An indoor or outdoor galley is discussed.", "Entertaining and overnight use."),
    AttributeDefinition("separate_shower", "accommodation", "Separate shower", "boolean", None, "A separate shower compartment is discussed.", "Overnight comfort."),
    AttributeDefinition("crew_cabin", "accommodation", "Crew cabin", "boolean", None, "Dedicated crew accommodation is discussed.", "Owner-operation versus crewed use."),
    AttributeDefinition("premium_styling", "character", "Premium / striking styling", "boolean", None, "Dan explicitly calls the boat sexy, beautiful, stylish or striking.", "Emotional and design-led preference."),
    AttributeDefinition("quiet_ride", "character", "Quiet ride", "boolean", None, "Dan explicitly comments on low noise or quiet running.", "Comfort and refinement."),
    AttributeDefinition("dry_ride", "character", "Dry ride", "boolean", None, "Dan explicitly comments on spray protection or a dry ride.", "Offshore and passenger comfort."),
)


CATEGORY_DEFINITIONS = (
    CategoryDefinition("adventure", "Adventure Boats", "Dan category anchor", "Versatile boats for purposeful day trips, weather, carrying gear and exploring.", "anchor"),
    CategoryDefinition("fast-explorer", "Fast Explorers", "Dan category anchor", "Explorer capability with materially faster passage speed.", "anchor"),
    CategoryDefinition("sport-yacht", "Sport Yachts", "Dan category anchor", "Performance-led yachts that still provide accommodation and social space.", "anchor"),
    CategoryDefinition("luxury-rib", "Luxury RIBs", "Dan category anchor", "Premium rigid-inflatable boats combining performance, finish and practical deck use.", "anchor"),
    CategoryDefinition("luxury-med-day-boat", "Luxury Med Day Boats", "Dan category anchor", "Open luxury day boats focused on swimming, social space and fair-weather use.", "anchor"),
    CategoryDefinition("power-catamaran", "Power Catamarans", "Transcript type", "Twin-hull power boats, including cruising and performance cats.", "candidate"),
    CategoryDefinition("centre-console", "Centre Consoles", "Transcript type", "Open boats organised around a central helm console.", "candidate"),
    CategoryDefinition("walkaround-day-boat", "Walkaround Day Boats", "Transcript type", "Day boats with easy movement around the helm and social areas.", "candidate"),
    CategoryDefinition("sports-cruiser", "Sports Cruisers", "Transcript type", "Fast planing cruisers with cockpit social space and overnight accommodation.", "candidate"),
    CategoryDefinition("express-cruiser", "Express Cruisers", "Transcript type", "Single-level or coupe-style cruisers designed for fast coastal use.", "candidate"),
    CategoryDefinition("flybridge-motor-yacht", "Flybridge Motor Yachts", "Transcript type", "Motor yachts with a second, elevated helm and social deck.", "candidate"),
    CategoryDefinition("pilothouse-crossover", "Pilothouse / All-weather Crossovers", "Transcript type", "Enclosed-helm boats balancing protection, deck access and practical year-round use.", "candidate"),
    CategoryDefinition("explorer-expedition", "Explorer / Expedition Yachts", "Transcript type", "Long-range displacement or semi-displacement yachts designed for extended travel.", "candidate"),
    CategoryDefinition("offshore-fishing", "Offshore Fishing Boats", "Transcript type", "Boats whose working layout and capability are explicitly framed around offshore fishing.", "candidate"),
    CategoryDefinition("bowrider-runabout", "Bowriders / Runabouts", "Transcript type", "Open day boats with forward seating and short-trip social use.", "candidate"),
    CategoryDefinition("weekender-commuter", "Weekenders / Commuters", "Transcript type", "Compact practical cruisers for short stays, commuting and mixed day use.", "candidate"),
    CategoryDefinition("chase-tender", "Chase Boats / Yacht Tenders", "Transcript type", "High-capability tenders and chase boats supporting a larger yacht or resort mission.", "candidate"),
    CategoryDefinition("lobster-downeast", "Lobster / Downeast Cruisers", "Transcript type", "Traditional workboat-influenced cruisers with efficient, protected layouts.", "candidate"),
    CategoryDefinition("amphibious", "Amphibious Boats", "Transcript type", "Boats with integrated land-running or beach-launch capability.", "candidate"),
    CategoryDefinition("superyacht", "Superyachts", "Transcript type", "Large crewed yachts with superyacht-scale accommodation and systems.", "candidate"),
)


@dataclass(frozen=True)
class TagRule:
    attribute_key: str
    value_key: str
    pattern: re.Pattern[str]
    confidence: float


@dataclass(frozen=True)
class CategoryRule:
    category_key: str
    pattern: re.Pattern[str]
    confidence: float


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


TAG_RULES = (
    TagRule("drive_type", "outboard", _rx(r"\boutboards?\b|\boutboard[- ]powered\b"), 0.94),
    TagRule("drive_type", "sterndrive", _rx(r"\bstern\s*drives?\b|\binboard/outboard\b|\bbravo\s+(?:one|two|three)\b"), 0.94),
    TagRule("drive_type", "ips-pod", _rx(r"\bIPS\s*\d*\b|\bvolvo\s+ips\b|\bpod\s+drives?\b"), 0.96),
    TagRule("drive_type", "shaft", _rx(r"\bshaft\s*drives?\b|\bstraight\s+shafts?\b|\bshaft[- ]driven\b"), 0.95),
    TagRule("drive_type", "waterjet", _rx(r"\bwater\s*jets?\b|\bjet\s+drives?\b|\bhamilton\s+jets?\b"), 0.94),
    TagRule("drive_type", "surface-drive", _rx(r"\bsurface\s+drives?\b|\bArneson\b"), 0.96),
    TagRule("drive_type", "electric", _rx(r"\belectric\s+(?:motor|drive|propulsion)\b|\bfully electric\b"), 0.92),
    TagRule("drive_type", "hybrid", _rx(r"\bhybrid\s+(?:drive|propulsion|system)\b"), 0.93),
    TagRule("hull_form", "power-catamaran", _rx(r"\bpower\s*cat(?:amaran)?\b|\bcatamaran\s+hull\b|\btwin\s+hulls?\b"), 0.94),
    TagRule("hull_form", "rib", _rx(r"\brigid\s+inflatable\b|\bRIB\b|\binflatable\s+(?:tubes?|collar)\b"), 0.95),
    TagRule("hull_form", "trimaran", _rx(r"\btrimaran\b|\bthree\s+hulls?\b"), 0.96),
    TagRule("hull_form", "amphibious", _rx(r"\bamphibious\b|\bretractable\s+(?:wheels|tracks)\b"), 0.97),
    TagRule("offshore_capable", "primary", _rx(r"\boffshore\s+(?:capable|use|boat|work|conditions?)\b|\bblue\s*water\b|\bopen[- ]ocean\b"), 0.88),
    TagRule("trailerable", "primary", _rx(r"\btrailerable\b|\btrailer\s+(?:boat|home|weight|width|launch)\b|\bon\s+the\s+trailer\b|\b(?:tow|towing)\s+(?:it|this|the\s+boat)\s+behind\s+(?:a|your)\s+(?:car|vehicle|truck|ute)\b"), 0.89),
    TagRule("great_loop_relevant", "primary", _rx(r"\bgreat\s+loop\b|\bbridge\s+clearance\b"), 0.94),
    TagRule("overnight_capable", "primary", _rx(r"\bovernight(?:ing)?\b|\bsleep(?:ing)?\s+(?:on|aboard|accommodation|capacity)\b|\bweekend\s+aboard\b"), 0.86),
    TagRule("family_suitable", "primary", _rx(r"\bfamily\s+(?:boat|use|cruising|day|weekend|friendly)\b|\bfor\s+the\s+family\b"), 0.85),
    TagRule("fishing_suitable", "primary", _rx(r"\b(?:sport|offshore|game)\s*fishing\b|\bthis\s+is\s+(?:an?\s+)?fishing\s+boat\b|\bdesigned\s+(?:for|around)\s+fishing\b|\bfishing\s+(?:space|setup|station|features?|rods?)\b|\bfishability\b"), 0.88),
    TagRule("watersports_suitable", "primary", _rx(r"\bwater\s*sports?\b|\bwakeboard(?:ing)?\b|\bwater\s*ski(?:ing)?\b|\bdiving\s+(?:boat|platform|setup)\b|\btoys?\s+in\s+the\s+water\b"), 0.87),
    TagRule("long_range_suitable", "primary", _rx(r"\blong[- ]range\b|\bextended\s+(?:cruising|passages?)\b|\bexpedition\s+(?:use|cruising|capable)\b|\bocean\s+crossing\b"), 0.91),
    TagRule("hydraulic_swim_platform", "primary", _rx(r"\b(?:hydraulic|submersible|lowering)\s+(?:swim|bathing|rear|aft)?\s*platform\b"), 0.96),
    TagRule("folding_balconies", "primary", _rx(r"\b(?:folding|drop[- ]down|opening|fold[- ]down)\s+(?:side\s+)?(?:balcon(?:y|ies)|terraces?|wings?|bulwarks?)\b|\bside\s+terraces?\b"), 0.94),
    TagRule("beach_club", "primary", _rx(r"\bbeach\s+club\b"), 0.97),
    TagRule("walkaround_decks", "primary", _rx(r"\bwalk\s*around\s+(?:deck|access|layout|boat)\b|\bfull\s+walkaround\b|\bfull\s+side\s+decks?\b"), 0.91),
    TagRule("side_boarding_door", "primary", _rx(r"\bside\s+(?:boarding|dive|hull)\s+door\b|\b(?:opening\s+)?boarding\s+door\b|\bdive\s+door\b|\bside\s+gate\b|\bdoor\s+in\s+the\s+(?:hull|side)\b"), 0.93),
    TagRule("enclosable_cockpit", "primary", _rx(r"\bfully\s+enclos(?:able|ed)\s+cockpit\b|\benclos(?:e|ed|ing)\s+(?:the\s+)?cockpit\b|\benclos(?:e|ed|ing)\s+(?:the\s+)?(?:back|rear|aft)\s+of\s+(?:the\s+)?boat\b|\bclose\s+off\s+the\s+cockpit\b|\b(?:eisen|ising)\s*glass\s+(?:enclosure|covers?)\b|\bcanvas\s+enclosure\b|\b(?:zip|roll)\s+(?:in|down)\s+(?:the\s+)?clears\b"), 0.95),
    TagRule("hardtop", "primary", _rx(r"\bhard\s*top\b|\bfixed\s+hardtop\b"), 0.92),
    TagRule("opening_sunroof", "primary", _rx(r"\bopening\s+(?:roof|sunroof)\b|\belectric\s+sunroof\b|\bsliding\s+(?:roof|sunroof)\b"), 0.93),
    TagRule("air_conditioning", "primary", _rx(r"\bair\s*conditioning\b|\bair\s*con\b|\bA/C\b"), 0.92),
    TagRule("generator", "primary", _rx(r"\bgenerator\b|\bgenset\b"), 0.93),
    TagRule("solar", "primary", _rx(r"\bsolar\s+(?:panels?|charging|array|power)\b"), 0.94),
    TagRule("watermaker", "primary", _rx(r"\bwater\s*maker\b|\bdesalination\s+system\b"), 0.96),
    TagRule("gyro_stabiliser", "primary", _rx(r"\bgyro\s*stabili[sz]er\b|\bSeakeeper\b|\bQuick\s+gyro\b"), 0.96),
    TagRule("fin_stabilisers", "primary", _rx(r"\bfin\s+stabili[sz]ers?\b|\bzero[- ]speed\s+fins?\b"), 0.96),
    TagRule("joystick_control", "primary", _rx(r"\bjoystick\s+(?:control|steering|docking|system)\b|\bdocking\s+joystick\b"), 0.94),
    TagRule("dynamic_positioning", "primary", _rx(r"\bdynamic\s+positioning\b|\bposition\s+hold\b|\bSkyhook\b|\bDPS\b"), 0.94),
    TagRule("bow_thruster", "primary", _rx(r"\bbow\s+thruster\b"), 0.96),
    TagRule("stern_thruster", "primary", _rx(r"\bstern\s+thruster\b"), 0.96),
    TagRule("tender_garage", "primary", _rx(r"\b(?:tender|toy)\s+garage\b|\bgarage\s+for\s+(?:the\s+)?tender\b"), 0.96),
    TagRule("galley", "primary", _rx(r"\bgalley\b|\boutdoor\s+kitchen\b"), 0.90),
    TagRule("separate_shower", "primary", _rx(r"\bseparate\s+shower\b|\bstandalone\s+shower\b|\bshower\s+stall\b"), 0.94),
    TagRule("crew_cabin", "primary", _rx(r"\bcrew\s+(?:cabin|quarters|accommodation)\b"), 0.96),
    TagRule("premium_styling", "primary", _rx(r"\bsexy(?:[- ]looking)?\b|\b(?:beautiful|gorgeous|stunning|striking)\s+(?:boat|design|profile|lines|shape|looking)\b|\blooks?\s+(?:sexy|beautiful|gorgeous|stunning|striking)\b|\bbeautifully\s+(?:styled|designed)\b"), 0.82),
    TagRule("quiet_ride", "primary", _rx(r"\b(?:really|very|remarkably|incredibly)?\s*quiet\s+(?:ride|running|underway|boat)\b|\bnoise\s+levels?\s+(?:are|is)\s+low\b"), 0.85),
    TagRule("dry_ride", "primary", _rx(r"\bdry\s+ride\b|\bkeeps?\s+(?:us|you|the cockpit)\s+dry\b|\bno\s+spray\s+(?:on|in)\b"), 0.87),
)


CATEGORY_RULES = (
    CategoryRule("adventure", _rx(r"\b(?:this|it|she)\s+is\s+(?:an?\s+)?adventure\s+boat\b|\bfor\s+an?\s+adventure\s+boat\b|\badventure[- ]ready\b"), 0.95),
    CategoryRule("fast-explorer", _rx(r"\bfast\s+explorers?\b"), 0.97),
    CategoryRule("sport-yacht", _rx(r"\bsports?\s+yachts?\b"), 0.97),
    CategoryRule("luxury-rib", _rx(r"\bluxury\s+RIBs?\b|\bpremium\s+RIBs?\b"), 0.97),
    CategoryRule("luxury-med-day-boat", _rx(r"\b(?:luxury|premium)\s+(?:med(?:iterranean)?\s+)?day\s+boats?\b|\bmed(?:iterranean)?\s+day\s+boats?\b"), 0.96),
    CategoryRule("power-catamaran", _rx(r"\bpower\s*cat(?:amaran)?s?\b|\bpower\s+catamarans?\b"), 0.95),
    CategoryRule("centre-console", _rx(r"\bcent(?:er|re)[- ]console\s+boats?\b|\b(?:this|it|she)\s+is\s+(?:an?\s+)?cent(?:er|re)\s+console\b|\bcent(?:er|re)\s+consoles\b"), 0.96),
    CategoryRule("walkaround-day-boat", _rx(r"\bwalk\s*around\s+day\s+boats?\b|\bwalkaround\s+boats?\b|\bday\s+boats?\b"), 0.87),
    CategoryRule("sports-cruiser", _rx(r"\bsports?\s+cruisers?\b"), 0.97),
    CategoryRule("express-cruiser", _rx(r"\bexpress\s+cruisers?\b"), 0.97),
    CategoryRule("flybridge-motor-yacht", _rx(r"\bfly\s*bridge\s+(?:motor\s+)?yachts?\b|\bflybridge\s+boats?\b"), 0.94),
    CategoryRule("pilothouse-crossover", _rx(r"\bpilot\s*house\s+boats?\b|\ball[- ]weather\s+(?:boat|crossover)\b"), 0.93),
    CategoryRule("explorer-expedition", _rx(r"\bexplorer\s+yachts?\b|\bexpedition\s+yachts?\b|\bexploration\s+yachts?\b"), 0.97),
    CategoryRule("offshore-fishing", _rx(r"\boffshore\s+fishing\s+boats?\b|\bsport\s*fish(?:er|ing)?\s+(?:boat|yacht)s?\b"), 0.95),
    CategoryRule("bowrider-runabout", _rx(r"\bbow\s*riders?\b|\brunabouts?\b"), 0.95),
    CategoryRule("weekender-commuter", _rx(r"\bweekenders?\b|\bcommuter\s+boats?\b"), 0.91),
    CategoryRule("chase-tender", _rx(r"\bchase\s+boats?\b|\bsuperyacht\s+tenders?\b|\byacht\s+tenders?\b"), 0.94),
    CategoryRule("lobster-downeast", _rx(r"\blobster\s+boats?\b|\bdown\s*east\s+(?:boat|cruiser)s?\b"), 0.96),
    CategoryRule("amphibious", _rx(r"\bamphibious\s+boats?\b"), 0.98),
    CategoryRule("superyacht", _rx(r"\b(?:this|it|she)\s+(?:is|was)\s+(?:an?\s+)?(?:super\s*yacht|megayacht)\b|\b(?:classed|classified|registered)\s+as\s+(?:an?\s+)?super\s*yacht\b"), 0.95),
)


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
NUMBER_TOKEN = r"(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)"


NUMERIC_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "top_speed_knots": (
        _rx(rf"\b(?:top|maximum|max|full)\s+speed\b.{{0,55}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>knots?|kts?|mph|km/?h)\b"),
        _rx(rf"\b(?:will|can|does|should)\s+(?:do|reach|get\s+to)\s+(?P<value>{NUMBER_TOKEN})\s*(?P<unit>knots?|kts?|mph|km/?h)\b"),
    ),
    "max_observed_speed_knots": (
        _rx(rf"\b(?:we(?:'re|\s+are)?|i(?:'m|\s+am)?|she(?:'s|\s+is)?|the\s+boat(?:'s|\s+is)?)\s+(?:now\s+)?(?:doing|at|running\s+at)\s+(?:about|around|nearly|over|just\s+over)?\s*(?P<value>{NUMBER_TOKEN})(?:\s*plus)?\s*(?P<unit>knots?|kts?)\b"),
        _rx(rf"\bdoing\s+(?:about|around|nearly|over|just\s+over)?\s*(?P<value>{NUMBER_TOKEN})(?:\s*plus)?\s*(?P<unit>knots?|kts?)\b"),
    ),
    "cruise_speed_knots": (
        _rx(rf"\bcruis(?:e|es|ing)\b.{{0,45}}?\b(?:at\s+)?(?P<value>{NUMBER_TOKEN})\s*(?P<unit>knots?|kts?|mph|km/?h)\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>knots?|kts?)\s+(?:is\s+)?(?:a\s+)?(?:comfortable\s+)?cruis(?:e|ing)\b"),
    ),
    "range_nm": (
        _rx(rf"\brange\b.{{0,55}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>nautical\s+miles?|nm|miles?|kilomet(?:er|re)s?|km)\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>nautical\s+miles?|nm)\s+(?:of\s+)?range\b"),
    ),
    "beam_feet": (
        _rx(rf"\bbeam\b.{{0,35}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b"),
    ),
    "draft_feet": (
        _rx(rf"\b(?:water\s+)?draft\b.{{0,35}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b"),
        _rx(rf"\bdraws?\s+(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\s+(?:of\s+)?draft\b"),
    ),
    "air_draft_feet": (
        _rx(rf"\bair\s*draft\b.{{0,35}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b"),
        _rx(rf"\bbridge\s+clearance\b.{{0,35}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>feet|foot|ft|meters?|metres?|m)\b"),
    ),
    "displacement_kg": (
        _rx(rf"\b(?:displacement|weighs?|weight)\b.{{0,45}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>kilograms?|kg|tonnes?|tons?|pounds?|lbs?)\b"),
    ),
    "fuel_capacity_l": (
        _rx(rf"\b(?:fuel|diesel|petrol)\s+(?:capacity|tank|tanks)\b.{{0,45}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>lit(?:er|re)s?|l|gallons?|gal)\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>lit(?:er|re)s?|l|gallons?|gal)\s+(?:of\s+)?fuel\b"),
    ),
    "water_capacity_l": (
        _rx(rf"\b(?:fresh\s*)?water\s+(?:capacity|tank|tanks)\b.{{0,45}}?\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>lit(?:er|re)s?|l|gallons?|gal)\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>lit(?:er|re)s?|l|gallons?|gal)\s+(?:of\s+)?(?:fresh\s*)?water\b"),
    ),
    "engine_power_hp": (
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s*(?P<unit>horsepower|hp)\b"),
    ),
    "cabins": (
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})[- ]cabins?\b"),
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s+(?:proper\s+|separate\s+)?cabins?\b"),
    ),
    "berths": (
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})[- ]berths?\b"),
        _rx(rf"\bsleeps?\s+(?P<value>{NUMBER_TOKEN})\b"),
    ),
    "heads": (
        _rx(rf"\b(?P<value>{NUMBER_TOKEN})\s+(?:heads?|bathrooms?)\b"),
    ),
}


NUMERIC_RANGES = {
    "top_speed_knots": (3, 100),
    "max_observed_speed_knots": (3, 100),
    "cruise_speed_knots": (3, 80),
    "range_nm": (5, 10000),
    "beam_feet": (4, 80),
    "draft_feet": (0.5, 30),
    "air_draft_feet": (2, 150),
    "displacement_kg": (100, 5000000),
    "fuel_capacity_l": (10, 1000000),
    "water_capacity_l": (5, 200000),
    "engine_power_hp": (10, 10000),
    "cabins": (0, 20),
    "berths": (1, 50),
    "heads": (1, 20),
}


ENGINE_COUNT_RULES = (
    (_rx(r"\bsingle\s+(?:engine|outboard|diesel|motor)\b"), 1),
    (_rx(r"\btwin\s+(?:engines?|outboards?|diesels?|motors?)\b"), 2),
    (_rx(r"\btriple\s+(?:engines?|outboards?|motors?)\b"), 3),
    (_rx(r"\bquad(?:ruple)?\s+(?:engines?|outboards?|motors?)\b"), 4),
    (_rx(r"\bfive\s+(?:engines?|outboards?|motors?)\b"), 5),
)


def _number(value: str) -> float:
    token = value.lower()
    return float(NUMBER_WORDS[token]) if token in NUMBER_WORDS else float(token)


def _canonical_numeric(key: str, value: float, unit: str) -> tuple[float, str]:
    unit_norm = normalise(unit)
    if key in {"top_speed_knots", "max_observed_speed_knots", "cruise_speed_knots"}:
        if unit_norm == "mph":
            value *= 0.868976
        elif unit_norm in {"km h", "kmh"}:
            value *= 0.539957
        return value, "kn"
    if key == "range_nm":
        if unit_norm in {"mile", "miles"}:
            value *= 0.868976
        elif unit_norm in {"kilometer", "kilometers", "kilometre", "kilometres", "km"}:
            value *= 0.539957
        return value, "nm"
    if key in {"beam_feet", "draft_feet", "air_draft_feet"}:
        if unit_norm in {"meter", "meters", "metre", "metres", "m"}:
            value *= 3.28084
        return value, "ft"
    if key == "displacement_kg":
        if unit_norm in {"ton", "tons", "tonne", "tonnes"}:
            value *= 1000
        elif unit_norm in {"pound", "pounds", "lb", "lbs"}:
            value *= 0.453592
        return value, "kg"
    if key in {"fuel_capacity_l", "water_capacity_l"}:
        if unit_norm in {"gallon", "gallons", "gal"}:
            value *= 3.78541
        return value, "L"
    if key == "engine_power_hp":
        return value, "hp"
    return value, "count"


def _quote(text: str, start: int, end: int, limit: int = 22) -> str:
    words = list(re.finditer(r"\S+", text))
    if not words:
        return ""
    hit = next((index for index, word in enumerate(words) if word.start() <= start < word.end()), 0)
    left = max(0, hit - limit // 2)
    right = min(len(words), left + limit)
    left = max(0, right - limit)
    excerpt = " ".join(word.group(0) for word in words[left:right])
    if left:
        excerpt = "..." + excerpt
    if right < len(words):
        excerpt += "..."
    return excerpt


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 65):start]
    if _rx(r"\bnot\s+(?:just|only)\s+$").search(prefix):
        return False
    return bool(_rx(
        r"(?:"
        r"\bno\s+(?:an?\s+|the\s+)?(?:separate\s+)?|"
        r"\bwithout\s+(?:an?\s+|the\s+)?(?:separate\s+)?|"
        r"\b(?:does|do|is|are|has|have)(?:n't|nt|\s+not)\s+"
        r"(?:have\s+|got\s+|fitted\s+with\s+)(?:an?\s+|the\s+)?(?:separate\s+)?|"
        r"\bnot\s+an?\s+(?:separate\s+)?"
        r")$"
    ).search(prefix))


def _qualifier(text: str, start: int, end: int) -> str:
    context = text[max(0, start - 70):min(len(text), end + 70)]
    if _rx(r"\b(?:option|optional|available\s+with|can\s+(?:have|add|fit)|if\s+specified)\b").search(context):
        return "optional"
    return "observed"


def _evidence_base(record: dict[str, Any], segment: dict[str, Any], match: re.Match[str]) -> dict[str, Any]:
    text = segment.get("text") or ""
    return {
        "video_id": record["youtube_video_id"],
        "start_seconds": float(segment.get("start") or 0),
        "sequence": int(segment.get("sequence") or 0),
        "evidence_text": _quote(text, match.start(), match.end()),
    }


def extract_video(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []
    categories: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for segment in record.get("transcript_segments") or []:
        text = segment.get("text") or ""
        for rule in TAG_RULES:
            for match in rule.pattern.finditer(text):
                negated = _negated(text, match.start())
                if negated and _rx(r"^\s+(?:control|controller|button|switch|outlet|vent)\b").search(text[match.end():match.end() + 30]):
                    negated = False
                if negated and rule.attribute_key in {"premium_styling", "quiet_ride", "dry_ride"}:
                    continue
                value_boolean = None
                if rule.value_key == "primary" and rule.attribute_key not in {"drive_type", "hull_form"}:
                    value_boolean = not negated
                elif negated:
                    continue
                qualifier = _qualifier(text, match.start(), match.end())
                key = (record["youtube_video_id"], segment.get("sequence"), rule.attribute_key, rule.value_key, value_boolean)
                if key in seen:
                    continue
                seen.add(key)
                observations.append({
                    **_evidence_base(record, segment, match),
                    "attribute_key": rule.attribute_key,
                    "value_key": rule.value_key,
                    "value_type": "boolean" if value_boolean is not None else "enum",
                    "value_boolean": value_boolean,
                    "value_number": None,
                    "value_text": rule.value_key if value_boolean is None else None,
                    "unit": None,
                    "qualifier": qualifier,
                    "confidence": round(rule.confidence - (0.07 if qualifier == "optional" else 0), 3),
                    "extraction_method": f"transcript_rule:{rule.attribute_key}:{rule.value_key}",
                })
        for rule in CATEGORY_RULES:
            for match in rule.pattern.finditer(text):
                if _negated(text, match.start()):
                    continue
                key = (record["youtube_video_id"], segment.get("sequence"), "category", rule.category_key)
                if key in seen:
                    continue
                seen.add(key)
                categories.append({
                    **_evidence_base(record, segment, match),
                    "category_key": rule.category_key,
                    "confidence": rule.confidence,
                    "extraction_method": f"transcript_category:{rule.category_key}",
                })
        for attribute_key, patterns in NUMERIC_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    value, unit = _canonical_numeric(attribute_key, _number(match.group("value")), match.groupdict().get("unit") or "count")
                    low, high = NUMERIC_RANGES[attribute_key]
                    if not low <= value <= high:
                        continue
                    rounded = round(value, 2)
                    key = (record["youtube_video_id"], segment.get("sequence"), attribute_key, rounded)
                    if key in seen:
                        continue
                    seen.add(key)
                    observations.append({
                        **_evidence_base(record, segment, match),
                        "attribute_key": attribute_key,
                        "value_key": "primary",
                        "value_type": "number",
                        "value_boolean": None,
                        "value_number": rounded,
                        "value_text": None,
                        "unit": unit,
                        "qualifier": _qualifier(text, match.start(), match.end()),
                        "confidence": 0.93 if attribute_key not in {"max_observed_speed_knots", "engine_power_hp"} else 0.89,
                        "extraction_method": f"transcript_numeric:{attribute_key}",
                    })
        for pattern, count in ENGINE_COUNT_RULES:
            for match in pattern.finditer(text):
                key = (record["youtube_video_id"], segment.get("sequence"), "engine_count", count)
                if key in seen:
                    continue
                seen.add(key)
                observations.append({
                    **_evidence_base(record, segment, match),
                    "attribute_key": "engine_count",
                    "value_key": "primary",
                    "value_type": "number",
                    "value_boolean": None,
                    "value_number": count,
                    "value_text": None,
                    "unit": "count",
                    "qualifier": _qualifier(text, match.start(), match.end()),
                    "confidence": 0.93,
                    "extraction_method": "transcript_numeric:engine_count",
                })
    return observations, categories


def _evidence_rank(item: dict[str, Any]) -> tuple[float, float]:
    return float(item["confidence"]), -float(item["start_seconds"])


def aggregate_attributes(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_attribute: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        by_attribute[observation["attribute_key"]].append(observation)
    output: list[dict[str, Any]] = []
    numeric_max = {"top_speed_knots", "max_observed_speed_knots", "range_nm", "engine_power_hp", "fuel_capacity_l", "water_capacity_l", "cabins", "berths", "heads", "engine_count"}
    for attribute_key, items in sorted(by_attribute.items()):
        if items[0]["value_type"] == "number":
            values = [float(item["value_number"]) for item in items]
            primary = max(values) if attribute_key in numeric_max else statistics.median(values)
            distinct_videos = len({item["video_id"] for item in items})
            output.append({
                "attribute_key": attribute_key,
                "value_key": "primary",
                "value_type": "number",
                "value_number": round(primary, 2),
                "value_boolean": None,
                "value_text": None,
                "unit": items[0]["unit"],
                "value_detail": {"minimum": min(values), "maximum": max(values), "observations": len(values)},
                "confidence": round(min(0.99, max(float(item["confidence"]) for item in items) + 0.02 * min(3, distinct_videos - 1)), 3),
                "evidence": sorted(items, key=_evidence_rank, reverse=True)[:5],
            })
            continue
        if items[0]["value_type"] == "enum":
            by_value: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in items:
                by_value[item["value_key"]].append(item)
            for value_key, value_items in sorted(by_value.items()):
                output.append({
                    "attribute_key": attribute_key,
                    "value_key": value_key,
                    "value_type": "enum",
                    "value_number": None,
                    "value_boolean": None,
                    "value_text": value_key,
                    "unit": None,
                    "value_detail": {"observations": len(value_items)},
                    "confidence": round(min(0.99, max(float(item["confidence"]) for item in value_items) + 0.02 * min(3, len({item['video_id'] for item in value_items}) - 1)), 3),
                    "evidence": sorted(value_items, key=_evidence_rank, reverse=True)[:5],
                })
            continue
        positives = [item for item in items if item["value_boolean"] is True]
        negatives = [item for item in items if item["value_boolean"] is False]
        conflict = bool(positives and negatives)
        selected = positives or negatives
        output.append({
            "attribute_key": attribute_key,
            "value_key": "primary",
            "value_type": "boolean",
            "value_number": None,
            "value_boolean": None if conflict else bool(positives),
            "value_text": "configuration-dependent" if conflict else None,
            "unit": None,
            "value_detail": {"positive_observations": len(positives), "negative_observations": len(negatives)},
            "confidence": round(max(float(item["confidence"]) for item in selected) - (0.12 if conflict else 0), 3),
            "evidence": sorted(items, key=_evidence_rank, reverse=True)[:5],
        })
    return output


def aggregate_categories(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["category_key"]].append(item)
    output = []
    for category_key, evidence in sorted(grouped.items()):
        videos = len({item["video_id"] for item in evidence})
        output.append({
            "category_key": category_key,
            "confidence": round(min(0.99, max(float(item["confidence"]) for item in evidence) + 0.02 * min(3, videos - 1)), 3),
            "evidence": sorted(evidence, key=_evidence_rank, reverse=True)[:5],
            "evidence_count": len(evidence),
        })
    return output


def load_profiles(input_dir: str | Path) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(input_dir).glob("*.json")):
        record = json.loads(path.read_text())
        video_id = record["youtube_video_id"]
        if video_id in NON_BOAT_OUTLIERS:
            continue
        identity = record.get("boat_identity") or {}
        if not identity.get("make") or not identity.get("model") or identity.get("length_feet") is None:
            continue
        identity_object = BoatIdentity(
            identity["make"],
            identity["model"],
            identity.get("full_name"),
            float(identity["length_feet"]),
            float(identity.get("confidence") or 0),
            identity.get("method") or "saved_identity",
        )
        canonical_key = pair_key(identity_object)
        if not canonical_key:
            continue
        group = groups.setdefault(canonical_key, {
            "canonical_key": canonical_key,
            "make": identity["make"],
            "model": identity["model"],
            "full_name": identity.get("full_name") or f"{identity['make']} {identity['model']}",
            "length_feet": float(identity["length_feet"]),
            "identity_confidence": float(identity.get("confidence") or 0),
            "videos": [],
            "observations": [],
            "category_evidence": [],
            "transcript_segments": 0,
        })
        observations, category_evidence = extract_video(record)
        incoming_confidence = float(identity.get("confidence") or 0)
        if incoming_confidence > group["identity_confidence"]:
            group.update({
                "make": identity["make"],
                "model": identity["model"],
                "full_name": identity.get("full_name") or f"{identity['make']} {identity['model']}",
                "length_feet": float(identity["length_feet"]),
                "identity_confidence": incoming_confidence,
            })
        group["videos"].append({
            "id": video_id,
            "title": record["title"],
            "types": sorted({item["video_type"] for item in record.get("playlists") or []}),
            "url": record["youtube_url"],
            "view_count": record.get("view_count") or 0,
            "comment_count": record.get("comment_count") or 0,
        })
        group["observations"].extend(observations)
        group["category_evidence"].extend(category_evidence)
        group["transcript_segments"] += len(record.get("transcript_segments") or [])
        group["identity_confidence"] = max(group["identity_confidence"], incoming_confidence)

    profiles = []
    for group in groups.values():
        length_observation = {
            "attribute_key": "length_feet",
            "value_key": "primary",
            "value_type": "number",
            "value_number": group["length_feet"],
            "value_boolean": None,
            "value_text": None,
            "unit": "ft",
            "value_detail": {"source": "validated_identity"},
            "confidence": group["identity_confidence"],
            "evidence": [],
        }
        attribute_evidence = group.pop("observations")
        category_evidence = group.pop("category_evidence")
        attributes = [length_observation, *aggregate_attributes(attribute_evidence)]
        categories = aggregate_categories(category_evidence)
        group["videos"].sort(key=lambda item: ("test_drive" not in item["types"], item["id"]))
        profiles.append({
            **group,
            "attributes": attributes,
            "attribute_evidence": attribute_evidence,
            "categories": categories,
            "category_evidence": category_evidence,
        })
    return sorted(profiles, key=lambda item: (item["make"].lower(), item["model"].lower()))
