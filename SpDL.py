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
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta
from queue import Queue, Empty

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import webbrowser

# ---------------- Config ----------------
DEFAULT_OUTPUT_FOLDER_NAME = "Spotify Downloads"
SPOTDL_CMD = "spotdl"
FFMPEG_CMD = "ffmpeg"
DOWNLOAD_TIMEOUT = 300
MAX_RETRIES = 1
RETRY_AFTER_SUCCESS_COUNT = 5
DEFAULT_CONCURRENT_WORKERS = 10
ETA_UPDATE_INTERVAL_SECONDS = 10 # NEW: Define the update frequency
# ----------------------------------------

def sanitize_for_filesystem(name: str, replacement: str = "_") -> str:
    if not name:
        return "Unknown"
    name = "".join(c if c.isprintable() else replacement for c in name.strip())
    name = name.replace("/", replacement).replace("\\", replacement)
    return name[:200]

def format_eta(seconds: int) -> str:
    if seconds <= 0:
        return "N/A" # Return N/A if time is zero or negative

    # Ensure seconds is an integer and non-negative
    seconds = max(0, int(round(seconds)))

    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    parts = []
    if d > 0:
        parts.append(f"{d}d")
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    if s > 0 or not parts: # Show seconds if no other unit or if time is less than 1 minute
        parts.append(f"{s}s")

    return " ".join(parts)

def is_tool(name: str) -> bool:
    return shutil.which(name) is not None

