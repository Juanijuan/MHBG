import json
from copy import deepcopy
from pathlib import Path

# ========= CONFIG =========
SEARCH_TERM = "kushala"
MOD_JSON = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Workshop\mods.json")
OUTPUT_DIR = Path(r"C:\Users\juani\Documents\MHBG\TTS_Extract")
# ==========================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

safe_name = SEARCH_TERM.lower().replace(" ", "_")
OUT_JSON = OUTPUT_DIR / f"{safe_name}_subset.json"
OUT_URLS = OUTPUT_DIR / f"{safe_name}_urls.txt"

IMAGE_HINTS = (
    "steamusercontent",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
)

with MOD_JSON.open("r", encoding="utf-8") as f:
    data = json.load(f)

urls = set()


def is_image_url(url):
    if not isinstance(url, str) or not url.strip():
        return False
    u = url.lower()
    return any(hint in u for hint in IMAGE_HINTS)


def has_target_nickname(obj):
    if not isinstance(obj, dict):
        return False
    nickname = obj.get("Nickname", "")
    return isinstance(nickname, str) and SEARCH_TERM.lower() in nickname.lower()


def collect_image_urls(obj):
    if isinstance(obj, dict):
        face = obj.get("FaceURL", "")
        back = obj.get("BackURL", "")

        if is_image_url(face):
            urls.add(face)
        if is_image_url(back):
            urls.add(back)

        custom_deck = obj.get("CustomDeck", {})
        if isinstance(custom_deck, dict):
            for deck in custom_deck.values():
                if isinstance(deck, dict):
                    face = deck.get("FaceURL", "")
                    back = deck.get("BackURL", "")
                    if is_image_url(face):
                        urls.add(face)
                    if is_image_url(back):
                        urls.add(back)

        for v in obj.values():
            collect_image_urls(v)

    elif isinstance(obj, list):
        for item in obj:
            collect_image_urls(item)


def contains_target(obj):
    if isinstance(obj, dict):
        if has_target_nickname(obj):
            return True
        return any(contains_target(v) for v in obj.values())

    elif isinstance(obj, list):
        return any(contains_target(item) for item in obj)

    return False


def prune(obj):
    if isinstance(obj, dict):
        if has_target_nickname(obj):
            collect_image_urls(obj)
            return deepcopy(obj)

        if not contains_target(obj):
            return None

        new_obj = {}
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                pruned = prune(v)
                if pruned is not None:
                    new_obj[k] = pruned
            else:
                new_obj[k] = v

        return new_obj

    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            pruned = prune(item)
            if pruned is not None:
                new_list.append(pruned)
        return new_list if new_list else None

    return obj


subset = {}
for k, v in data.items():
    if k == "ObjectStates" and isinstance(v, list):
        filtered_states = []
        for state in v:
            pruned = prune(state)
            if pruned is not None:
                filtered_states.append(pruned)
        subset[k] = filtered_states
    else:
        subset[k] = deepcopy(v)

with OUT_JSON.open("w", encoding="utf-8") as f:
    json.dump(subset, f, ensure_ascii=False, indent=2)

with OUT_URLS.open("w", encoding="utf-8") as f:
    for url in sorted(urls):
        f.write(url + "\n")

print("Hecho.")
print("Término buscado:", SEARCH_TERM)
print("JSON reducido:", OUT_JSON)
print("TXT de URLs:", OUT_URLS)
print("URLs únicas encontradas:", len(urls))

print("\nPrimeras URLs:")
for i, url in enumerate(sorted(urls)[:20], start=1):
    print(f"{i}. {url}")