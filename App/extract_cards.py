import argparse
import json
from copy import deepcopy
from pathlib import Path

from image_importer import import_images_from_urls, sanitize_search_name
from project_paths import CARD_OUTPUTS_DIR, INPUT_DIR


SEARCH_TERM = "kirin"
DEFAULT_MOD_JSON = INPUT_DIR / "mods.json"
OUTPUT_DIR = CARD_OUTPUTS_DIR
SEARCH_FIELDS = ("Nickname", "Name", "Description", "GMNotes")
IMAGE_HINTS = (
    "steamusercontent",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
)


def matches_search(obj: dict, search_term: str) -> bool:
    if not isinstance(obj, dict):
        return False

    term = (search_term or "").strip().lower()
    if not term:
        return False

    for field in SEARCH_FIELDS:
        value = obj.get(field, "")
        if isinstance(value, str) and term in value.lower():
            return True

    return False


def is_image_url(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    lowered = url.lower()
    return any(hint in lowered for hint in IMAGE_HINTS)


def collect_image_urls(obj, urls: set[str]) -> None:
    if isinstance(obj, dict):
        for field in ("FaceURL", "BackURL", "ImageURL"):
            value = obj.get(field, "")
            if is_image_url(value):
                urls.add(value)

        custom_deck = obj.get("CustomDeck", {})
        if isinstance(custom_deck, dict):
            for deck in custom_deck.values():
                if not isinstance(deck, dict):
                    continue
                for field in ("FaceURL", "BackURL"):
                    value = deck.get(field, "")
                    if is_image_url(value):
                        urls.add(value)

        custom_image = obj.get("CustomImage", {})
        if isinstance(custom_image, dict):
            for field in ("ImageURL", "ImageSecondaryURL"):
                value = custom_image.get(field, "")
                if is_image_url(value):
                    urls.add(value)

        for value in obj.values():
            collect_image_urls(value, urls)

    elif isinstance(obj, list):
        for item in obj:
            collect_image_urls(item, urls)


def contains_target(obj, search_term: str) -> bool:
    if isinstance(obj, dict):
        if matches_search(obj, search_term):
            return True
        return any(contains_target(value, search_term) for value in obj.values())

    if isinstance(obj, list):
        return any(contains_target(item, search_term) for item in obj)

    return False


def prune(obj, search_term: str, urls: set[str]):
    if isinstance(obj, dict):
        if matches_search(obj, search_term):
            collect_image_urls(obj, urls)
            return deepcopy(obj)

        if not contains_target(obj, search_term):
            return None

        new_obj = {}
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                pruned = prune(value, search_term, urls)
                if pruned is not None:
                    new_obj[key] = pruned
            else:
                new_obj[key] = value

        return new_obj

    if isinstance(obj, list):
        new_list = []
        for item in obj:
            pruned = prune(item, search_term, urls)
            if pruned is not None:
                new_list.append(pruned)
        return new_list if new_list else None

    return obj


def write_report(report_path: Path, search_term: str, mod_json: Path, out_json: Path, out_urls: Path, urls: list[str], imported_summary: dict | None) -> None:
    with report_path.open("w", encoding="utf-8") as report:
        report.write("CARD EXTRACTION REPORT\n")
        report.write("=" * 60 + "\n\n")
        report.write(f"Search term: {search_term}\n")
        report.write(f"Source JSON: {mod_json}\n")
        report.write(f"Subset JSON: {out_json}\n")
        report.write(f"URL list: {out_urls}\n")
        report.write(f"Unique URLs found: {len(urls)}\n")

        if imported_summary is not None:
            report.write(f"Imported images: {imported_summary['copied_count']}\n")
            report.write(f"Cache URLs not found: {imported_summary['not_found_count']}\n")
            report.write(f"Non-image matches skipped: {imported_summary['skipped_non_images_count']}\n")
            report.write(f"Import report: {imported_summary['report_path']}\n")

        report.write("\nURLS\n")
        report.write("-" * 30 + "\n")
        for url in urls:
            report.write(f"{url}\n")


def extract_cards(search_term: str, mod_json: Path = DEFAULT_MOD_JSON, output_dir: Path = OUTPUT_DIR, auto_import: bool = True) -> dict:
    search_term = (search_term or "").strip()
    if not search_term:
        raise ValueError("Search cannot be empty.")

    safe_name = sanitize_search_name(search_term)
    search_dir = output_dir / safe_name
    search_dir.mkdir(parents=True, exist_ok=True)

    out_json = search_dir / "subset.json"
    out_urls = search_dir / "urls.txt"
    report_path = search_dir / "report.txt"

    with mod_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    urls: set[str] = set()
    subset = {}

    for key, value in data.items():
        if key == "ObjectStates" and isinstance(value, list):
            filtered_states = []
            for state in value:
                pruned = prune(state, search_term, urls)
                if pruned is not None:
                    filtered_states.append(pruned)
            subset[key] = filtered_states
        else:
            subset[key] = deepcopy(value)

    sorted_urls = sorted(urls)

    with out_json.open("w", encoding="utf-8") as handle:
        json.dump(subset, handle, ensure_ascii=False, indent=2)

    with out_urls.open("w", encoding="utf-8") as handle:
        for url in sorted_urls:
            handle.write(url + "\n")

    imported_summary = None
    if auto_import:
        imported_summary = import_images_from_urls(
            search_term=search_term,
            urls_file=out_urls,
            output_dir=search_dir / "assets",
        )

    write_report(
        report_path=report_path,
        search_term=search_term,
        mod_json=mod_json,
        out_json=out_json,
        out_urls=out_urls,
        urls=sorted_urls,
        imported_summary=imported_summary,
    )

    print("Done.")
    print(f"Search term: {search_term}")
    print(f"Subset JSON: {out_json}")
    print(f"URL list: {out_urls}")
    print(f"Report: {report_path}")
    print(f"Unique URLs found: {len(sorted_urls)}")

    if imported_summary is not None:
        print(f"Imported images: {imported_summary['copied_count']}")
        print(f"Cache URLs not found: {imported_summary['not_found_count']}")

    print("\nFirst URLs:")
    for index, url in enumerate(sorted_urls[:20], start=1):
        print(f"{index}. {url}")

    return {
        "search_term": search_term,
        "search_dir": search_dir,
        "subset_json": out_json,
        "urls_file": out_urls,
        "report_path": report_path,
        "url_count": len(sorted_urls),
        "imported_summary": imported_summary,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract cards and related images from mods.json."
    )
    parser.add_argument(
        "--search",
        default=SEARCH_TERM,
        help="Text to search inside Nickname, Name, Description, or GMNotes.",
    )
    parser.add_argument(
        "--mods-json",
        type=Path,
        default=DEFAULT_MOD_JSON,
        help="Path to the source mods.json file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Base output folder. Results are written to <output-dir>/<search>/",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Only create the subset JSON and URL list, without importing images from the cache.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    extract_cards(
        search_term=args.search,
        mod_json=args.mods_json,
        output_dir=args.output_dir,
        auto_import=not args.skip_import,
    )


if __name__ == "__main__":
    main()
