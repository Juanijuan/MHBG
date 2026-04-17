# MHBG Asset Toolkit

Windows-first desktop toolkit for extracting Monster Hunter World: The Board Game assets from a local Tabletop Simulator cache.

This project is aimed at modelers, painters, graphic designers, and makers who want a simple workflow without digging through scripts by hand.

## What It Does

- launches a no-console desktop UI
- extracts matching card data from `mods.json`
- imports matching image files from the local TTS cache
- renames imported images with readable names such as `Kirin_1`, `Kirin_2`, and so on
- extracts matching 3D model files from the local TTS cache
- includes official Steamforged scale notes when available
- cuts card sheets into a rows x columns grid with an image preview and Windows file picker

## Folder Layout

```text
MHBG/
|-- Launch_MHBG_Toolkit.py
|-- Launch_MHBG_Toolkit.pyw
|-- README.md
|-- .gitignore
|-- App/
|   |-- gui_launcher.pyw
|   |-- extract_cards.py
|   |-- extract_models.py
|   |-- image_importer.py
|   |-- sheet_cutter.py
|   |-- scale_reference.py
|   `-- project_paths.py
|-- Input/
|   |-- README.txt
|   `-- mods.json
|-- Outputs/
|   |-- Cards/
|   |-- Models/
|   `-- Print/
|-- Reference/
|   `-- steamforged_scale_notes.txt
`-- Tools/
```

What each folder is for:

- `App/`: the actual toolkit scripts
- `Input/`: your local source files, especially `mods.json`
- `Outputs/`: everything the toolkit generates
- `Reference/`: human-readable notes such as scale references
- `Tools/`: optional local helper dependencies and scratch tools

## Requirements

- Windows
- Python 3.10 or newer
- Tabletop Simulator installed locally
- a local `mods.json` export placed at `Input/mods.json`

Python packages:

- `Pillow`
- `UnityPy`

Install them with:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install pillow UnityPy
```

## Quick Start

1. Put your local `mods.json` file in `Input/mods.json`.
2. Start the launcher with one of these:

```bash
python Launch_MHBG_Toolkit.py
```

Or double-click:

```text
Launch_MHBG_Toolkit.pyw
```

3. Use the desktop window:
- `Card extractor`
- `3D model extractor`
- `Image sheet cutter`

The launcher blocks empty searches on purpose, because an empty search would try to scan the full JSON and can create a very large output.

## Desktop Workflows

### Card extractor

Use this when you want card-related data and cached images for a monster, hunter, weapon, behavior, or similar keyword.

Suggested searches:

- `kirin`
- `teostra`
- `kushala daora`
- `hunter`
- `behaviour`
- `weapon`

Output goes to:

```text
Outputs/Cards/<search>/
```

Typical output:

- `subset.json`
- `urls.txt`
- `report.txt`
- `assets/`
- `assets/import_report.txt`

### 3D model extractor

Use this when you want matching meshes, textures, colliders, and related reports from the TTS cache.

Suggested searches:

- `hunter`
- `hunting horn`
- `great sword`
- `kirin`
- `teostra`
- `kushala daora`

Output goes to:

```text
Outputs/Models/<search>/
```

Typical output:

- `report.txt`
- `report.json`
- `selected_objects.json`
- `urls.txt`
- `meshes/`
- `textures/`
- `colliders/`
- `normals/`
- `assetbundles/`

When a local Steamforged reference exists, the model report also includes the official or guidance scale for that search.

### Image sheet cutter

Use this when you already have a card sheet image and want it split automatically.

Workflow:

1. Click `Choose image`.
2. Pick a `.png`, `.jpg`, `.jpeg`, `.webp`, or similar image.
3. Enter rows and columns.
4. Click `Cut image sheet`.

By default, the cut cards are saved next to the source image in a folder named like:

```text
<image_name>_cards
```

## Command-Line Usage

The desktop launcher is the recommended entry point, but advanced users can still run the scripts directly.

### Extract cards

```bash
python App\extract_cards.py --search kirin
```

Useful options:

- `--mods-json`
- `--output-dir`
- `--skip-import`

### Import cached images only

```bash
python App\image_importer.py --search kirin
```

### Extract 3D models

```bash
python App\extract_models.py --search "hunting horn"
```

Useful options:

- `--mods-json`
- `--output-base`

### Cut a sheet image

```bash
python App\sheet_cutter.py --input path\to\sheet.png --rows 4 --cols 4
```

Optional:

- `--output-dir`

## Default Local TTS Paths

By default, the toolkit looks for Tabletop Simulator cache files here:

- `%USERPROFILE%\Documents\My Games\Tabletop Simulator\Mods\Images`
- `%USERPROFILE%\Documents\My Games\Tabletop Simulator\Mods\Raw Images`
- `%USERPROFILE%\Documents\My Games\Tabletop Simulator\Mods\Models`
- `%USERPROFILE%\Documents\My Games\Tabletop Simulator\Mods\Assetbundles`

If your TTS folders live somewhere else, update the values in `App/project_paths.py`.

## Notes About `mods.json`

- keep your personal `mods.json` in `Input/mods.json`
- `Input/mods.json` is ignored by Git on purpose
- this lets you publish the repo without uploading your own source data

## Troubleshooting

### The launcher does not open

- make sure Python is installed
- try `python Launch_MHBG_Toolkit.py`
- if needed, use the full path to `python.exe`

### No images are imported

- make sure `urls.txt` was generated
- make sure the matching files exist in your local TTS cache
- confirm the cache paths in `App/project_paths.py`

### Model extraction finds the wrong things

- try a more specific search such as `kushala daora` instead of `kushala`
- use full weapon names like `hunting horn` or `charge blade`

### OBJ or assetbundle export does not work

- make sure `UnityPy` is installed
- some assetbundles may still fail depending on their internal data
- check `report.txt` and `report.json` for warnings

## GitHub Publishing Notes

The repository is set up so local-only or generated content stays out of version control, including:

- `Input/mods.json`
- `Outputs/`
- `Tools/`
- `.vscode/`
- Python cache files

That means you can keep your personal data and generated assets locally while sharing only the toolkit itself.

## Contributing

Pull requests and issue reports are welcome, especially for:

- better search heuristics
- additional scale references
- better cache matching
- GUI improvements
- clearer reports

## Legal Notes

- Monster Hunter is a Capcom property.
- This toolkit is an unofficial community project.
- It is not affiliated with Capcom, Steamforged Games, or Berserk Games.
- Only extract, print, share, or redistribute files you are allowed to use.
- The `LICENSE` file applies to the toolkit source code and documentation in this repository.
- It does not grant rights over third-party assets, trademarks, game content, cached files, or extracted data.

## License

This repository uses the MIT license for the toolkit code and documentation only. See `LICENSE` for the full text.
