import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from project_paths import (
    INPUT_DIR,
    MODEL_OUTPUTS_DIR,
    TTS_ASSETBUNDLES_DIR,
    TTS_IMAGES_DIR,
    TTS_MODELS_DIR,
    TTS_RAW_IMAGES_DIR,
)
from scale_reference import lookup_official_scale_reference


# =========================================================
# CONFIGURATION
# =========================================================

# Puedes dejarlo vacío y pasar la búsqueda por consola:
#   python App\extract_models.py --search kirin
#   python App\extract_models.py --search "great sword"
# O fijar aquí una búsqueda por defecto para no escribirla cada vez.
SEARCH_TERM = "kirin"
DEFAULT_MOD_JSON = INPUT_DIR / "mods.json"

ASSETBUNDLES_DIR = TTS_ASSETBUNDLES_DIR
MODELS_DIR = TTS_MODELS_DIR
IMAGES_DIR = TTS_IMAGES_DIR
RAW_IMAGES_DIR = TTS_RAW_IMAGES_DIR

OUTPUT_BASE_DIR = MODEL_OUTPUTS_DIR
UNITYPY_SITE_PACKAGES = Path(__file__).resolve().parents[1] / "Tools" / "unitypy-venv" / "Lib" / "site-packages"

SEARCH_FIELDS = ("Nickname", "Name", "Description", "GMNotes")
GENERIC_CONTAINER_NAMES = {
    "bag",
    "custom_assetbundle_bag",
    "custom_model_bag",
    "custom_model_infinite_bag",
    "infinite_bag",
}
HELPER_FRAGMENTS = {
    "ammo",
    "bag",
    "box",
    "card",
    "cards",
    "counter",
    "damage",
    "deck",
    "effect",
    "elemental",
    "helper",
    "kinsect",
    "marker",
    "markers",
    "node",
    "nodes",
    "reference",
    "token",
    "tokens",
    "track",
}
HIGH_REUSE_MESH_THRESHOLD = 12
MIN_SELECTION_SCORE = 0


# =========================================================
# CLI
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract real 3D models from mods.json and the local TTS cache."
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
        help="Path to the mods.json exported from TTS.",
    )
    parser.add_argument(
        "--output-base",
        type=Path,
        default=OUTPUT_BASE_DIR,
        help="Base output folder. Results are written to <output-base>/<search>/",
    )
    return parser.parse_args()


# =========================================================
# HELPERS
# =========================================================

def sanitize_name(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_\-]", "", value)
    return value if value else "all_models"


def sanitize_tts_url(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (url or "").strip())


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_files(folder: Path):
    if not folder.exists():
        return []
    return [path for path in folder.rglob("*") if path.is_file()]


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def field_texts(obj: dict):
    return {field: str(obj.get(field, "") or "") for field in SEARCH_FIELDS}


def joined_search_text(values: dict) -> str:
    return " | ".join(values[field] for field in SEARCH_FIELDS if values[field])


def match_fields(values: dict, term: str):
    if not term:
        return list(values.keys())

    term_lower = term.lower()
    matches = []
    for field, value in values.items():
        if isinstance(value, str) and term_lower in value.lower():
            matches.append(field)
    return matches


def object_type(obj: dict) -> str:
    return normalize_text(str(obj.get("Name", "") or ""))


