from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "App"
INPUT_DIR = ROOT_DIR / "Input"
REFERENCE_DIR = ROOT_DIR / "Reference"
OUTPUTS_DIR = ROOT_DIR / "Outputs"
CARD_OUTPUTS_DIR = OUTPUTS_DIR / "Cards"
MODEL_OUTPUTS_DIR = OUTPUTS_DIR / "Models"
PRINT_OUTPUTS_DIR = OUTPUTS_DIR / "Print"

TTS_MODS_DIR = Path.home() / "Documents" / "My Games" / "Tabletop Simulator" / "Mods"
TTS_IMAGES_DIR = TTS_MODS_DIR / "Images"
TTS_RAW_IMAGES_DIR = TTS_MODS_DIR / "Raw Images"
TTS_MODELS_DIR = TTS_MODS_DIR / "Models"
TTS_ASSETBUNDLES_DIR = TTS_MODS_DIR / "Assetbundles"
