from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz.fuzz import partial_ratio, token_set_ratio


MAKE_ALIASES = {
    "tesoro": "Tesoro",
    "xo boats": "XO",
    "xo": "XO",
    "merry fisher": "Jeanneau",
    "jeanneau": "Jeanneau",
    "saxdor": "Saxdor",
    "quarken": "Quarken",
    "wellcraft": "Wellcraft",
    "sargo": "Sargo",
    "nimbus": "Nimbus",
    "axopar": "Axopar",
    "flipper": "Flipper",
    "parker": "Parker",
    "navan": "Navan",
    "brabus": "Brabus",
    "hydrolift": "Hydrolift",
    "aiata": "Aiata",
    "ryck": "Ryck",
    "boston whaler": "Boston Whaler",
    "grady white": "Grady-White",
    "grady-white": "Grady-White",
    "storm bay": "Storm Bay",
    "riviera": "Riviera",
    "maritimo": "Maritimo",
    "regal": "Regal",
    "beneteau": "Beneteau",
    "highfield": "Highfield",
    "back cove": "Back Cove",
    "frauscher": "Frauscher",
    "omikron": "Omikron",
    "lomac": "Lomac",
    "fairline": "Fairline",
    "delta": "Delta",
    "silvercraft": "Silvercraft",
    "say": "SAY",
    "clb": "CLB",
    "chris craft": "Chris-Craft",
    "chris-craft": "Chris-Craft",
    "prestige yachts": "Prestige",
    "prestige": "Prestige",
    "sacs": "SACS",
    "azimut": "Azimut",
    "fjord": "Fjord",
    "centouno navi": "Centouno Navi",
    "koshi": "Koshi",
    "sterk": "Sterk",
    "sabre": "Sabre",
    "yot": "YOT",
    "barbaros": "Barbaros",
    "whitehaven": "Whitehaven",
    "cantiere delle marche": "Cantiere Delle Marche",
    "marex": "Marex",
    "rafnar": "Rafnar",
    "technohull": "Technohull",
    "silvercat": "Silvercat",
    "belize": "Belize",
    "aquila": "Aquila",
    "iron boat": "Iron",
    "iron": "Iron",
    "iguana": "Iguana",
    "zar": "ZAR",
    "integrity": "Integrity",
    "wiszniewski": "Wiszniewski",
    "scimitar": "Scimitar",
    "alaska": "Alaska",
    "deantonio": "DeAntonio",
    "parker": "Parker",
    "dromeas": "Dromeas",
    "majesty": "Majesty",
    "duchy": "Duchy",
    "regulator": "Regulator",
    "monterey": "Monterey",
    "zodiac": "Zodiac",
    "sea ray": "Sea Ray",
    "schaefer": "Schaefer",
    "four winns": "Four Winns",
    "toy marine": "Toy Marine",
    "pearl": "Pearl",
    "tasman": "Tasman",
    "alaska": "Alaska",
    "bluegame": "Bluegame",
    "capelli": "Capelli",
    "clipper": "Clipper",
    "cranchi": "Cranchi",
    "endurance": "Hampton",
    "four winns": "Four Winns",
    "galeon": "Galeon",
    "hampton": "Hampton",
    "invictus": "Invictus",
    "italboats": "Italboats",
    "lancia aprea": "Lancia Aprea",
    "nordhavn": "Nordhavn",
    "ocean alexander": "Ocean Alexander",
    "oryx": "Oryx",
    "princess": "Princess",
    "sealine": "Sealine",
    "sunseeker": "Sunseeker",
    "valhalla": "Valhalla Boatworks",
}


STOP_MODEL_WORDS = {
    "walkthrough", "review", "tour", "test", "drive", "tested", "first", "look",
    "offshore", "boat", "sea", "trial", "part", "full", "detailed", "with", "the",
    "walk", "before", "could", "can", "and", "or", "vs", "versus", "now", "tested",
    "yes", "its", "that", "good", "hard", "to", "be", "great", "choice", "for", "your",
    "a", "new", "market", "leader", "future", "doing", "what", "she", "does",
    "crosses", "line", "between", "modern", "gentlemans", "racer", "this", "is", "part",
}

MODEL_LENGTH_OVERRIDES = {
    ("Nimbus", "C11"): 40.7,
    ("Nimbus", "W11"): 40.7,
    ("Nimbus", "T11"): 40.7,
    ("Nimbus", "T9X"): 30.8,
    ("Nimbus", "T9"): 30.8,
    ("Nimbus", "W9"): 30.8,
    ("Nimbus", "T8"): 26.2,
    ("Azimut", "S6"): 59.1,
    ("Tasman", "80"): 26.25,
}