# ------------------ GUI App ------------------
class SpotDLGUI:
    def __init__(self):
        # ---------------- UI Thread & Concurrency Setup ----------------
        self.queue = Queue()
        self.result_queue = Queue()
        self.track_tasks = []
        self.total_tracks = 0
        self.completed_tracks = 0
        self.stop_flag = threading.Event()
        self.executor_thread = None
        self.error_count = 0
        self.log_file_path = None

        # Concurrency management
        self.executor = None
        self.active_futures = []

        # ETA Management (NEW)
        self.download_start_time = None
        self.last_eta_update_time = datetime.min # Initialize to minimum possible time

        # ---------------- Setup UI ----------------
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()
        self.root.title("SPOTDL GUI v2.0.0 (Concurrent)")
        self.root.geometry("900x750") # Slightly taller to accommodate new label
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

        # Concurrency and Subfolder Frame
        option_frame = ctk.CTkFrame(self.root)
        option_frame.pack(fill="x", padx=10, pady=(0, 5))

        # Subfolder name
        self.subfolder_var = ctk.StringVar(value=DEFAULT_OUTPUT_FOLDER_NAME)
        subfolder_label = ctk.CTkLabel(option_frame, text="Output Subfolder:")
        subfolder_label.pack(side="left", padx=(5, 5), pady=5)
        self.subfolder_entry = ctk.CTkEntry(option_frame, textvariable=self.subfolder_var, width=200)
        self.subfolder_entry.pack(side="left", padx=(0, 20), pady=5)

        # Concurrent Downloads Option
        self.concurrent_var = ctk.IntVar(value=DEFAULT_CONCURRENT_WORKERS)
        concurrent_label = ctk.CTkLabel(option_frame, text="Concurrent Downloads:")
        concurrent_label.pack(side="left", padx=(20, 5), pady=5)
        self.concurrent_entry = ctk.CTkEntry(option_frame, textvariable=self.concurrent_var, width=50)
        self.concurrent_entry.pack(side="left", padx=(0, 5), pady=5)


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

        # ETA Label (NEW)
        self.eta_label = ctk.CTkLabel(self.root, text="ETA: Ready")
        self.eta_label.pack(pady=(0,5))

        self.current_track_label = ctk.CTkLabel(self.root, text="Current track: None")
        self.current_track_label.pack(pady=(0,5))
        self.status_label = ctk.CTkLabel(self.root, text="Status: Ready")
        self.status_label.pack(pady=(0,5))

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
        # NOTE: Using a placeholder check here since mutagen import is handled outside of runtime
        missing = []
        if not is_tool(SPOTDL_CMD):
            missing.append("spotdl")
        if not is_tool(FFMPEG_CMD):
            missing.append("ffmpeg")
        if missing:
            messagebox.showinfo("Dependencies missing",
                                      f"The following dependencies are required:\n{', '.join(missing)}\nPlease install them manually.")

    def install_dependency(self, name):
        # Removed automatic installation logic as it often requires elevated privileges (sudo/pipx)
        # and can be unreliable in a general context. Informing the user is safer.
        pass

    # ---------------- Download Logic ----------------

    def start_downloads(self):
        try:
            workers = self.concurrent_var.get()
            if not isinstance(workers, int) or workers <= 0:
                 workers = DEFAULT_CONCURRENT_WORKERS
                 self.concurrent_var.set(workers)
        except Exception:
            workers = DEFAULT_CONCURRENT_WORKERS
            self.concurrent_var.set(workers)

        self.track_tasks.clear()
        self.completed_tracks = 0
        self.error_count = 0
        self.stop_flag.clear()
        self.active_futures.clear()

        # ETA Initialization (NEW)
        self.download_start_time = datetime.now()
        self.last_eta_update_time = datetime.now()


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
            # For playlist links, we rely on spotdl to resolve tracks internally, so it's one task
            self.track_tasks.append({"title": link.strip(), "artist": "Playlist", "playlist": "Playlist", "spotify_id": ""})

        self.total_tracks = len(self.track_tasks)
        if self.total_tracks == 0:
            messagebox.showinfo("Info", "No tracks found to download.")
            return

        self.progress_var.set(0)
        self.progress_label.configure(text=f"0 / {self.total_tracks} (0.000%)")
        self.eta_label.configure(text="ETA: Calculating...")
        self.current_track_label.configure(text="Current track: Starting...")
        self.status_label.configure(text=f"Status: Initializing {workers} workers.")

        # Start the background execution thread
        self.executor_thread = threading.Thread(target=self.download_coordinator, args=(workers,))
        self.executor_thread.start()

        # Start the UI update poller
        self.root.after(100, self._check_download_status)

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")


    def stop_downloads(self):
        self.stop_flag.set()
        self.status_label.configure(text="Status: Stopping downloads...")
        self.eta_label.configure(text="ETA: Stopping...")
        self.stop_btn.configure(state="disabled")

    def load_csv(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            # Try to infer if header is present
            try:
                # Read the first chunk to detect dialect and header
                first_lines = "".join(f.readline() for _ in range(5))
                f.seek(0)

                if 'Track name' in first_lines or 'track name' in first_lines:
                    reader = csv.DictReader(f)
                else:
                    # Assume no header, just a list of queries/links
                    reader = csv.reader(f)

            except Exception:
                f.seek(0)
                reader = csv.reader(f) # Fallback to simple reader

            if isinstance(reader, csv.DictReader):
                for row in reader:
                    self.track_tasks.append({
                        "title": row.get("Track name") or row.get("track name") or "",
                        "artist": row.get("Artist name") or row.get("artist name") or "",
                        "playlist": row.get("Playlist name") or row.get("playlist name") or "Default",
                        "spotify_id": row.get("Spotify - id") or row.get("spotify - id") or ""
                    })
            else:
                for row in reader:
                    query = row[0].strip() if row else ""
                    if query:
                        # Treat the entire line as the spotDL query
                        self.track_tasks.append({
                            "title": query,
                            "artist": "",
                            "playlist": "Default",
                            "spotify_id": ""
                        })

    def _download_single_track(self, track: dict, root_out: Path) -> dict:
        """
        Executes the spotdl command for a single track. Runs on a worker thread.
        """
        if self.stop_flag.is_set():
            return {"track": track, "success": False, "skipped": True}

        title = track.get('title','')
        artist = track.get('artist','')

        # Determine the correct output path and query
        playlist_folder_name = sanitize_for_filesystem(track.get("playlist", "Default"))
        playlist_folder = root_out / playlist_folder_name
        playlist_folder.mkdir(parents=True, exist_ok=True)

        # NOTE: spotdl handles the output template, we just pass the folder
        out_folder = str(playlist_folder)

        # Use Spotify ID or clean query string
        query = f"https://open.spotify.com/track/{track['spotify_id']}" \
            if track.get("spotify_id") and track.get("spotify_id") != "null" \
            else f"{artist} - {title}"

        cmd = [
            SPOTDL_CMD,
            query,
            "--output", out_folder,
            "--format", "mp3",
            "--overwrite", "skip",
            "--log-level", "ERROR"
        ]

        error_message = ""
        try:
            self.result_queue.put({"type": "current_track", "info": f"{artist} — {title}"})

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=DOWNLOAD_TIMEOUT,
                check=True # Raise CalledProcessError if return code is non-zero
            )
            success = proc.returncode == 0

        except subprocess.TimeoutExpired:
            success = False
            error_message = f"Timeout ({DOWNLOAD_TIMEOUT}s) occurred."
        except subprocess.CalledProcessError as e:
            success = False
            error_message = f"spotdl failed (Exit Code {e.returncode}). Output: {e.stderr}"
        except Exception as e:
            success = False
            error_message = f"Download process failed: {e}"

        if not success:
            log_entry = f"{title} by {artist} failed. Query: '{query}'. Error: {error_message}\n"
            # Since we are in a worker thread, we write directly to the log file (which is safe)
            with open(root_out.parent / self.log_file_path, "a", encoding="utf-8") as f:
                 f.write(log_entry)

        return {"track": track, "success": success, "skipped": self.stop_flag.is_set()}


    def download_coordinator(self, workers: int):
        """
        The main coordinator function running on a separate thread.
        It uses the ThreadPoolExecutor to run tasks in parallel.
        """
        root_out = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get())
        root_out.mkdir(parents=True, exist_ok=True)
        log_name = datetime.now().strftime("ERROR_%y_%m_%d-%H-%M-%S.log")
        self.log_file_path = root_out.parent / log_name # Store log file one level up

        self.status_label.configure(text=f"Status: Running {workers} concurrent downloads...")

        # Use ThreadPoolExecutor for concurrent execution
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

        # Submit all tasks to the executor
        for track in self.track_tasks:
            future = self.executor.submit(self._download_single_track, track, root_out)
            self.active_futures.append(future)

        # Wait for all futures to complete (or for stop_flag)
        for future in concurrent.futures.as_completed(self.active_futures):
            if self.stop_flag.is_set():
                break # Exit the loop if stop is requested

            try:
                result = future.result()
                self.result_queue.put({"type": "result", "data": result})
            except Exception as e:
                # Should not happen if _download_single_track handles exceptions, but good practice
                self.result_queue.put({"type": "error", "message": f"Future failed: {e}"})

        # Wait for any currently running tasks to finish (optional, but cleaner shutdown)
        self.executor.shutdown(wait=True)
        self.executor = None # Clear executor reference

        # Signal completion to the main thread
        self.result_queue.put({"type": "finished"})


    def _update_eta(self):
        """
        Calculates and updates the Estimated Time of Arrival (ETA).
        """
        if self.completed_tracks == 0 or self.stop_flag.is_set() or self.total_tracks == 0:
            self.eta_label.configure(text="ETA: Calculating...")
            return

        current_time = datetime.now()
        # Time elapsed in seconds
        time_elapsed = (current_time - self.download_start_time).total_seconds()

        # Avoid division by zero, though completed_tracks > 0 is checked above
        if self.completed_tracks > 0 and time_elapsed > 0:
            # Calculate average time per completed track
            avg_time_per_track = time_elapsed / self.completed_tracks

            # Calculate remaining tracks and remaining time
            remaining_tracks = self.total_tracks - self.completed_tracks
            remaining_seconds = avg_time_per_track * remaining_tracks

            # Format and display
            eta_str = format_eta(remaining_seconds)
            self.eta_label.configure(text=f"ETA: {eta_str}")
        else:
            self.eta_label.configure(text="ETA: N/A")

        self.last_eta_update_time = current_time # Update tracking timestamp


    def _check_download_status(self):
        """
        This function runs periodically on the main UI thread to safely
        process results from the worker threads and update the GUI.
        """
        keep_polling = True

        while not self.result_queue.empty():
            try:
                item = self.result_queue.get_nowait()

                if item["type"] == "finished":
                    self._final_cleanup()
                    keep_polling = False
                    break

                elif item["type"] == "current_track":
                    self.current_track_label.configure(text=f"Current track: {item['info']}")

                elif item["type"] == "result":
                    result = item["data"]
                    if not result["success"]:
                        self.error_count += 1

                    if not result["skipped"]:
                        self.completed_tracks += 1

                    # Update progress bar
                    pct = (self.completed_tracks / self.total_tracks) * 100
                    self.progress_var.set(pct / 100)
                    self.progress_label.configure(text=f"{self.completed_tracks} / {self.total_tracks} ({pct:.3f}%)")
                    self.status_label.configure(text=f"Status: Downloading... Errors: {self.error_count}")

                elif item["type"] == "error":
                    # Handle general errors from the future
                    print(f"FATAL THREAD ERROR: {item['message']}")
                    self.error_count += 1

            except Empty:
                break

        if keep_polling:
            # Check if 10 seconds have passed since the last ETA update
            time_since_last_update = (datetime.now() - self.last_eta_update_time).total_seconds()
            if time_since_last_update >= ETA_UPDATE_INTERVAL_SECONDS:
                self._update_eta()

            self.root.after(500, self._check_download_status) # Poll again in 500ms


    def _final_cleanup(self):
        """
        Final steps after all downloads (or stop signal) have been processed.
        Runs on the main UI thread.
        """
        self.status_label.configure(text="Status: Cleaning up...")
        self.eta_label.configure(text="ETA: Complete")

        root_out = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get())

        # Delete empty folders
        if self.delete_empty_var.get():
            try:
                for f in root_out.iterdir():
                    if f.is_dir() and not any(f.iterdir()):
                        f.rmdir()
            except Exception as e:
                print(f"Error deleting empty folder: {e}")

        # All Done popup
        end_time = datetime.now()
        messagebox.showinfo(
            "All Done!",
            f"Downloads finished or stopped.\nTotal completed: {self.completed_tracks} / {self.total_tracks}\nErrors recorded: {self.error_count}"
        )

        # Reset UI
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.current_track_label.configure(text="Current track: None")
        self.status_label.configure(text="Status: Ready")


    # ---------------- Close ----------------
    def on_close(self):
        if messagebox.askokcancel("Quit", "Exit SPOTDL GUI?"):
            self.stop_flag.set()
            # If executor is still running (e.g., during stop_downloads), shut it down
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()

# ---------------- Main ----------------
if __name__ == "__main__":
    SpotDLGUI()
