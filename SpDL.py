#!/usr/bin/env python3
"""
SPOTDL GUI v1.9.0 — Deluxe Spotify Downloader GUI

Author: Minxify_ig
Website: https://minxie.likesyou.org
Github: https://github.com/Minxify/Spotify-downloader-GUI
"""

import os
import sys
import csv
import time
import json
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from queue import Queue, Empty

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import webbrowser

# ---------------- Config ----------------
DEFAULT_OUTPUT_FOLDER_NAME = "Spotify Downloads"
SPOTDL_CMD = "spotdl"
FFMPEG_CMD = "ffmpeg"
DOWNLOAD_TIMEOUT = 300
MAX_RETRIES = 2
RETRY_AFTER_SUCCESS_COUNT = 5
# ----------------------------------------

def sanitize_for_filesystem(name: str, replacement: str = "_") -> str:
    if not name:
        return "Unknown"
    name = "".join(c if c.isprintable() else replacement for c in name.strip())
    name = name.replace("/", replacement).replace("\\", replacement)
    return name[:200]

def format_eta(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def is_tool(name: str) -> bool:
    return shutil.which(name) is not None

# ------------------ GUI App ------------------
class SpotDLGUI:
    def __init__(self):
        # ---------------- UI Thread ----------------
        self.queue = Queue()
        self.track_tasks = []
        self.total_tracks = 0
        self.completed_tracks = 0
        self.retry_queue = []
        self.success_since_last_retry = 0
        self.stop_flag = threading.Event()
        self.executor_thread = None
        self.error_count = 0
        self.log_file_path = None

        # ---------------- Setup UI ----------------
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()
        self.root.title("SPOTDL GUI v1.9.0")
        self.root.geometry("900x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Input type dropdown
        self.input_type_var = ctk.StringVar(value="CSV/TXT")
        self.input_types = ["CSV/TXT", "Spotify Playlist Link"]
        self.input_dropdown = ctk.CTkComboBox(self.root, values=self.input_types, variable=self.input_type_var, command=self.update_input_mode)
        self.input_dropdown.pack(pady=(10,5))

        # CSV input
        self.csv_frame = ctk.CTkFrame(self.root)
        self.csv_frame.pack(fill="x", padx=10)
        self.csv_path_var = ctk.StringVar()
        self.csv_entry = ctk.CTkEntry(self.csv_frame, textvariable=self.csv_path_var, width=600)
        self.csv_entry.pack(side="left", padx=(5,5), pady=5)
        self.csv_btn = ctk.CTkButton(self.csv_frame, text="Select CSV/TXT", command=self.select_csv)
        self.csv_btn.pack(side="left", padx=5, pady=5)

        # Playlist link input
        self.playlist_frame = ctk.CTkFrame(self.root)
        self.playlist_frame.pack(fill="x", padx=10)
        self.playlist_frame.pack_forget()
        self.playlist_var = ctk.StringVar()
        self.playlist_entry = ctk.CTkEntry(self.playlist_frame, textvariable=self.playlist_var, width=600)
        self.playlist_entry.pack(side="left", padx=(5,5), pady=5)

        # Output folder
        out_frame = ctk.CTkFrame(self.root)
        out_frame.pack(fill="x", padx=10, pady=(5,5))
        self.dest_var = ctk.StringVar()
        self.out_entry = ctk.CTkEntry(out_frame, textvariable=self.dest_var, width=600)
        self.out_entry.pack(side="left", padx=(5,5), pady=5)
        self.out_btn = ctk.CTkButton(out_frame, text="Select Folder", command=self.select_out)
        self.out_btn.pack(side="left", padx=5)

        # Subfolder name
        self.subfolder_var = ctk.StringVar(value=DEFAULT_OUTPUT_FOLDER_NAME)
        self.subfolder_entry = ctk.CTkEntry(self.root, textvariable=self.subfolder_var, width=300)
        self.subfolder_entry.pack(padx=10, pady=(0,5))

        # Options
        self.delete_empty_var = ctk.BooleanVar(value=True)
        self.delete_empty_chk = ctk.CTkCheckBox(self.root, text="Delete empty playlist folders after download", variable=self.delete_empty_var)
        self.delete_empty_chk.pack(pady=(0,5))

        # Buttons
        btn_frame = ctk.CTkFrame(self.root)
        btn_frame.pack(pady=(5,10))
        self.start_btn = ctk.CTkButton(btn_frame, text="Start Download", command=self.start_downloads)
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop", command=self.stop_downloads, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        # Progress info
        self.progress_var = ctk.DoubleVar()
        self.progressbar = ctk.CTkProgressBar(self.root, variable=self.progress_var)
        self.progressbar.pack(fill="x", padx=10, pady=(5,2))
        self.progress_label = ctk.CTkLabel(self.root, text="0 / 0 (0.000%)")
        self.progress_label.pack(pady=(0,5))
        self.current_track_label = ctk.CTkLabel(self.root, text="Current track: None")
        self.current_track_label.pack(pady=(0,5))

        # Footer links
        footer_frame = ctk.CTkFrame(self.root)
        footer_frame.pack(side="bottom", pady=5)
        self.website_label = ctk.CTkLabel(footer_frame, text="Hi there!", text_color="cyan", cursor="hand2")
        self.website_label.pack(side="left", padx=5)
        self.website_label.bind("<Button-1>", lambda e: webbrowser.open("https://minxie.likesyou.org"))
        self.github_label = ctk.CTkLabel(footer_frame, text="Github project", text_color="cyan", cursor="hand2")
        self.github_label.pack(side="left", padx=5)
        self.github_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Minxify/Spotify-downloader-GUI"))

        # Cursor bindings
        self.root.bind_all("<Enter>", self.update_cursor)

        # Dependency check
        self.check_dependencies()

        # Start GUI thread
        self.root.mainloop()

    # ---------------- UI Methods ----------------
    def update_input_mode(self, value=None):
        if self.input_type_var.get() == "CSV/TXT":
            self.csv_frame.pack(fill="x", padx=10)
            self.playlist_frame.pack_forget()
        else:
            self.playlist_frame.pack(fill="x", padx=10)
            self.csv_frame.pack_forget()

    def select_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV/TXT Files", "*.csv *.txt")])
        if path:
            self.csv_path_var.set(path)

    def select_out(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_var.set(path)

    def update_cursor(self, event=None):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget:
            cls_name = widget.winfo_class()
            if cls_name in ("CTkEntry", "Entry"):
                widget.configure(cursor="xterm")
            elif cls_name in ("CTkButton", "Button"):
                widget.configure(cursor="hand2")
            else:
                widget.configure(cursor="arrow")

    # ---------------- Dependency Check ----------------
    def check_dependencies(self):
        missing = []
        if not is_tool(SPOTDL_CMD):
            missing.append("spotdl")
        if not is_tool(FFMPEG_CMD):
            missing.append("ffmpeg")
        try:
            import mutagen
        except Exception:
            missing.append("mutagen")
        if missing:
            ans = messagebox.askyesno("Dependencies missing",
                                      f"The following dependencies are required:\n{', '.join(missing)}\nInstall now?")
            if ans:
                for dep in missing:
                    self.install_dependency(dep)
            else:
                messagebox.showinfo("Info", "Cannot run without dependencies.")
                self.root.destroy()

    def install_dependency(self, name):
        try:
            if name == "mutagen":
                subprocess.run(["sudo", "pacman", "-Sy", "--noconfirm", "python-mutagen"], check=True)
            else:
                subprocess.run(["pipx", "install", name], check=True)
        except Exception as e:
            messagebox.showerror("Install failed", f"Failed to install {name}: {e}")

    # ---------------- Download Logic ----------------
    def start_downloads(self):
        self.track_tasks.clear()
        self.completed_tracks = 0
        self.success_since_last_retry = 0
        self.retry_queue.clear()
        self.stop_flag.clear()
        self.error_count = 0

        if self.input_type_var.get() == "CSV/TXT":
            path = self.csv_path_var.get()
            if not os.path.exists(path):
                messagebox.showerror("Error", "Invalid CSV/TXT path")
                return
            self.load_csv(path)
        else:
            link = self.playlist_var.get()
            if not link.strip():
                messagebox.showerror("Error", "Enter a Spotify playlist link")
                return
            self.track_tasks.append({"title": link.strip(), "artist": "", "playlist": "Playlist", "spotify_id": ""})

        self.total_tracks = len(self.track_tasks)
        self.progress_var.set(0)
        self.progress_label.configure(text=f"0 / {self.total_tracks} (0.000%)")
        self.current_track_label.configure(text="Current track: None")

        self.executor_thread = threading.Thread(target=self.download_worker)
        self.executor_thread.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def stop_downloads(self):
        self.stop_flag.set()
        self.stop_btn.configure(state="disabled")

    def load_csv(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.track_tasks.append({
                    "title": row.get("Track name") or row.get("track name") or "",
                    "artist": row.get("Artist name") or row.get("artist name") or "",
                    "playlist": row.get("Playlist name") or row.get("playlist name") or "Default",
                    "spotify_id": row.get("Spotify - id") or row.get("spotify - id") or ""
                })

    def download_worker(self):
        start_time = datetime.now()
        root_out = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get())
        root_out.mkdir(parents=True, exist_ok=True)
        log_name = datetime.now().strftime("ERROR_%y_%m_%d-%H-%M-%S.log")
        self.log_file_path = root_out / log_name

        for idx, track in enumerate(self.track_tasks[:]):
            if self.stop_flag.is_set():
                break
            self.current_track_label.configure(text=f"Current track: {track.get('artist','')} — {track.get('title','')}")
            playlist_folder = root_out / sanitize_for_filesystem(track.get("playlist"))
            playlist_folder.mkdir(parents=True, exist_ok=True)
            out_template = str(playlist_folder / "{artist} - {title}.mp3")
            query = f"https://open.spotify.com/track/{track['spotify_id']}" if track.get("spotify_id") else f"{track.get('artist','')} - {track.get('title','')}"
            cmd = [SPOTDL_CMD, "--output", out_template, "--format", "mp3", query]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT)
                success = proc.returncode == 0
            except Exception:
                success = False

            if not success:
                self.error_count += 1
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{track.get('artist','')} — {track.get('title','')} failed\n")
            self.completed_tracks += 1
            pct = (self.completed_tracks / self.total_tracks)*100
            self.progress_var.set(pct/100)
            self.progress_label.configure(text=f"{self.completed_tracks} / {self.total_tracks} ({pct:.3f}%)")
            self.track_tasks.pop(0)

        # Delete empty folders
        if self.delete_empty_var.get():
            for f in root_out.iterdir():
                if f.is_dir() and not any(f.iterdir()):
                    f.rmdir()

        # All Done popup
        end_time = datetime.now()
        start_fmt = start_time.strftime("%y_%m_%d-%H-%M-%S")
        end_fmt = end_time.strftime("%y_%m_%d-%H-%M-%S")
        messagebox.showinfo("All Done!", f"Downloads finished.\nErrors: {self.error_count}\nTime: {start_fmt} - {end_fmt}")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.current_track_label.configure(text="Current track: None")

    # ---------------- Close ----------------
    def on_close(self):
        if messagebox.askokcancel("Quit", "Exit SPOTDL GUI?"):
            self.stop_flag.set()
            self.root.destroy()

# ---------------- Main ----------------
if __name__ == "__main__":
    SpotDLGUI()