METRIC_HUNDREDS_MAKES = {"Highfield", "Iron", "Jeanneau", "Parker"}

# Small, explicit review layer for titles whose model name does not encode a
# length. Values were verified against manufacturer/registry specifications.
IDENTITY_OVERRIDES = {
    "-ndiytdzPio": ("Frauscher", "x Porsche 850 Fantom Air", 28.44),
    "B_tvQOJzSeI": ("SACS", "Strider 11", 36.81),
    "Es3cI1nAbhE": ("Centouno Navi", "Vespro 55", 54.13),
    "NL0jVDGVpvc": ("Centouno Navi", "Vespro 55", 54.13),
    "KBkfpbS3lCw": ("Cantiere Delle Marche", "Darwin 102", 102.0),
    "XzoKu_BS4Sw": ("Cantiere Delle Marche", "Darwin 102", 102.0),
    "R8InZglqxR0": ("Technohull", "GTX", 35.10),
    "k_0cwh40riU": ("Technohull", "GTX", 35.10),
    "ZfoqsZif_I8": ("Iguana", "Commuter", 30.18),
    "i9fptQ9a884": ("Iguana", "Commuter", 30.18),
    "g7EjccZHX1I": ("Lomac", "8.5 Gran Turismo", 27.89),
    # Companion-video and description review. These titles omit, abbreviate or
    # rename the model, but the paired description names it explicitly.
    "5R-y9vIFh00": ("Aiata", "Wayfinder 38", 38.0),
    "JVvYfGq1snQ": ("Aiata", "Wayfinder 38", 38.0),
    "Q18O4YcJ5AE": ("Whitehaven", "Harbour Classic 52", 52.0),
    "Js0IoYY357I": ("Whitehaven", "Harbour Classic 52", 52.0),
    "ymDYHloBcW8": ("Gulf Craft", "Nomad 101", 101.0),
    "YIKdcAvwrWU": ("Gulf Craft", "Nomad 101", 101.0),
    "uJBOFUd4WR8": ("Gulf Craft", "Nomad 101", 101.0),
    "0f_C5HHcN84": ("Omikron", "OT 60", 60.0),
    "h_UWIp8cpjA": ("Omikron", "OT 60", 60.0),
    "Tdg6hUmrFb8": ("Aquila", "Molokai 28", 28.0),
    "SWSEu6foWFg": ("Aquila", "Molokai 28", 28.0),
    "yoI6wnWMhrg": ("Aquila", "Molokai 47", 47.0),
    "sV754B4Pedc": ("Quarken", "35 Cabin", 35.0),
    "MrrCoWt3Dl0": ("Quarken", "35 Cabin", 35.0),
    "d_Cp9CPRsv8": ("Quarken", "27 T-Top", 27.0),
    "QkTHrT6e1Po": ("Quarken", "27 T-Top", 27.0),
    "FaPFpmyQAw4": ("Koshi", "51 GT", 51.0),
    "nUCgufOEERg": ("Koshi", "51 GT", 51.0),
    "iz0nBcsVseg": ("Wiszniewski", "W-43", 43.0),
    "emSn5apclwA": ("Wiszniewski", "W-43", 43.0),
    "uq841919wS0": ("Fairline", "F33", 33.0),
    "jxc0Sk0T6qo": ("Fairline", "F33", 33.0),
    "6L_YKjH_Jzk": ("Toy Marine", "36", 36.0),
    "ToGp7PmWpU0": ("Toy Marine", "36", 36.0),
    "zDqJ6ESgvLc": ("Parker", "Sorrento 100", 34.38),
}

NON_BOAT_OUTLIERS = {"no--l9AC1J8", "p2Nr0Rno530", "v9agV5W3Ims"}

MODEL_VARIANTS = {
    "cabin", "calypso", "conquest", "coupe", "daybridge", "dfndr", "dscvr",
    "express", "fly", "flybridge", "freedom", "gourmet", "gran", "gt", "gtc",
    "gto", "gts", "gtwa", "hardtop", "open", "rebel", "salon", "sav", "sedan",
    "sport", "sports", "smy", "sundancer", "sx", "t", "tender", "top", "tourer",
    "turismo", "vantage", "wa", "wayfinder", "xl", "xo",
}


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@dataclass
class BoatIdentity:
    make: str | None
    model: str | None
    full_name: str | None
    length_feet: float | None
    confidence: float
    method: str


