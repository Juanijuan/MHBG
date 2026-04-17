import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk, UnidentifiedImageError


SCRIPT_DIR = Path(__file__).resolve().parent
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IMAGE_FILETYPES = [
    ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
    ("All files", "*.*"),
]


def resolve_python_command() -> list[str]:
    current = Path(sys.executable)
    checked = []

    if current.name.lower() == "pythonw.exe":
        python_candidate = current.with_name("python.exe")
        if python_candidate.exists():
            return [str(python_candidate)]
        checked.append(str(python_candidate))

    if current.exists() and current.name.lower().startswith("python"):
        return [str(current)]

    user_python_dir = Path.home() / "AppData" / "Local" / "Programs" / "Python"
    if user_python_dir.exists():
        candidates = sorted(user_python_dir.glob("Python*/python.exe"), reverse=True)
        for candidate in candidates:
            if candidate.exists():
                return [str(candidate)]
            checked.append(str(candidate))

    path_python = shutil.which("python")
    if path_python and "WindowsApps" not in path_python:
        return [path_python]

    path_python3 = shutil.which("python3")
    if path_python3 and "WindowsApps" not in path_python3:
        return [path_python3]

    for launcher in ("py", "pyw"):
        if shutil.which(launcher):
            return [launcher, "-3"]

    checked_info = ", ".join(checked) if checked else "no direct candidates checked"
    raise RuntimeError(f"No usable Python interpreter was found ({checked_info}).")