def is_object_record(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False

    marker_keys = {
        "AltLookAngle",
        "Bag",
        "ChildObjects",
        "ColorDiffuse",
        "ContainedObjects",
        "Description",
        "DragSelectable",
        "GMNotes",
        "GUID",
        "Grid",
        "LuaScript",
        "Name",
        "Nickname",
        "States",
        "Transform",
    }
    return any(key in obj for key in marker_keys)


def object_has_model(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False

    custom_mesh = obj.get("CustomMesh", {})
    if isinstance(custom_mesh, dict):
        mesh = custom_mesh.get("MeshURL", "")
        if isinstance(mesh, str) and mesh.strip():
            return True

    for field in ("MeshURL", "ModelURL"):
        value = obj.get(field, "")
        if isinstance(value, str) and value.strip():
            return True

    return False


def object_has_assetbundle(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False

    bundle = obj.get("CustomAssetbundle", {})
    if not isinstance(bundle, dict):
        return False

    for field in ("AssetbundleURL", "AssetbundleSecondaryURL"):
        value = bundle.get(field, "")
        if isinstance(value, str) and value.strip():
            return True

    return False


def extract_urls(obj: dict):
    urls = {}

    for field in ("MeshURL", "ModelURL", "ColliderURL", "DiffuseURL", "NormalURL", "SpecularURL", "ImageURL"):
        value = obj.get(field, "")
        if isinstance(value, str) and value.strip():
            urls[field] = value.strip()

    custom_mesh = obj.get("CustomMesh", {})
    if isinstance(custom_mesh, dict):
        for field in ("MeshURL", "DiffuseURL", "NormalURL", "ColliderURL"):
            value = custom_mesh.get(field, "")
            if isinstance(value, str) and value.strip():
                urls[f"CustomMesh.{field}"] = value.strip()

    custom_assetbundle = obj.get("CustomAssetbundle", {})
    if isinstance(custom_assetbundle, dict):
        for field in ("AssetbundleURL", "AssetbundleSecondaryURL"):
            value = custom_assetbundle.get(field, "")
            if isinstance(value, str) and value.strip():
                urls[f"CustomAssetbundle.{field}"] = value.strip()

    return urls


def primary_assetbundle_url(urls: dict) -> str:
    for key in ("CustomAssetbundle.AssetbundleURL", "CustomAssetbundle.AssetbundleSecondaryURL"):
        value = urls.get(key, "")
        if value:
            return value
    return ""


def primary_mesh_url(urls: dict) -> str:
    for key in ("CustomMesh.MeshURL", "MeshURL", "ModelURL"):
        value = urls.get(key, "")
        if value:
            return value
    return ""


def primary_resource_url(urls: dict) -> str:
    return primary_assetbundle_url(urls) or primary_mesh_url(urls)


def asset_signature(urls: dict):
    return (
        urls.get("CustomAssetbundle.AssetbundleURL") or "",
        urls.get("CustomAssetbundle.AssetbundleSecondaryURL") or "",
        urls.get("CustomMesh.MeshURL") or urls.get("MeshURL") or urls.get("ModelURL") or "",
        urls.get("CustomMesh.DiffuseURL") or urls.get("DiffuseURL") or urls.get("SpecularURL") or urls.get("ImageURL") or "",
        urls.get("CustomMesh.ColliderURL") or urls.get("ColliderURL") or "",
        urls.get("CustomMesh.NormalURL") or urls.get("NormalURL") or "",
    )


def has_states(obj: dict) -> bool:
    states = obj.get("States", {})
    return isinstance(states, dict) and bool(states)


def has_contained_objects(obj: dict) -> bool:
    contained = obj.get("ContainedObjects", [])
    return isinstance(contained, list) and bool(contained)


def has_bag_payload(obj: dict) -> bool:
    bag = obj.get("Bag", {})
    return isinstance(bag, dict) and bool(bag)


def is_container_object(obj: dict) -> bool:
    return has_contained_objects(obj) or has_states(obj) or has_bag_payload(obj) or object_type(obj) in GENERIC_CONTAINER_NAMES


def is_leaf_model(obj: dict) -> bool:
    return object_has_model(obj) and not is_container_object(obj)


def helper_fragments_in_text(values: dict):
    combined = " ".join(values.values()).lower()
    hits = [fragment for fragment in sorted(HELPER_FRAGMENTS) if fragment in combined]
    return hits


def build_context(obj: dict, path: str):
    values = field_texts(obj)
    return {
        "path": path,
        "text": joined_search_text(values),
        "fields": values,
        "has_assetbundle": object_has_assetbundle(obj),
        "has_model": object_has_model(obj),
    }


def official_scale_for_candidate(node: dict, term: str) -> dict:
    ancestor_text = " | ".join(ancestor["text"] for ancestor in node.get("ancestors", []))
    return lookup_official_scale_reference(
        term,
        node.get("nickname", ""),
        node.get("name", ""),
        node.get("description", ""),
        node.get("gmnotes", ""),
        ancestor_text,
    )


def collect_model_nodes(obj, path="root", ancestors=None, results=None):
    if ancestors is None:
        ancestors = []
    if results is None:
        results = []

    if isinstance(obj, dict):
        current_context = build_context(obj, path)

        if is_object_record(obj) and (object_has_model(obj) or object_has_assetbundle(obj)):
            urls = extract_urls(obj)
            results.append(
                {
                    "path": path,
                    "name": str(obj.get("Name", "") or ""),
                    "nickname": str(obj.get("Nickname", "") or ""),
                    "guid": str(obj.get("GUID", "") or ""),
                    "description": str(obj.get("Description", "") or ""),
                    "gmnotes": str(obj.get("GMNotes", "") or ""),
                    "urls": urls,
                    "object_type": object_type(obj),
                    "has_assetbundle": object_has_assetbundle(obj),
                    "has_contained_objects": has_contained_objects(obj),
                    "has_states": has_states(obj),
                    "has_bag_payload": has_bag_payload(obj),
                    "is_leaf_model": is_leaf_model(obj),
                    "ancestors": list(ancestors),
                }
            )

        next_ancestors = ancestors + [current_context]
        for key, value in obj.items():
            collect_model_nodes(value, f"{path}/{key}", next_ancestors, results)

    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            collect_model_nodes(item, f"{path}[{index}]", ancestors, results)

    return results


def score_candidate(node: dict, term: str, mesh_counts: Counter):
    values = {
        "Nickname": node["nickname"],
        "Name": node["name"],
        "Description": node["description"],
        "GMNotes": node["gmnotes"],
    }
    own_matches = match_fields(values, term)
    ancestor_matches = []
    ancestor_assetbundle_matches = []
    if term:
        for ancestor in node["ancestors"]:
            matches = match_fields(ancestor["fields"], term)
            if matches:
                payload = {
                    "path": ancestor["path"],
                    "matches": matches,
                    "text": ancestor["text"],
                }
                ancestor_matches.append(payload)
                if ancestor.get("has_assetbundle"):
                    ancestor_assetbundle_matches.append(payload)

    matches_search = not term or bool(own_matches) or bool(ancestor_matches)
    assetbundle_url = primary_assetbundle_url(node["urls"])
    mesh_url = primary_mesh_url(node["urls"])
    primary_resource = assetbundle_url or mesh_url
    mesh_reuse = mesh_counts.get(primary_resource, 0)
    helper_hits = helper_fragments_in_text(values)
    official_scale = official_scale_for_candidate(node, term)

    score = 0
    reasons = []

    if assetbundle_url:
        score += 220
        reasons.append("assetbundle")
    elif "CustomMesh.MeshURL" in node["urls"]:
        score += 100
        reasons.append("custom_mesh")
    elif primary_resource:
        score += 60
        reasons.append("root_mesh")

    if own_matches:
        score += 120
        reasons.append("direct_match")
    elif ancestor_matches:
        score += 45
        reasons.append("ancestor_match")

    if node["has_assetbundle"] and node["object_type"] == "custom_assetbundle":
        score += 120
        reasons.append("custom_assetbundle_object")

    if node["is_leaf_model"]:
        score += 90
        reasons.append("leaf_model")

    if node["path"].count("/States/") > 0:
        score += 40
        reasons.append("state_variant")

    if node["object_type"] == "custom_model":
        score += 35
        reasons.append("custom_model_leaf")

    if node["urls"].get("CustomMesh.DiffuseURL") or node["urls"].get("DiffuseURL"):
        score += 12
        reasons.append("has_texture")

    if node["urls"].get("CustomMesh.ColliderURL") or node["urls"].get("ColliderURL"):
        score += 5
        reasons.append("has_collider")

    if node["urls"].get("CustomMesh.NormalURL") or node["urls"].get("NormalURL"):
        score += 5
        reasons.append("has_normal")

    if is_container_object(
        {
            "Name": node["name"],
            "ContainedObjects": [1] if node["has_contained_objects"] else [],
            "States": {"1": 1} if node["has_states"] else {},
            "Bag": {"1": 1} if node["has_bag_payload"] else {},
        }
    ):
        score -= 80
        reasons.append("container_penalty")

    if node["object_type"] in GENERIC_CONTAINER_NAMES:
        score -= 140
        reasons.append("generic_container_penalty")

    if helper_hits:
        score -= 90
        reasons.append("helper_penalty")

    if ancestor_assetbundle_matches and not node["has_assetbundle"]:
        score -= 220
        reasons.append("shadowed_by_assetbundle_ancestor")

    if mesh_reuse >= HIGH_REUSE_MESH_THRESHOLD:
        penalty = min(120, (mesh_reuse - HIGH_REUSE_MESH_THRESHOLD + 1) * 5)
        score -= penalty
        reasons.append(f"common_mesh_penalty:{mesh_reuse}")

    return {
        **node,
        "matches_search": matches_search,
        "match_fields": own_matches,
        "ancestor_matches": ancestor_matches,
        "ancestor_assetbundle_matches": ancestor_assetbundle_matches,
        "helper_fragments": helper_hits,
        "mesh_reuse_count": mesh_reuse,
        "primary_assetbundle_url": assetbundle_url,
        "primary_mesh_url": mesh_url,
        "primary_resource_url": primary_resource,
        "asset_signature": asset_signature(node["urls"]),
        "official_scale": official_scale,
        "score": score,
        "score_reasons": reasons,
    }


def select_candidates(scored_nodes):
    ordered = sorted(
        scored_nodes,
        key=lambda item: (
            item["score"],
            len(item["match_fields"]),
            int(item["is_leaf_model"]),
            -item["mesh_reuse_count"],
            item["path"],
        ),
        reverse=True,
    )

    selected = []
    discarded = []
    seen_signatures = {}

    for candidate in ordered:
        discard_reasons = []

        if not candidate["matches_search"]:
            discard_reasons.append("search_mismatch")

        if candidate["score"] < MIN_SELECTION_SCORE:
            discard_reasons.append("score_below_threshold")

        if candidate["ancestor_assetbundle_matches"] and not candidate["has_assetbundle"]:
            discard_reasons.append("shadowed_by_assetbundle_ancestor")

        signature = candidate["asset_signature"]
        if signature in seen_signatures:
            discard_reasons.append(f"duplicate_signature:{seen_signatures[signature]}")

        if discard_reasons:
            discarded.append({**candidate, "discard_reasons": discard_reasons})
            continue

        selected.append(candidate)
        seen_signatures[signature] = candidate["path"]

    return selected, discarded


def build_cache_lookup(all_files):
    lookup = defaultdict(list)
    for file_path in all_files:
        lookup[file_path.name.lower()].append(file_path)
    return lookup


def unique_paths(paths):
    unique = []
    seen = set()
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_cached_files_for_url(url: str, all_files, lookup):
    sanitized = sanitize_tts_url(url).lower()
    parts = [part for part in (url or "").strip("/").split("/") if part]
    tail = parts[-1].lower() if parts else ""

    exact_matches = []
    if sanitized:
        exact_matches.extend(lookup.get(sanitized, []))
    if tail:
        exact_matches.extend(lookup.get(tail, []))
    exact_matches = unique_paths(exact_matches)
    if exact_matches:
        return exact_matches

    loose_matches = []
    for file_path in all_files:
        name_lower = file_path.name.lower()
        if sanitized and sanitized in name_lower:
            loose_matches.append(file_path)
            continue
        if tail and tail in name_lower:
            loose_matches.append(file_path)

    return unique_paths(loose_matches)


def output_subfolder_for_field(field: str) -> str:
    lowered = field.lower()
    if "colliderurl" in lowered:
        return "colliders"
    if "normalurl" in lowered:
        return "normals"
    if "assetbundle" in lowered:
        return "assetbundles"
    if "diffuseurl" in lowered or "specularurl" in lowered or "imageurl" in lowered:
        return "textures"
    return "meshes"


def ensure_output_dirs(base_dir: Path):
    folders = {
        "base": base_dir,
        "meshes": base_dir / "meshes",
        "textures": base_dir / "textures",
        "colliders": base_dir / "colliders",
        "normals": base_dir / "normals",
        "assetbundles": base_dir / "assetbundles",
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    return folders


def copy_with_unique_name(src: Path, dst_folder: Path, prefix: str):
    base_name = f"{prefix}_{src.name}" if prefix else src.name
    candidate = dst_folder / base_name

    if not candidate.exists():
        shutil.copy2(src, candidate)
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        alt_candidate = dst_folder / f"{stem}_{index}{suffix}"
        if not alt_candidate.exists():
            shutil.copy2(src, alt_candidate)
            return alt_candidate
        index += 1


def json_ready_candidates(candidates):
    prepared = []
    for candidate in candidates:
        row = dict(candidate)
        row["ancestors"] = candidate["ancestors"]
        prepared.append(row)
    return prepared


def load_unitypy():
    if UNITYPY_SITE_PACKAGES.exists():
        site_packages = str(UNITYPY_SITE_PACKAGES)
        if site_packages not in sys.path:
            sys.path.insert(0, site_packages)

    try:
        import UnityPy  # type: ignore
    except Exception:
        return None

    return UnityPy


def identity_matrix():
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def multiply_matrix(left, right):
    return [
        [sum(left[row][idx] * right[idx][col] for idx in range(4)) for col in range(4)]
        for row in range(4)
    ]


def translation_matrix(vector):
    matrix = identity_matrix()
    matrix[0][3] = float(vector.x)
    matrix[1][3] = float(vector.y)
    matrix[2][3] = float(vector.z)
    return matrix


def scale_matrix(vector):
    matrix = identity_matrix()
    matrix[0][0] = float(vector.x)
    matrix[1][1] = float(vector.y)
    matrix[2][2] = float(vector.z)
    return matrix


def rotation_matrix(quaternion):
    x = float(quaternion.x)
    y = float(quaternion.y)
    z = float(quaternion.z)
    w = float(quaternion.w)

    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    return [
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def transform_matrix(transform):
    return multiply_matrix(
        translation_matrix(transform.m_LocalPosition),
        multiply_matrix(
            rotation_matrix(transform.m_LocalRotation),
            scale_matrix(transform.m_LocalScale),
        ),
    )


def transform_point(matrix, vertex):
    x, y, z = vertex
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def should_skip_base(game_object_name: str, include_base: bool) -> bool:
    if include_base:
        return False

    name = normalize_text(game_object_name)
    return "figurebase" in name or name == "base"


def export_mesh_hierarchy(game_object, world_matrix, lines, vertex_offset: int, include_base: bool, warnings):
    try:
        transform = game_object.m_Transform.read()
    except FileNotFoundError as exc:
        warnings.append(
            {
                "game_object": getattr(game_object, "m_Name", "unnamed"),
                "reason": "missing_transform_dependency",
                "detail": str(exc),
            }
        )
        return lines, vertex_offset
    except Exception as exc:
        warnings.append(
            {
                "game_object": getattr(game_object, "m_Name", "unnamed"),
                "reason": "transform_read_error",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
        return lines, vertex_offset

    current_matrix = multiply_matrix(world_matrix, transform_matrix(transform))
    object_name = game_object.m_Name or "unnamed"

    if game_object.m_MeshFilter and not should_skip_base(object_name, include_base):
        try:
            mesh_filter = game_object.m_MeshFilter.read()
            mesh = mesh_filter.m_Mesh.read()
            raw_lines = mesh.export().splitlines()
            local_vertex_count = 0

            lines.append(f"o {object_name}")

            for raw_line in raw_lines:
                if raw_line.startswith("v "):
                    _, x, y, z = raw_line.split()[:4]
                    tx, ty, tz = transform_point(current_matrix, (float(x), float(y), float(z)))
                    lines.append(f"v {tx:.6f} {ty:.6f} {tz:.6f}")
                    local_vertex_count += 1
                elif raw_line.startswith("f "):
                    face_parts = []
                    for part in raw_line.split()[1:]:
                        vertex_index = part.split("/")[0]
                        face_parts.append(str(int(vertex_index) + vertex_offset))
                    lines.append("f " + " ".join(face_parts))

            vertex_offset += local_vertex_count
        except FileNotFoundError as exc:
            warnings.append(
                {
                    "game_object": object_name,
                    "reason": "missing_mesh_dependency",
                    "detail": str(exc),
                }
            )
        except Exception as exc:
            warnings.append(
                {
                    "game_object": object_name,
                    "reason": "mesh_export_error",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )

    for child_ptr in transform.m_Children:
        try:
            child_transform = child_ptr.read()
            child_object = child_transform.m_GameObject.read()
        except FileNotFoundError as exc:
            warnings.append(
                {
                    "game_object": object_name,
                    "reason": "missing_child_dependency",
                    "detail": str(exc),
                }
            )
            continue
        except Exception as exc:
            warnings.append(
                {
                    "game_object": object_name,
                    "reason": "child_read_error",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        lines, vertex_offset = export_mesh_hierarchy(
            child_object,
            current_matrix,
            lines,
            vertex_offset,
            include_base,
            warnings,
        )

    return lines, vertex_offset


def root_game_objects_from_env(env):
    roots = []

    for _, pointer in env.container.items():
        try:
            asset = pointer.read()
        except Exception:
            continue
        if getattr(asset, "m_Name", None) and asset.__class__.__name__ == "GameObject":
            roots.append(asset)

    if roots:
        return roots

    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        game_object = obj.read()
        transform = game_object.m_Transform.read()
        father = transform.m_Father
        if not father or father.m_PathID == 0:
            roots.append(game_object)

    return roots


def export_assetbundle_to_obj(bundle_path: Path, output_dir: Path, base_name: str):
    UnityPy = load_unitypy()
    if UnityPy is None:
        return {"success": False, "reason": "unitypy_not_available", "outputs": []}

    env = UnityPy.load(str(bundle_path))
    roots = root_game_objects_from_env(env)
    if not roots:
        return {"success": False, "reason": "no_root_gameobject_found", "outputs": []}

    outputs = []
    warnings = []
    for root in roots:
        root_safe_name = sanitize_name(root.m_Name)[:60]
        for include_base, suffix in ((True, "full"), (False, "no_base")):
            lines, vertex_count = export_mesh_hierarchy(
                root,
                identity_matrix(),
                ["# OBJ export generated from Unity assetbundle"],
                0,
                include_base,
                warnings,
            )
            if vertex_count == 0:
                continue

            target = output_dir / f"{base_name}_{root_safe_name}_{suffix}.obj"
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            outputs.append(
                {
                    "root_name": root.m_Name,
                    "include_base": include_base,
                    "vertex_count": vertex_count,
                    "path": str(target),
                }
            )

    if not outputs:
        return {
            "success": False,
            "reason": "no_mesh_vertices_exported",
            "outputs": [],
            "warnings": warnings,
        }

    return {"success": True, "reason": "", "outputs": outputs, "warnings": warnings}


# =========================================================
# EXECUTION
# =========================================================

def main():
    args = parse_args()

    search_term = args.search or ""
    safe_term = sanitize_name(search_term)
    mod_json = args.mods_json
    output_dir = args.output_base / safe_term
    search_scale = lookup_official_scale_reference(search_term)

    if not mod_json.exists():
        raise FileNotFoundError(f"Mod JSON not found: {mod_json}")

    output_folders = ensure_output_dirs(output_dir)

    report_txt_file = output_dir / "report.txt"
    report_json_file = output_dir / "report.json"
    objects_json_file = output_dir / "selected_objects.json"
    urls_file = output_dir / "urls.txt"

    print("Loading JSON...")
    data = load_json(mod_json)

    print("Collecting 3D model objects...")
    model_nodes = collect_model_nodes(data)
    mesh_counts = Counter(
        primary_resource_url(node["urls"]) for node in model_nodes if primary_resource_url(node["urls"])
    )
    scored_nodes = [score_candidate(node, search_term, mesh_counts) for node in model_nodes]
    selected_nodes, discarded_nodes = select_candidates(scored_nodes)

    print(f"Model candidates: {len(model_nodes)}")
    print(f"Selected objects: {len(selected_nodes)}")
    print(f"Discarded objects: {len(discarded_nodes)}")
    print(f"Scale reference for this search: {search_scale['summary']}")

    with objects_json_file.open("w", encoding="utf-8") as handle:
        json.dump(json_ready_candidates(selected_nodes), handle, ensure_ascii=False, indent=2)

    all_urls = []
    seen_urls = set()
    for item in selected_nodes:
        for field, url in item["urls"].items():
            key = (field, url)
            if key not in seen_urls:
                seen_urls.add(key)
                all_urls.append((field, url))

    with urls_file.open("w", encoding="utf-8") as handle:
        for field, url in all_urls:
            handle.write(f"{output_subfolder_for_field(field)}\t{field}\t{url}\n")

    print(f"Unique selected URLs: {len(all_urls)}")

    print("Indexing local cache...")
    all_files = []
    all_files += collect_files(ASSETBUNDLES_DIR)
    all_files += collect_files(MODELS_DIR)
    all_files += collect_files(IMAGES_DIR)
    all_files += collect_files(RAW_IMAGES_DIR)
    cache_lookup = build_cache_lookup(all_files)

    print(f"Cached files scanned: {len(all_files)}")

    copied_files = []
    not_found_urls = []
    printable_exports = []
    printable_export_failures = []
    printable_export_warnings = []

    for index, item in enumerate(selected_nodes, start=1):
        nickname = item["nickname"].strip() or item["name"].strip() or f"object_{index}"
        short_name = sanitize_name(nickname)[:60]

        for field, url in item["urls"].items():
            matches = find_cached_files_for_url(url, all_files, cache_lookup)
            target_folder_name = output_subfolder_for_field(field)
            target_folder = output_folders[target_folder_name]

            if matches:
                for source_path in matches:
                    prefix = f"{index:03d}_{short_name}_{field.replace('.', '_')}"
                    copied_to = copy_with_unique_name(source_path, target_folder, prefix)
                    copied_files.append(
                        {
                            "object_index": index,
                            "nickname": nickname,
                            "field": field,
                            "category": target_folder_name,
                            "url": url,
                            "source": str(source_path),
                            "copied_to": str(copied_to),
                        }
                    )

                    if (
                        field == "CustomAssetbundle.AssetbundleURL"
                        and copied_to.suffix.lower() == ".unity3d"
                    ):
                        export_base_name = f"{index:03d}_{short_name}_printable"
                        export_result = export_assetbundle_to_obj(
                            copied_to,
                            output_folders["meshes"],
                            export_base_name,
                        )
                        if export_result["success"]:
                            for warning in export_result.get("warnings", []):
                                printable_export_warnings.append(
                                    {
                                        "object_index": index,
                                        "nickname": nickname,
                                        "bundle_path": str(copied_to),
                                        **warning,
                                    }
                                )
                            for exported in export_result["outputs"]:
                                printable_exports.append(
                                    {
                                        "object_index": index,
                                        "nickname": nickname,
                                        "bundle_path": str(copied_to),
                                        **exported,
                                    }
                                )
                        else:
                            for warning in export_result.get("warnings", []):
                                printable_export_warnings.append(
                                    {
                                        "object_index": index,
                                        "nickname": nickname,
                                        "bundle_path": str(copied_to),
                                        **warning,
                                    }
                                )
                            printable_export_failures.append(
                                {
                                    "object_index": index,
                                    "nickname": nickname,
                                    "bundle_path": str(copied_to),
                                    "reason": export_result["reason"],
                                }
                            )
            else:
                not_found_urls.append(
                    {
                        "object_index": index,
                        "nickname": nickname,
                        "field": field,
                        "category": target_folder_name,
                        "url": url,
                    }
                )

    report_payload = {
        "config": {
            "search_term": search_term,
            "search_scale_reference": search_scale,
            "mods_json": str(mod_json),
            "output_dir": str(output_dir),
            "assetbundles_dir": str(ASSETBUNDLES_DIR),
            "models_dir": str(MODELS_DIR),
            "images_dir": str(IMAGES_DIR),
            "raw_images_dir": str(RAW_IMAGES_DIR),
        },
        "summary": {
            "model_candidates": len(model_nodes),
            "selected_objects": len(selected_nodes),
            "discarded_objects": len(discarded_nodes),
            "selected_urls": len(all_urls),
            "copied_files": len(copied_files),
            "missing_urls": len(not_found_urls),
            "printable_exports": len(printable_exports),
            "printable_export_failures": len(printable_export_failures),
            "printable_export_warnings": len(printable_export_warnings),
        },
        "selected_objects": json_ready_candidates(selected_nodes),
        "discarded_objects": json_ready_candidates(discarded_nodes),
        "copied_files": copied_files,
        "missing_urls": not_found_urls,
        "printable_exports": printable_exports,
        "printable_export_failures": printable_export_failures,
        "printable_export_warnings": printable_export_warnings,
    }

    with report_json_file.open("w", encoding="utf-8") as handle:
        json.dump(report_payload, handle, ensure_ascii=False, indent=2)

    with report_txt_file.open("w", encoding="utf-8") as report:
        report.write("TTS MODEL EXTRACTION REPORT\n")
        report.write("=" * 80 + "\n\n")
        report.write(f"Search term              : {search_term!r}\n")
        report.write(f"Search scale reference   : {search_scale['summary']}\n")
        report.write(f"Source JSON              : {mod_json}\n")
        report.write(f"Base output              : {output_dir}\n")
        report.write(f"Model candidates         : {len(model_nodes)}\n")
        report.write(f"Selected objects         : {len(selected_nodes)}\n")
        report.write(f"Discarded objects        : {len(discarded_nodes)}\n")
        report.write(f"Selected URLs            : {len(all_urls)}\n")
        report.write(f"Copied files             : {len(copied_files)}\n")
        report.write(f"Missing cache URLs       : {len(not_found_urls)}\n\n")
        report.write(f"Printable OBJ exports    : {len(printable_exports)}\n")
        report.write(f"OBJ export failures      : {len(printable_export_failures)}\n\n")
        report.write(f"OBJ export warnings      : {len(printable_export_warnings)}\n\n")

        report.write("OUTPUT FOLDERS\n")
        report.write("-" * 80 + "\n")
        for key in ("meshes", "textures", "colliders", "normals"):
            report.write(f"{key:10s}: {output_folders[key]}\n")
        report.write(f"{'assetbundles':10s}: {output_folders['assetbundles']}\n")
        report.write("\n")

        report.write("SELECTED OBJECTS\n")
        report.write("-" * 80 + "\n")
        for index, item in enumerate(selected_nodes, start=1):
            report.write(f"[{index:03d}] Nickname        : {item['nickname']}\n")
            report.write(f"      Name            : {item['name']}\n")
            report.write(f"      GUID            : {item['guid']}\n")
            report.write(f"      Path            : {item['path']}\n")
            report.write(f"      Score           : {item['score']}\n")
            report.write(f"      Match           : {', '.join(item['match_fields']) or '(ancestor match only or empty search)'}\n")
            report.write(f"      Mesh reuse      : {item['mesh_reuse_count']}\n")
            report.write(f"      Leaf            : {item['is_leaf_model']}\n")
            report.write(f"      Assetbundle     : {item['has_assetbundle']}\n")
            report.write(f"      Official scale  : {item['official_scale']['summary']}\n")
            if item["ancestor_matches"]:
                report.write("      Related ancestors:\n")
                for ancestor in item["ancestor_matches"]:
                    report.write(f"        - {ancestor['path']} [{', '.join(ancestor['matches'])}]\n")
            if item["helper_fragments"]:
                report.write(f"      Helper hits     : {', '.join(item['helper_fragments'])}\n")
            if item["urls"]:
                report.write("      URLs:\n")
                for field, url in item["urls"].items():
                    category = output_subfolder_for_field(field)
                    report.write(f"        - {field} [{category}]: {url}\n")
            report.write("\n")

        report.write("DISCARDED OBJECTS\n")
        report.write("-" * 80 + "\n")
        for item in discarded_nodes:
            report.write(f"- {item['path']} | {item['nickname'] or item['name'] or '(unnamed)'}\n")
            report.write(f"  Score   : {item['score']}\n")
            report.write(f"  Reasons : {', '.join(item['discard_reasons'])}\n")
            report.write(f"  Scoring : {', '.join(item['score_reasons'])}\n")

        report.write("\nCOPIED FILES\n")
        report.write("-" * 80 + "\n")
        for row in copied_files:
            report.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
            report.write(f"      Field    : {row['field']}\n")
            report.write(f"      Category : {row['category']}\n")
            report.write(f"      URL      : {row['url']}\n")
            report.write(f"      Source   : {row['source']}\n")
            report.write(f"      Copied   : {row['copied_to']}\n\n")

        report.write("PRINTABLE OBJ EXPORTS\n")
        report.write("-" * 80 + "\n")
        for row in printable_exports:
            report.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
            report.write(f"      Bundle    : {row['bundle_path']}\n")
            report.write(f"      Root name : {row['root_name']}\n")
            report.write(f"      Variant   : {'with base' if row['include_base'] else 'without base'}\n")
            report.write(f"      Vertices  : {row['vertex_count']}\n")
            report.write(f"      OBJ       : {row['path']}\n\n")

        report.write("OBJ EXPORT FAILURES\n")
        report.write("-" * 80 + "\n")
        for row in printable_export_failures:
            report.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
            report.write(f"      Bundle : {row['bundle_path']}\n")
            report.write(f"      Reason : {row['reason']}\n\n")

        report.write("OBJ EXPORT WARNINGS\n")
        report.write("-" * 80 + "\n")
        for row in printable_export_warnings:
            report.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
            report.write(f"      Bundle : {row['bundle_path']}\n")
            report.write(f"      Object : {row['game_object']}\n")
            report.write(f"      Warning: {row['reason']}\n")
            report.write(f"      Detail : {row['detail']}\n\n")

        report.write("URLS NOT FOUND IN CACHE\n")
        report.write("-" * 80 + "\n")
        for row in not_found_urls:
            report.write(f"[{row['object_index']:03d}] {row['nickname']}\n")
            report.write(f"      Field    : {row['field']}\n")
            report.write(f"      Category : {row['category']}\n")
            report.write(f"      URL      : {row['url']}\n\n")

    print("\nProcess finished.")
    print(f"Output folder         : {output_dir}")
    print(f"TXT report            : {report_txt_file}")
    print(f"JSON report           : {report_json_file}")
    print(f"Objects JSON          : {objects_json_file}")
    print(f"URL list              : {urls_file}")
    print(f"Copied files          : {len(copied_files)}")
    print(f"Missing cache URLs    : {len(not_found_urls)}")
    print(f"Printable OBJ exports : {len(printable_exports)}")
    print(f"OBJ export failures   : {len(printable_export_failures)}")
    print(f"OBJ export warnings   : {len(printable_export_warnings)}")


if __name__ == "__main__":
    main()
