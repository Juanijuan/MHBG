import re
import shutil
from pathlib import Path

# ========= CONFIG =========
SEARCH_TERM = "kushala"
BASE_DIR = Path(r"C:\Users\juani\Documents\MHBG\TTS_Extract")
IMAGES_DIR = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Images")
RAW_IMAGES_DIR = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Raw Images")
# ==========================

safe_name = SEARCH_TERM.lower().replace(" ", "_")
URLS_FILE = BASE_DIR / f"{safe_name}_urls.txt"
OUTPUT_DIR = BASE_DIR / f"{safe_name}_assets"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_tts_url(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", url.strip())


def load_urls(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de URLs: {path}")
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def collect_files(folder: Path):
    if not folder.exists():
        return []
    return [p for p in folder.rglob("*") if p.is_file()]


def copy_match(src: Path, dst_folder: Path, used_names: set):
    dst = dst_folder / src.name
    if dst.name in used_names:
        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while True:
            candidate = dst_folder / f"{stem}_{i}{suffix}"
            if candidate.name not in used_names:
                dst = candidate
                break
            i += 1
    shutil.copy2(src, dst)
    used_names.add(dst.name)
    return dst


urls = load_urls(URLS_FILE)
all_files = collect_files(IMAGES_DIR) + collect_files(RAW_IMAGES_DIR)

print(f"Término buscado: {SEARCH_TERM}")
print(f"URLs cargadas: {len(urls)}")
print(f"Archivos a revisar: {len(all_files)}")

used_output_names = set()
found = []
not_found = []

for url in urls:
    sanitized = sanitize_tts_url(url)
    matches = []

    # Coincidencia exacta
    for f in all_files:
        if f.name == sanitized:
            matches.append(f)

    # Coincidencia parcial
    if not matches:
        for f in all_files:
            if sanitized in f.name:
                matches.append(f)

    # Hash final de la URL
    if not matches:
        parts = [p for p in url.strip("/").split("/") if p]
        tail = parts[-1] if parts else ""
        if tail:
            tail_lower = tail.lower()
            for f in all_files:
                if tail_lower in f.name.lower():
                    matches.append(f)

    if matches:
        copied = []
        for m in matches:
            dst = copy_match(m, OUTPUT_DIR, used_output_names)
            copied.append(str(dst))
        found.append((url, copied))
    else:
        not_found.append(url)

print("\nRESULTADOS")
print("=" * 60)
print(f"URLs encontradas: {len(found)}")
print(f"URLs no encontradas: {len(not_found)}")

report_path = OUTPUT_DIR / f"reporte_{safe_name}.txt"
with report_path.open("w", encoding="utf-8") as rep:
    rep.write(f"REPORTE DE EXTRACCIÓN {SEARCH_TERM.upper()}\n")
    rep.write("=" * 60 + "\n\n")

    rep.write("ENCONTRADAS\n")
    rep.write("-" * 30 + "\n")
    for url, files in found:
        rep.write(f"URL: {url}\n")
        for file in files:
            rep.write(f"  -> {file}\n")
        rep.write("\n")

    rep.write("\nNO ENCONTRADAS\n")
    rep.write("-" * 30 + "\n")
    for url in not_found:
        rep.write(f"{url}\n")

print(f"\nReporte guardado en: {report_path}")
print(f"Archivos copiados en: {OUTPUT_DIR}")