class Tooltip:
    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window = None
        self.after_id = None

        self.widget.bind("<Enter>", self._schedule, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self):
        if self.tip_window is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            background="#fff8dc",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class ScriptLauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MHBG Asset Toolkit")
        self.root.geometry("1120x920")
        self.root.minsize(960, 820)

        self.python_command = resolve_python_command()
        self.log_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.current_process: subprocess.Popen[str] | None = None
        self.worker_thread: threading.Thread | None = None
        self.preview_photo = None
        self.selected_image_path: Path | None = None

        self.cards_query = tk.StringVar(value="kirin")
        self.models_query = tk.StringVar(value="kirin")
        self.pillow_file_var = tk.StringVar(value="No image selected")
        self.pillow_rows_var = tk.StringVar(value="2")
        self.pillow_cols_var = tk.StringVar(value="3")

        self.run_buttons: list[ttk.Button] = []

        self._build_ui()
        self.root.after(100, self._flush_log_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(4, weight=1)
        container.rowconfigure(5, weight=1)

        header = ttk.Label(
            container,
            text="MHBG asset toolkit",
            font=("Segoe UI", 18, "bold"),
        )
        header.grid(row=0, column=0, sticky="w")

        note = ttk.Label(
            container,
            text="Empty searches are blocked here on purpose so the app does not scan the whole JSON by accident.",
            foreground="#555555",
        )
        note.grid(row=1, column=0, sticky="w", pady=(4, 14))

        self._build_cards_section(container).grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._build_models_section(container).grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self._build_pillow_section(container).grid(row=4, column=0, sticky="nsew", pady=(0, 12))
        self._build_log_section(container).grid(row=5, column=0, sticky="nsew")

    def _build_cards_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Card extractor")
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Extract a filtered JSON subset, export the matching URL list, then import and rename the images automatically into Outputs/Cards.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))

        button = ttk.Button(
            frame,
            text="Extract cards",
            command=self._run_extract_cards,
        )
        button.grid(row=1, column=0, sticky="nw", padx=(12, 10), pady=(0, 12))
        self.run_buttons.append(button)

        entry = ttk.Entry(frame, textvariable=self.cards_query)
        entry.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))
        Tooltip(
            entry,
            "Search ideas:\n"
            "- kirin\n"
            "- teostra\n"
            "- kushala daora\n"
            "- hunter\n"
            "- behaviour\n"
            "- weapon",
        )
        return frame

    def _build_models_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="3D model extractor")
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Search 3D models in the TTS mod data, copy local cache files into Outputs/Models, and include the official SFG scale reference when available.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))

        button = ttk.Button(
            frame,
            text="Extract 3D models",
            command=self._run_extract_models,
        )
        button.grid(row=1, column=0, sticky="nw", padx=(12, 10), pady=(0, 12))
        self.run_buttons.append(button)

        entry = ttk.Entry(frame, textvariable=self.models_query)
        entry.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))
        Tooltip(
            entry,
            "Search ideas:\n"
            "- hunter\n"
            "- hunting horn\n"
            "- great sword\n"
            "- kirin\n"
            "- teostra\n"
            "- kushala daora",
        )
        return frame

    def _build_pillow_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Image sheet cutter")
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(2, weight=1)

        left = ttk.Frame(frame)
        left.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(12, 10), pady=12)
        left.columnconfigure(1, weight=1)

        ttk.Label(
            left,
            text="Pick a sheet image, set rows and columns, and split it without typing file paths by hand.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        browse_button = ttk.Button(left, text="Choose image", command=self._select_pillow_image)
        browse_button.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.run_buttons.append(browse_button)

        path_label = ttk.Label(left, textvariable=self.pillow_file_var)
        path_label.grid(row=1, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(0, 10))

        ttk.Label(left, text="Rows").grid(row=2, column=0, sticky="w")
        rows_entry = ttk.Spinbox(left, from_=1, to=99, textvariable=self.pillow_rows_var, width=8)
        rows_entry.grid(row=2, column=1, sticky="w", pady=(0, 12))

        ttk.Label(left, text="Columns").grid(row=3, column=0, sticky="w")
        cols_entry = ttk.Spinbox(left, from_=1, to=99, textvariable=self.pillow_cols_var, width=8)
        cols_entry.grid(row=3, column=1, sticky="w", pady=(0, 12))

        cut_button = ttk.Button(left, text="Cut image sheet", command=self._run_pillow_cutter)
        cut_button.grid(row=4, column=0, sticky="w")
        self.run_buttons.append(cut_button)

        preview_frame = ttk.Frame(frame, padding=(0, 12, 12, 12))
        preview_frame.grid(row=0, column=1, rowspan=3, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        ttk.Label(preview_frame, text="Preview").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.preview_label = tk.Label(
            preview_frame,
            text="No image",
            anchor="center",
            relief="solid",
            background="#f4f4f4",
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        return frame

    def _build_log_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Execution log")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = ScrolledText(frame, height=16, wrap="word", font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.log_text.insert("end", f"Detected Python: {' '.join(self.python_command)}\n")
        self.log_text.configure(state="disabled")
        return frame

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for button in self.run_buttons:
            button.configure(state=state)

    def _ensure_query(self, value: str, script_name: str) -> str | None:
        cleaned = value.strip()
        if cleaned:
            return cleaned

        messagebox.showwarning(
            "Empty search",
            f"{script_name} was not started because an empty query would scan the whole JSON file.",
        )
        return None

    def _run_extract_cards(self) -> None:
        query = self._ensure_query(self.cards_query.get(), "extract_cards.py")
        if not query:
            return

        script_path = SCRIPT_DIR / "extract_cards.py"
        self._launch_process(
            [*self.python_command, "-u", str(script_path), "--search", query],
            title=f"Card extraction - {query}",
        )

    def _run_extract_models(self) -> None:
        query = self._ensure_query(self.models_query.get(), "extract_models.py")
        if not query:
            return

        script_path = SCRIPT_DIR / "extract_models.py"
        self._launch_process(
            [*self.python_command, "-u", str(script_path), "--search", query],
            title=f"3D model extraction - {query}",
        )

    def _select_pillow_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select an image for the sheet cutter",
            initialdir=str(SCRIPT_DIR.parent),
            filetypes=IMAGE_FILETYPES,
        )
        if not file_path:
            return

        self.selected_image_path = Path(file_path)
        self.pillow_file_var.set(str(self.selected_image_path))
        self._update_preview(self.selected_image_path)

    def _update_preview(self, image_path: Path) -> None:
        try:
            with Image.open(image_path) as image:
                preview = image.copy()
                preview.thumbnail((320, 240))
        except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
            self.preview_photo = None
            self.preview_label.configure(image="", text=f"Could not load image\n{exc}")
            return

        self.preview_photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _run_pillow_cutter(self) -> None:
        if self.selected_image_path is None:
            messagebox.showwarning(
                "Image required",
                "Select an image before running the sheet cutter.",
            )
            return

        try:
            rows = int(self.pillow_rows_var.get().strip())
            cols = int(self.pillow_cols_var.get().strip())
        except ValueError:
            messagebox.showwarning(
                "Invalid values",
                "Rows and columns must be integers.",
            )
            return

        if rows <= 0 or cols <= 0:
            messagebox.showwarning(
                "Invalid values",
                "Rows and columns must be greater than zero.",
            )
            return

        script_path = SCRIPT_DIR / "sheet_cutter.py"
        self._launch_process(
            [
                *self.python_command,
                "-u",
                str(script_path),
                "--input",
                str(self.selected_image_path),
                "--rows",
                str(rows),
                "--cols",
                str(cols),
            ],
            title=f"Image sheet cutter - {self.selected_image_path.name}",
        )

    def _launch_process(self, command: list[str], title: str) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo(
                "Process already running",
                "Wait for the current script to finish before starting another one.",
            )
            return

        self._append_log("")
        self._append_log("=" * 80)
        self._append_log(f"Launching: {title}")
        self._append_log("Command: " + " ".join(command))
        self._set_running_state(True)

        self.worker_thread = threading.Thread(
            target=self._run_process_worker,
            args=(command,),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_process_worker(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(SCRIPT_DIR.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            self.current_process = process

            assert process.stdout is not None
            for line in process.stdout:
                self.log_queue.put(("log", line.rstrip("\n")))

            return_code = process.wait()
            self.log_queue.put(("done", return_code))
        except Exception as exc:
            self.log_queue.put(("error", str(exc)))

    def _flush_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()

                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "done":
                    self._append_log(f"Process finished with exit code {payload}.")
                    self.current_process = None
                    self._set_running_state(False)
                elif kind == "error":
                    self._append_log(f"Could not launch process: {payload}")
                    self.current_process = None
                    self._set_running_state(False)
        except queue.Empty:
            pass

        self.root.after(100, self._flush_log_queue)

    def _on_close(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            should_close = messagebox.askyesno(
                "Close launcher",
                "A script is still running. The window will close, but the process may keep running in the background. Close anyway?",
            )
            if not should_close:
                return

        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ScriptLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
