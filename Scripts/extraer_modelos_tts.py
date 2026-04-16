import json
import re
import shutil
from pathlib import Path

# =========================================================
# CONFIGURACIÓN
# =========================================================

SEARCH_TERM = "kushala"
# Ejemplos:
# SEARCH_TERM = "hunter"
# SEARCH_TERM = "teostra"
# SEARCH_TERM = "kirin"
# SEARCH_TERM = ""
# Si está vacío, extrae todos los modelos encontrados.
MOD_JSON = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Workshop\mods.json")

MODELS_DIR = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Models")
IMAGES_DIR = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Images")
RAW_IMAGES_DIR = Path(r"C:\Users\juani\Documents\My Games\Tabletop Simulator\Mods\Raw Images")

OUTPUT_BASE_DIR = Path(r"C:\Users\juani\Documents\MHBG\Modelos 3d")

# Si True, ignora modelos genéricos repetidos sin nombre útil
SKIP_GENERIC_OBJECTS = True

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def sanitize_name(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_\-]", "", text)
    return text if text else "all_models"


def sanitize_tts_url(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", url.strip())


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_files(folder: Path):
    if not folder.exists():
        return []
    return [p for p in folder.rglob("*") if p.is_file()]


def match_text(value: str, term: str) -> bool:
    if not isinstance(value, str):
        return False
    if not term:
        return True
    return term.lower() in value.lower()


def object_has_model(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False

    custom_mesh = obj.get("CustomMesh", {})
    if isinstance(custom_mesh, dict):
        mesh = custom_mesh.get("MeshURL", "")
        if isinstance(mesh, str) and mesh.strip():
            return True

    # Por si algún objeto lo tuviera en raíz
    for field in ("MeshURL", "ModelURL"):
        value = obj.get(field, "")
        if isinstance(value, str) and value.strip():
            return True

    return False


def object_matches_search(obj: dict, term: str) -> bool:
    if not isinstance(obj, dict):
        return False

    if not object_has_model(obj):
        return False

    nickname = obj.get("Nickname", "")
    name = obj.get("Name", "")
    description = obj.get("Description", "")
    gmnotes = obj.get("GMNotes", "")

    if not term:
        return True

    fields = [nickname, name, description, gmnotes]

    for value in fields:
        if match_text(value, term):
            return True

    # fallback: busca dentro del bloque serializado
    try:
        blob = json.dumps(obj, ensure_ascii=False)
        if term.lower() in blob.lower():
            return True
    except Exception:
        pass

    return False


def extract_urls(obj: dict):
    urls = {}

    # En raíz, por si acaso
    for field in ("MeshURL", "ModelURL", "ColliderURL", "DiffuseURL", "NormalURL", "SpecularURL", "ImageURL"):
        value = obj.get(field, "")
        if isinstance(value, str) and value.strip():
            urls[field] = value.strip()

    # Dentro de CustomMesh, que es el caso importante
    custom_mesh = obj.get("CustomMesh", {})
    if isinstance(custom_mesh, dict):
        for field in ("MeshURL", "DiffuseURL", "NormalURL", "ColliderURL"):
            value = custom_mesh.get(field, "")
            if isinstance(value, str) and value.strip():
                urls[f"CustomMesh.{field}"] = value.strip()

    return urls


def is_generic_object(obj: dict) -> bool:
    """
    Intenta excluir bolsas genéricas, nodos y objetos poco útiles cuando no tienen nombre específico.
    """
    nickname = (obj.get("Nickname", "") or "").strip().lower()
    name = (obj.get("Name", "") or "").strip().lower()

    generic_names = {
        "custom_model_bag",
        "custom_model_infinite_bag",
    }

    generic_nick_fragments = {
        "nodes",
        "time cards",
        "damage deck",
        "track tokens",
    }

    if name in generic_names:
        if not nickname:
            return True
        for frag in generic_nick_fragments:
            if frag in nickname:
                return True

    return False


def walk_models(obj, path="root", results=None, term=""):
    if results is None:
        results = []

    if isinstance(obj, dict):
        if object_matches_search(obj, term):
            if not (SKIP_GENERIC_OBJECTS and is_generic_object(obj)):
                entry = {
                    "path": path,
                    "nickname": obj.get("Nickname", ""),
                    "name": obj.get("Name", ""),
                    "guid": obj.get("GUID", ""),
                    "description": obj.get("Description", ""),
                    "gmnotes": obj.get("GMNotes", ""),
                    "urls": extract_urls(obj),
                }
                results.append(entry)

        for k, v in obj.items():
            walk_models(v, f"{path}/{k}", results, term)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            walk_models(item, f"{path}[{i}]", results, term)

    return results


def find_cached_files_for_url(url: str, all_files):
    matches = []

    sanitized = sanitize_tts_url(url)
    parts = [p for p in url.strip("/").split("/") if p]
    tail = parts[-1].lower() if parts else ""

    for f in all_files:
        name_lower = f.name.lower()

        if f.name == sanitized:
            matches.append(f)
            continue

        if sanitized.lower() in name_lower:
            matches.append(f)
            continue

        if tail and tail in name_lower:
            matches.append(f)
            continue

    # quitar duplicados
    unique = []
    seen = set()
    for m in matches:
        key = str(m.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


def copy_with_unique_name(src: Path, dst_folder: Path, prefix: str, used_names: set):
    suffix = src.suffix
    base_name = f"{prefix}_{src.name}" if prefix else src.name
    dst = dst_folder / base_name

    if dst.name in used_names:
        stem = dst.stem
        suffix = dst.suffix
        idx = 1
        while True:
            candidate = dst_folder / f"{stem}_{idx}{suffix}"
            if candidate.name not in used_names:
                dst = candidate
                break
            idx += 1

    shutil.copy2(src, dst)
    used_names.add(dst.name)
    return dst


# =========================================================
# EJECUCIÓN
# =========================================================

if not MOD_JSON.exists():
    raise FileNotFoundError(f"No existe el JSON del mod: {MOD_JSON}")

safe_term = sanitize_name(SEARCH_TERM)
OUTPUT_DIR = OUTPUT_BASE_DIR / safe_term
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_FILE = OUTPUT_DIR / f"reporte_{safe_term}.txt"
JSON_FILE = OUTPUT_DIR / f"objetos_{safe_term}.json"
URLS_FILE = OUTPUT_DIR / f"urls_{safe_term}.txt"

print("Cargando JSON...")
data = load_json(MOD_JSON)

print("Buscando objetos con modelos 3D...")
results = walk_models(data, term=SEARCH_TERM)

print(f"Objetos encontrados: {len(results)}")

with JSON_FILE.open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

all_urls = []
seen_urls = set()

for item in results:
    for field, url in item["urls"].items():
        if url not in seen_urls:
            seen_urls.add(url)
            all_urls.append((field, url))

with URLS_FILE.open("w", encoding="utf-8") as f:
    for field, url in all_urls:
        f.write(f"{field}\t{url}\n")

print(f"URLs únicas recogidas: {len(all_urls)}")

print("Indexando caché local...")
all_files = []
all_files += collect_files(MODELS_DIR)
all_files += collect_files(IMAGES_DIR)
all_files += collect_files(RAW_IMAGES_DIR)

print(f"Archivos en caché revisados: {len(all_files)}")

used_output_names = set()
copied_files = []
not_found_urls = []

for idx, item in enumerate(results, start=1):
    nickname = item["nickname"].strip() or item["name"].strip() or f"objeto_{idx}"
    short_name = sanitize_name(nickname)[:50]

    for field, url in item["urls"].items():
        matches = find_cached_files_for_url(url, all_files)

        if matches:
            for src in matches:
                prefix = f"{idx:03d}_{short_name}_{field.replace('.', '_')}"
                dst = copy_with_unique_name(src, OUTPUT_DIR, prefix, used_output_names)
                copied_files.append({
                    "object_index": idx,
                    "nickname": nickname,
                    "field": field,
                    "url": url,
                    "source": str(src),
                    "copied_to": str(dst),
                })
        else:
            not_found_urls.append({
                "object_index": idx,
                "nickname": nickname,
                "field": field,
                "url": url,
            })

with REPORT_FILE.open("w", encoding="utf-8") as rep:
    rep.write("REPORTE DE EXTRACCIÓN DE MODELOS TTS\n")
    rep.write("=" * 80 + "\n\n")
    rep.write(f"Término de búsqueda: {SEARCH_TERM!r}\n")
    rep.write(f"JSON origen: {MOD_JSON}\n")
    rep.write(f"Objetos encontrados: {len(results)}\n")
    rep.write(f"URLs únicas: {len(all_urls)}\n")
    rep.write(f"Archivos copiados: {len(copied_files)}\n")
    rep.write(f"URLs no encontradas en caché: {len(not_found_urls)}\n\n")

    rep.write("OBJETOS ENCONTRADOS\n")
    rep.write("-" * 80 + "\n")
    for idx, item in enumerate(results, start=1):
        rep.write(f"[{idx:03d}] Nickname : {item['nickname']}\n")
        rep.write(f"      Name     : {item['name']}\n")
        rep.write(f"      GUID     : {item['guid']}\n")
        rep.write(f"      Ruta     : {item['path']}\n")
        if item["urls"]:
            rep.write("      URLs:\n")
            for field, url in item["urls"].items():
                rep.write(f"        - {field}: {url}\n")
        else:
            rep.write("      URLs: (ninguna)\n")
        rep.write("\n")

    rep.write("\nARCHIVOS COPIADOS\n")
    rep.write("-" * 80 + "\n")
    for row in copied_files:
        rep.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
        rep.write(f"      Campo   : {row['field']}\n")
        rep.write(f"      URL     : {row['url']}\n")
        rep.write(f"      Origen  : {row['source']}\n")
        rep.write(f"      Copiado : {row['copied_to']}\n\n")

    rep.write("\nURLS NO ENCONTRADAS EN CACHÉ\n")
    rep.write("-" * 80 + "\n")
    for row in not_found_urls:
        rep.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
        rep.write(f"      Campo: {row['field']}\n")
        rep.write(f"      URL  : {row['url']}\n\n")

print("\nProceso terminado.")
print(f"Carpeta de salida: {OUTPUT_DIR}")
print(f"Reporte: {REPORT_FILE}")
print(f"JSON de objetos: {JSON_FILE}")
print(f"TXT de URLs: {URLS_FILE}")
print(f"Archivos copiados: {len(copied_files)}")
print(f"URLs no encontradas: {len(not_found_urls)}")