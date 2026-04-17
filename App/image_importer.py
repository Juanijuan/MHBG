import argparse
import re
import shutil
from pathlib import Path

from project_paths import CARD_OUTPUTS_DIR, TTS_IMAGES_DIR, TTS_RAW_IMAGES_DIR

SEARCH_TERM = "kirin"
BASE_DIR = CARD_OUTPUTS_DIR
IMAGES_DIR = TTS_IMAGES_DIR
RAW_IMAGES_DIR = TTS_RAW_IMAGES_DIR
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def sanitize_search_name(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_\-]", "", value)
    return value if value else "all"


def pretty_prefix(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text or "")
    if not parts:
        return "Asset"
    return "_".join(part.capitalize() for part in parts)


def sanitize_tts_url(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (url or "").strip())


def load_urls(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"URL file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def collect_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return [path for path in folder.rglob("*") if path.is_file()]


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def find_matches_for_url(url: str, all_files: list[Path]) -> list[Path]:
    sanitized = sanitize_tts_url(url)
    matches: list[Path] = []

    for file_path in all_files:
        if file_path.name == sanitized:
            matches.append(file_path)

    if not matches and sanitized:
        for file_path in all_files:
            if sanitized in file_path.name:
                matches.append(file_path)

    if not matches:
        parts = [part for part in url.strip("/").split("/") if part]
        tail = parts[-1] if parts else ""
        if tail:
            tail_lower = tail.lower()
            for file_path in all_files:
                if tail_lower in file_path.name.lower():
                    matches.append(file_path)

    unique_matches = []
    seen = set()
    for match in matches:
        key = str(match.resolve())
        if key not in seen:
            seen.add(key)
            unique_matches.append(match)

    return unique_matches


def copy_match(src: Path, dst_folder: Path, prefix: str, counter: int) -> Path:
    suffix = src.suffix.lower() or ".png"
    candidate = dst_folder / f"{prefix}_{counter}{suffix}"

    while candidate.exists():
        counter += 1
        candidate = dst_folder / f"{prefix}_{counter}{suffix}"

    shutil.copy2(src, candidate)
    return candidate


def import_images_from_urls(
    search_term: str,
    urls_file: Path,
    output_dir: Path,
    images_dir: Path = IMAGES_DIR,
    raw_images_dir: Path = RAW_IMAGES_DIR,
) -> dict:
    urls = load_urls(urls_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_files = collect_files(images_dir) + collect_files(raw_images_dir)

    print(f"Search term: {search_term}")
    print(f"Loaded URLs: {len(urls)}")
    print(f"Files to scan: {len(all_files)}")

    prefix = pretty_prefix(search_term)
    copied_rows = []
    not_found = []
    skipped_non_images = []
    copied_sources = set()
    next_index = 1

    for url in urls:
        matches = find_matches_for_url(url, all_files)

        if not matches:
            not_found.append(url)
            continue

        copied_for_url = []
        for match in matches:
            resolved = str(match.resolve())

            if not is_supported_image(match):
                skipped_non_images.append(str(match))
                continue

            if resolved in copied_sources:
                continue

            dst = copy_match(match, output_dir, prefix, next_index)
            copied_sources.add(resolved)
            copied_for_url.append(str(dst))
            copied_rows.append((url, str(match), str(dst)))
            next_index += 1

        if not copied_for_url and all(not is_supported_image(match) for match in matches):
            not_found.append(url)

    report_path = output_dir / "import_report.txt"
    with report_path.open("w", encoding="utf-8") as report:
        report.write(f"IMPORT REPORT {pretty_prefix(search_term).upper()}\n")
        report.write("=" * 60 + "\n\n")
        report.write(f"URL file: {urls_file}\n")
        report.write(f"Output directory: {output_dir}\n")
        report.write(f"Files scanned: {len(all_files)}\n")
        report.write(f"Copied files: {len(copied_rows)}\n")
        report.write(f"URLs not found: {len(not_found)}\n")
        report.write(f"Non-image matches skipped: {len(skipped_non_images)}\n\n")

        report.write("COPIED\n")
        report.write("-" * 30 + "\n")
        for url, src, dst in copied_rows:
            report.write(f"URL: {url}\n")
            report.write(f"  Source: {src}\n")
            report.write(f"  Copied: {dst}\n\n")

        report.write("NOT FOUND\n")
        report.write("-" * 30 + "\n")
        for url in not_found:
            report.write(f"{url}\n")

        report.write("\nNON-IMAGE MATCHES SKIPPED\n")
        report.write("-" * 30 + "\n")
        for src in skipped_non_images:
            report.write(f"{src}\n")

    print("\nRESULTS")
    print("=" * 60)
    print(f"Copied files: {len(copied_rows)}")
    print(f"URLs not found: {len(not_found)}")
    print(f"Non-image matches skipped: {len(skipped_non_images)}")
    print(f"Report saved to: {report_path}")
    print(f"Copied files saved in: {output_dir}")

    return {
        "search_term": search_term,
        "urls_file": urls_file,
        "output_dir": output_dir,
        "copied_count": len(copied_rows),
        "not_found_count": len(not_found),
        "skipped_non_images_count": len(skipped_non_images),
        "copied_rows": copied_rows,
        "not_found": not_found,
        "skipped_non_images": skipped_non_images,
        "report_path": report_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import images from the TTS cache using a URL list."
    )
    parser.add_argument(
        "--search",
        default=SEARCH_TERM,
        help="Base text used to locate the URL list and rename the imported images.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=BASE_DIR,
        help="Base folder where card extraction outputs its search folders.",
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        help="Direct path to the URL list. Defaults to <base>/<search>/urls.txt.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output folder. Defaults to <base>/<search>/assets.",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=IMAGES_DIR,
        help="TTS Images cache folder.",
    )
    parser.add_argument(
        "--raw-images-dir",
        type=Path,
        default=RAW_IMAGES_DIR,
        help="TTS Raw Images cache folder.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    safe_name = sanitize_search_name(args.search)
    search_dir = args.base_dir / safe_name
    urls_file = args.urls_file or (search_dir / "urls.txt")
    output_dir = args.output_dir or (search_dir / "assets")

    import_images_from_urls(
        search_term=args.search,
        urls_file=urls_file,
        output_dir=output_dir,
        images_dir=args.images_dir,
        raw_images_dir=args.raw_images_dir,
    )


if __name__ == "__main__":
    main()
