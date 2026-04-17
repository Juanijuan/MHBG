import re


SFG_SCALE_REFERENCES = [
    {
        "key": "hunter",
        "label": "Hunters / hunter weapon classes",
        "aliases": [
            "hunter",
            "hunters",
            "great sword",
            "long sword",
            "sword and shield",
            "dual blades",
            "hammer",
            "hunting horn",
            "lance",
            "gunlance",
            "switch axe",
            "charge blade",
            "insect glaive",
            "bow",
            "light bowgun",
            "heavy bowgun",
        ],
        "height_text": "33 mm",
        "height_mm": 33,
        "base_text": None,
        "notes": "Official SFG hunter miniature height, including the base.",
    },
    {
        "key": "teostra",
        "label": "Teostra",
        "aliases": ["teostra"],
        "height_text": "100 mm",
        "height_mm": 100,
        "base_text": "120 mm",
        "notes": "Official SFG height, including the base.",
    },
    {
        "key": "nergigante",
        "label": "Nergigante",
        "aliases": ["nergigante"],
        "height_text": "160 mm",
        "height_mm": 160,
        "base_text": "120 mm",
        "notes": "Official SFG height, including the base.",
    },
    {
        "key": "kushala_daora",
        "label": "Kushala Daora",
        "aliases": ["kushala daora", "kushala"],
        "height_text": ">255 mm",
        "height_mm": 255,
        "base_text": None,
        "notes": "Official SFG height is more than 255 mm, including the base.",
    },
    {
        "key": "kirin",
        "label": "Kirin",
        "aliases": ["kirin"],
        "height_text": None,
        "height_mm": None,
        "base_text": "100 mm",
        "notes": "No official SFG height is stored in this reference table yet. Use the official base size as the first scale anchor.",
    },
    {
        "key": "kulu_ya_ku",
        "label": "Kulu-Ya-Ku",
        "aliases": ["kulu ya ku", "kulu-ya-ku"],
        "height_text": None,
        "height_mm": None,
        "base_text": "60 mm",
        "notes": "No official SFG height is stored in this reference table yet. Use the official base size as the first scale anchor.",
    },
    {
        "key": "diablos_family",
        "label": "Diablos / Black Diablos",
        "aliases": ["black diablos", "diablos"],
        "height_text": None,
        "height_mm": None,
        "base_text": "120 mm",
        "notes": "No official SFG height is stored in this reference table yet. Use the official base size as the first scale anchor.",
    },
    {
        "key": "general_monster_range",
        "label": "General monster reference",
        "aliases": [
            "great jagras",
            "barroth",
            "rathalos",
            "azure rathalos",
            "pukei pukei",
            "jyuratodus",
            "tobi kadachi",
            "anjanath",
            "tzitzi ya ku",
            "great girros",
            "radobaan",
            "barioth",
            "rajang",
        ],
        "height_text": None,
        "height_mm": None,
        "base_text": "100-120 mm",
        "notes": "No exact official SFG height is stored in this reference table. For these monsters, the official base range is usually 100-120 mm.",
    },
]


def normalize_scale_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _match_alias(alias: str, normalized_text: str) -> bool:
    normalized_alias = normalize_scale_text(alias)
    if not normalized_alias:
        return False
    padded_text = f" {normalized_text} "
    padded_alias = f" {normalized_alias} "
    return padded_alias in padded_text


def lookup_official_scale_reference(*texts: str) -> dict:
    normalized_text = normalize_scale_text(" | ".join(text for text in texts if text))
    best_match = None
    best_alias = ""

    for entry in SFG_SCALE_REFERENCES:
        for alias in entry["aliases"]:
            if _match_alias(alias, normalized_text) and len(alias) > len(best_alias):
                best_match = entry
                best_alias = alias

    if not best_match:
        return {
            "matched": False,
            "match_alias": "",
            "label": "Unknown",
            "height_text": None,
            "height_mm": None,
            "base_text": None,
            "notes": "No official SFG scale reference matched this search.",
            "summary": "Official SFG height: not available in the local reference table.",
        }

    summary_parts = []
    if best_match["height_text"]:
        summary_parts.append(f"Official SFG height: {best_match['height_text']}")
    else:
        summary_parts.append("Official SFG height: not available in the local reference table")

    if best_match.get("base_text"):
        summary_parts.append(f"Official base: {best_match['base_text']}")

    if best_match.get("notes"):
        summary_parts.append(best_match["notes"])

    return {
        "matched": True,
        "match_alias": best_alias,
        "label": best_match["label"],
        "height_text": best_match["height_text"],
        "height_mm": best_match["height_mm"],
        "base_text": best_match["base_text"],
        "notes": best_match["notes"],
        "summary": " | ".join(summary_parts),
    }
