from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable


APP_NAME = "Quick App Launcher"


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = get_base_dir() / "appsettings.json"


@dataclass
class AppEntry:
    name: str
    path: str
    arguments: str = ""
    working_directory: str = ""
    delay_seconds: int = 0
    enabled: bool = True
    startup_enabled: bool = False
    prevent_duplicate: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "AppEntry":
        return cls(
            name=str(data.get("name", "")).strip(),
            path=str(data.get("path", "")).strip(),
            arguments=str(data.get("arguments", "")).strip(),
            working_directory=str(data.get("working_directory", "")).strip(),
            delay_seconds=max(0, int(data.get("delay_seconds", 0) or 0)),
            enabled=bool(data.get("enabled", True)),
            startup_enabled=bool(data.get("startup_enabled", False)),
            prevent_duplicate=bool(data.get("prevent_duplicate", True)),
        )


def default_config() -> dict:
    return {
        "version": 1,
        "startup_initial_delay_seconds": 30,
        "apps": [],
    }


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        config = default_config()
        save_config(config)
        return config

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        backup = CONFIG_PATH.with_suffix(".invalid.json")
        try:
            CONFIG_PATH.replace(backup)
        except OSError:
            pass
        raise RuntimeError(f"設定檔無法讀取，已嘗試備份為 {backup.name}：{exc}") from exc

    config = default_config()
    config["startup_initial_delay_seconds"] = max(
        0, int(raw.get("startup_initial_delay_seconds", 30) or 0)
    )
    config["apps"] = [
        asdict(AppEntry.from_dict(item))
        for item in raw.get("apps", [])
        if isinstance(item, dict)
    ]
    return config


def save_config(config: dict) -> None:
    temp_path = CONFIG_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    temp_path.replace(CONFIG_PATH)


def expand_path(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value.strip().strip('"')))


def split_arguments(arguments: str) -> list[str]:
    if not arguments.strip():
        return []
    # Windows 下由 subprocess 處理完整命令列較可靠；這裡保留 quoted arguments。
    import shlex
    return shlex.split(arguments, posix=False)


def process_is_running(executable_path: str) -> bool:
    """Best-effort duplicate detection using Windows tasklist; failure means 'unknown'."""
    if os.name != "nt":
        return False

    executable_name = Path(executable_path).name
    if not executable_name:
        return False

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {executable_name}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
            check=False,
        )
        return executable_name.lower() in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def launch_app(app: AppEntry, log: Callable[[str], None]) -> bool:
    path = expand_path(app.path)
    if not path:
        log(f"[略過] {app.name}：未設定路徑")
        return False

    if not Path(path).exists():
        log(f"[失敗] {app.name}：找不到 {path}")
        return False

    if app.prevent_duplicate and process_is_running(path):
        log(f"[略過] {app.name}：程式已在執行")
        return True

    working_directory = expand_path(app.working_directory)
    if not working_directory:
        working_directory = str(Path(path).parent)

    command = [path, *split_arguments(app.arguments)]

    try:
        subprocess.Popen(
            command,
            cwd=working_directory if Path(working_directory).is_dir() else None,
            shell=False,
        )
        log(f"[完成] 已啟動 {app.name}")
        return True
    except OSError as exc:
        log(f"[失敗] {app.name}：{exc}")
        return False


def launch_sequence(
    apps: list[AppEntry],
    log: Callable[[str], None],
    stop_event: threading.Event | None = None,
) -> None:
    selected = [app for app in apps if app.enabled]
    if not selected:
        log("沒有可啟動的項目。")
        return

    for app in selected:
        if stop_event and stop_event.is_set():
            log("啟動流程已取消。")
            return

        delay = max(0, app.delay_seconds)
        if delay:
            log(f"[等待] {app.name}：{delay} 秒")
            for _ in range(delay * 10):
                if stop_event and stop_event.is_set():
                    log("啟動流程已取消。")
                    return
                time.sleep(0.1)

        launch_app(app, log)

    log("啟動流程結束。")


class AppDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: AppEntry | None = None):
        super().__init__(parent)
        self.title("新增應用程式" if app is None else "編輯應用程式")
        self.resizable(False, False)
        self.result: AppEntry | None = None
        self.transient(parent)
        self.grab_set()

        app = app or AppEntry(name="", path="")

        self.name_var = tk.StringVar(value=app.name)
        self.path_var = tk.StringVar(value=app.path)
        self.args_var = tk.StringVar(value=app.arguments)
        self.cwd_var = tk.StringVar(value=app.working_directory)
        self.delay_var = tk.StringVar(value=str(app.delay_seconds))
        self.enabled_var = tk.BooleanVar(value=app.enabled)
        self.startup_var = tk.BooleanVar(value=app.startup_enabled)
        self.duplicate_var = tk.BooleanVar(value=app.prevent_duplicate)

        frame = ttk.Frame(self, padding=12)
        frame.grid(sticky="nsew")

        self._row(frame, 0, "名稱", self.name_var)
        self._path_row(frame, 1, "執行檔", self.path_var, self._browse_executable)
        self._row(frame, 2, "啟動參數", self.args_var)
        self._path_row(frame, 3, "工作目錄", self.cwd_var, self._browse_directory)
        self._row(frame, 4, "啟動前延遲（秒）", self.delay_var)

        ttk.Checkbutton(frame, text="啟用此項目", variable=self.enabled_var).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(
            frame, text="自動啟動模式包含此項目", variable=self.startup_var
        ).grid(row=6, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(
            frame, text="偵測到程式已執行時略過", variable=self.duplicate_var
        ).grid(row=7, column=0, columnspan=3, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="儲存", command=self._save).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Return>", lambda _: self._save())
        self.wait_visibility()
        self.focus_set()

    @staticmethod
    def _row(parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=58).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4
        )

    @staticmethod
    def _path_row(parent, row, label, variable, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=48).grid(
            row=row, column=1, sticky="ew", padx=(8, 4), pady=4
        )
        ttk.Button(parent, text="瀏覽", command=command).grid(
            row=row, column=2, sticky="ew", pady=4
        )

    def _browse_executable(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="選擇應用程式",
            filetypes=[
                ("應用程式", "*.exe"),
                ("捷徑", "*.lnk"),
                ("所有檔案", "*.*"),
            ],
        )
        if path:
            self.path_var.set(path)
            if not self.name_var.get().strip():
                self.name_var.set(Path(path).stem)

    def _browse_directory(self) -> None:
        path = filedialog.askdirectory(parent=self, title="選擇工作目錄")
        if path:
            self.cwd_var.set(path)

    def _save(self) -> None:
        name = self.name_var.get().strip()
        path = self.path_var.get().strip()
        if not name or not path:
            messagebox.showwarning("資料不完整", "名稱與執行檔路徑為必填。", parent=self)
            return

        try:
            delay = max(0, int(self.delay_var.get().strip() or "0"))
        except ValueError:
            messagebox.showwarning("格式錯誤", "延遲秒數必須是整數。", parent=self)
            return

        self.result = AppEntry(
            name=name,
            path=path,
            arguments=self.args_var.get().strip(),
            working_directory=self.cwd_var.get().strip(),
            delay_seconds=delay,
            enabled=self.enabled_var.get(),
            startup_enabled=self.startup_var.get(),
            prevent_duplicate=self.duplicate_var.get(),
        )
        self.destroy()