class SalesCatalogue:
    def __init__(self, sqlite_path: str | Path):
        uri = f"file:{Path(sqlite_path).resolve()}?mode=ro&immutable=1"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.execute("PRAGMA query_only = ON")
        self._makes = self._load_makes()

    def _load_makes(self) -> list[tuple[str, str, int]]:
        rows = self.conn.execute(
            """
            SELECT make, COUNT(*) AS sales
            FROM sold_boats
            WHERE make IS NOT NULL AND length(trim(make)) >= 2
            GROUP BY make
            HAVING COUNT(*) >= 5
            ORDER BY length(make) DESC, sales DESC
            """
        ).fetchall()
        canonical: dict[str, tuple[str, int]] = {}
        for make, sales in rows:
            key = normalise(make)
            if key and (key not in canonical or sales > canonical[key][1]):
                canonical[key] = (make.strip(), sales)
        return [(key, value[0], value[1]) for key, value in canonical.items()]

    @lru_cache(maxsize=1024)
    def models_for_make(self, make: str) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            """
            SELECT model, COUNT(*) AS sales
            FROM sold_boats
            WHERE lower(make) = lower(?) AND model IS NOT NULL AND trim(model) <> ''
            GROUP BY model
            ORDER BY sales DESC
            """,
            (make,),
        ).fetchall()
        return [(model.strip(), sales) for model, sales in rows]

    def match(self, title: str, description: str = "", video_id: str | None = None) -> BoatIdentity:
        if video_id in NON_BOAT_OUTLIERS:
            return BoatIdentity(None, None, None, None, 1.0, "non_boat_playlist_outlier")
        if video_id in IDENTITY_OVERRIDES:
            make, model, length_feet = IDENTITY_OVERRIDES[video_id]
            return BoatIdentity(make, model, f"{make} {model}", length_feet, 0.99, "verified_official_spec")
        title_norm = normalise(title)
        source_norm = normalise(f"{title} {description[:2200]}")
        make = None
        make_key = None
        method = "unmatched"
        confidence = 0.0

        aliases = sorted(MAKE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
        for scope, label, base_confidence in ((title_norm, "title_make_alias", 0.91), (source_norm, "description_make_alias", 0.76)):
            matches = []
            for alias, canonical in aliases:
                match = re.search(rf"\b{re.escape(normalise(alias))}(?=\b|\d)", scope)
                if match:
                    matches.append((match.start(), -len(normalise(alias)), canonical, normalise(alias)))
            if matches:
                _position, _specificity, make, make_key = min(matches)
                method = label
                confidence = base_confidence
                break

        if not make:
            for scope, label, base_confidence in ((title_norm, "title_sales_make", 0.87), (source_norm, "description_sales_make", 0.70)):
                for candidate_key, candidate_make, _sales in self._makes:
                    if len(candidate_key) < 3:
                        continue
                    if re.search(rf"\b{re.escape(candidate_key)}\b", scope):
                        make = candidate_make
                        make_key = candidate_key
                        method = label
                        confidence = base_confidence
                        break
                if make:
                    break

        if not make:
            return BoatIdentity(None, None, None, extract_length(title, description), 0.0, method)

        models = self.models_for_make(make)
        model = None
        model_score = 0.0
        for candidate, _sales in models[:1200]:
            candidate_norm = normalise(candidate)
            if len(candidate_norm) < 2:
                continue
            exact = bool(re.search(rf"\b{re.escape(candidate_norm)}\b", source_norm))
            if exact:
                score = 100.0 + min(len(candidate_norm), 30) / 100.0
                if any(character.isdigit() for character in candidate_norm):
                    score += 5.0
                if candidate_norm in title_norm:
                    score += 2.0
            else:
                score = max(partial_ratio(candidate_norm, title_norm), token_set_ratio(candidate_norm, title_norm))
            if score > model_score:
                model, model_score = candidate, score

        inferred_model = infer_model_after_make(title_norm, make_key or normalise(make))
        inferred_from = "title"
        if not inferred_model:
            inferred_model = infer_model_after_make(source_norm, make_key or normalise(make))
            inferred_from = "description"
        # An explicit make + numeric model in Dan's title is stronger evidence
        # than a shorter catalogue model that happens to occur elsewhere in a
        # long description (prices, engines and competitor references are common).
        if inferred_model and any(character.isdigit() for character in inferred_model) and inferred_from == "title":
            model = inferred_model
            model_score = 97.0
            method += "+title_model"
        elif inferred_model and any(character.isdigit() for character in inferred_model) and (not model or not any(character.isdigit() for character in model)):
            model = inferred_model
            model_score = 86.0
            method += "+description_model"
        elif model_score < 70:
            model = inferred_model
            model_score = 74.0 if model else 0.0
            method += "+title_model"
        else:
            method += "+sales_model"

        if not model:
            return BoatIdentity(None, None, None, extract_length(title, description), 0.0, "make_without_model")

        confidence = min(0.99, confidence * 0.55 + (model_score / 100.0) * 0.45)
        full_name = f"{make} {model}".strip()
        return BoatIdentity(make, model, full_name, extract_length(title, description, model, make), confidence, method)


def infer_model_after_make(title_norm: str, make_norm: str) -> str | None:
    match = re.search(rf"\b{re.escape(make_norm)}(?:\s+|(?=\d))(.+)", title_norm)
    if not match:
        return None
    tokens = []
    for token in match.group(1).split():
        if token in STOP_MODEL_WORDS or len(tokens) >= 4:
            break
        tokens.append(token.upper() if token.isalnum() and len(token) <= 6 else token)
    for index in range(len(tokens) - 1):
        if not tokens[index].isdigit() or not 6 <= int(tokens[index]) <= 20:
            continue
        decimal_tail = re.fullmatch(r"(\d)([a-z]+)?", tokens[index + 1], re.I)
        if decimal_tail:
            tokens = tokens[:index] + [f"{tokens[index]}.{decimal_tail.group(1)}{(decimal_tail.group(2) or '').upper()}"] + tokens[index + 2:]
            break
    return " ".join(tokens).strip() or None


def extract_length(title: str, description: str = "", model: str = "", make: str = "") -> float | None:
    for (override_make, override_model), override in MODEL_LENGTH_OVERRIDES.items():
        if make == override_make and model.upper().startswith(override_model):
            return override
    if make == "XO":
        xo_series = re.search(r"\b([7-9]|10)\b", model)
        if xo_series:
            return round(int(xo_series.group(1)) * 3.28084, 2)
    single_metric = re.search(r"\b([7-9])(?:\.0)?\b", model)
    if single_metric and make in {"Lomac", "Nimbus"}:
        return round(int(single_metric.group(1)) * 3.28084, 2)
    decimal_model = re.search(r"(?<!\d)(\d{1,2}\.\d)(?!\d)", model)
    if decimal_model:
        value = float(decimal_model.group(1))
        if 6 <= value <= 20:
            return round(value * 3.28084, 2)
    model_number = re.search(r"(?<!\d)(\d{2,4})(?!\d)", model)
    if model_number:
        raw = model_number.group(1)
        number = int(raw)
        if len(raw) == 4 and 600 <= number <= 1500:
            value = (number / 100.0) * 3.28084
        elif len(raw) == 4 and 1800 <= number <= 9000:
            value = number / 100.0
        elif len(raw) == 3 and make in METRIC_HUNDREDS_MAKES:
            value = (number / 100.0) * 3.28084
        elif len(raw) == 3 and 180 <= number <= 999:
            value = number / 10.0
        else:
            value = float(number)
        if 18 <= value <= 200:
            return round(value, 2)
    # Only use prose dimensions after exhausting the canonical model. Long
    # descriptions commonly mention competitor sizes and engine measurements.
    for source in (title, description[:1200]):
        imperial = re.search(r"\b(\d{2}(?:\.\d)?)\s*(?:ft|foot|feet|')\b", source, re.I)
        if imperial:
            return float(imperial.group(1))
        metric = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*(?:m|metre|meter)s?\b", source, re.I)
        if metric:
            return round(float(metric.group(1)) * 3.28084, 2)
    return None


def pair_key(identity: BoatIdentity) -> str | None:
    if not identity.make or not identity.model:
        return None
    model = normalise(identity.model)
    model = re.sub(r"\bsports? motor yacht\b", "smy", model)
    tokens = re.findall(r"[a-z]*\d+(?:\.\d+)?[a-z]*|[a-z]+", model)
    number_index = next((index for index, token in enumerate(tokens) if any(char.isdigit() for char in token)), None)
    if number_index is None:
        return normalise(f"{identity.make} {identity.model}")
    if number_index and len(tokens[number_index - 1]) <= 3 and tokens[number_index - 1] not in MODEL_VARIANTS:
        core = [tokens[number_index - 1] + tokens[number_index]]
    else:
        core = [tokens[number_index]]
    for token in tokens[number_index + 1:number_index + 4]:
        if token not in MODEL_VARIANTS:
            break
        core.append(token)
    return normalise(f"{identity.make} {' '.join(core)}")
