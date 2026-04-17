from pathlib import Path
import runpy


launcher_path = Path(__file__).resolve().parent / "App" / "gui_launcher.pyw"
runpy.run_path(str(launcher_path), run_name="__main__")