class LauncherUI:
    def __init__(self, config: dict):
        self.config = config
        self.apps = [AppEntry.from_dict(item) for item in config.get("apps", [])]
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("860x560")
        self.root.minsize(720, 460)

        self._build()
        self._refresh()
        self.root.after(100, self._drain_log_queue)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="新增", command=self._add).pack(side="left")
        ttk.Button(toolbar, text="編輯", command=self._edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="移除", command=self._remove).pack(side="left")
        ttk.Button(toolbar, text="上移", command=lambda: self._move(-1)).pack(
            side="left", padx=(12, 4)
        )
        ttk.Button(toolbar, text="下移", command=lambda: self._move(1)).pack(
            side="left"
        )

        ttk.Button(toolbar, text="啟動選取", command=self._launch_selected).pack(
            side="right"
        )
        ttk.Button(toolbar, text="啟動全部", command=self._launch_all).pack(
            side="right", padx=4
        )
        ttk.Button(toolbar, text="取消流程", command=self.stop_event.set).pack(
            side="right"
        )

        columns = ("enabled", "name", "delay", "startup", "path")
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=12)
        self.tree.heading("enabled", text="啟用")
        self.tree.heading("name", text="名稱")
        self.tree.heading("delay", text="延遲")
        self.tree.heading("startup", text="自動啟動")
        self.tree.heading("path", text="路徑")
        self.tree.column("enabled", width=55, anchor="center", stretch=False)
        self.tree.column("name", width=150)
        self.tree.column("delay", width=70, anchor="center", stretch=False)
        self.tree.column("startup", width=85, anchor="center", stretch=False)
        self.tree.column("path", width=430)
        self.tree.pack(fill="both", expand=True, pady=(10, 8))
        self.tree.bind("<Double-1>", lambda _: self._edit())

        settings = ttk.Frame(outer)
        settings.pack(fill="x", pady=(0, 8))
        ttk.Label(settings, text="自動啟動模式的初始等待：").pack(side="left")
        self.initial_delay_var = tk.StringVar(
            value=str(self.config.get("startup_initial_delay_seconds", 30))
        )
        ttk.Entry(settings, textvariable=self.initial_delay_var, width=7).pack(
            side="left"
        )
        ttk.Label(settings, text="秒").pack(side="left", padx=(4, 12))
        ttk.Button(settings, text="儲存設定", command=self._save).pack(side="left")
        ttk.Button(
            settings, text="開啟設定檔位置", command=self._open_config_folder
        ).pack(side="left", padx=4)

        ttk.Label(outer, text="執行紀錄").pack(anchor="w")
        self.log_box = tk.Text(outer, height=9, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=False)

    def _refresh(self, selected_index: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, app in enumerate(self.apps):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    "是" if app.enabled else "否",
                    app.name,
                    f"{app.delay_seconds} 秒",
                    "是" if app.startup_enabled else "否",
                    app.path,
                ),
            )
        if selected_index is not None and 0 <= selected_index < len(self.apps):
            self.tree.selection_set(str(selected_index))
            self.tree.focus(str(selected_index))

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _add(self) -> None:
        dialog = AppDialog(self.root)
        self.root.wait_window(dialog)
        if dialog.result:
            self.apps.append(dialog.result)
            self._save(silent=True)
            self._refresh(len(self.apps) - 1)

    def _edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = AppDialog(self.root, self.apps[index])
        self.root.wait_window(dialog)
        if dialog.result:
            self.apps[index] = dialog.result
            self._save(silent=True)
            self._refresh(index)

    def _remove(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        if messagebox.askyesno("確認移除", f"要移除「{self.apps[index].name}」嗎？"):
            del self.apps[index]
            self._save(silent=True)
            self._refresh(min(index, len(self.apps) - 1))

    def _move(self, offset: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        target = index + offset
        if 0 <= target < len(self.apps):
            self.apps[index], self.apps[target] = self.apps[target], self.apps[index]
            self._save(silent=True)
            self._refresh(target)

    def _save(self, silent: bool = False) -> None:
        try:
            initial_delay = max(0, int(self.initial_delay_var.get().strip() or "0"))
        except ValueError:
            messagebox.showwarning("格式錯誤", "初始等待秒數必須是整數。")
            return

        self.config["startup_initial_delay_seconds"] = initial_delay
        self.config["apps"] = [asdict(app) for app in self.apps]
        save_config(self.config)
        if not silent:
            self._log("設定已儲存。")

    def _launch_all(self) -> None:
        self._start_worker([app for app in self.apps if app.enabled])

    def _launch_selected(self) -> None:
        indices = [int(item) for item in self.tree.selection()]
        self._start_worker([self.apps[index] for index in indices])

    def _start_worker(self, apps: list[AppEntry]) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在執行", "已有一組啟動流程正在執行。")
            return
        self.stop_event.clear()
        self.worker = threading.Thread(
            target=launch_sequence,
            args=(apps, self._thread_log, self.stop_event),
            daemon=True,
        )
        self.worker.start()

    def _thread_log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                self._log(self.log_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(100, self._drain_log_queue)

    def _log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{time.strftime('%H:%M:%S')}  {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    @staticmethod
    def _open_config_folder() -> None:
        if os.name == "nt":
            os.startfile(str(CONFIG_PATH.parent))
        else:
            subprocess.Popen(["xdg-open", str(CONFIG_PATH.parent)])

    def run(self) -> None:
        self.root.mainloop()


def run_startup_mode(config: dict) -> None:
    initial_delay = max(0, int(config.get("startup_initial_delay_seconds", 30)))
    if initial_delay:
        time.sleep(initial_delay)

    apps = [
        AppEntry.from_dict(item)
        for item in config.get("apps", [])
        if bool(item.get("startup_enabled", False))
    ]

    log_path = get_base_dir() / "launcher.log"

    def file_log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

    launch_sequence(apps, file_log)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--startup",
        action="store_true",
        help="以無介面自動啟動模式執行，只開啟標記為自動啟動的項目。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config()
    except RuntimeError as exc:
        if args.startup:
            return 1
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, str(exc))
        return 1

    if args.startup:
        run_startup_mode(config)
        return 0

    LauncherUI(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
