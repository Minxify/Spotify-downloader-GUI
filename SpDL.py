#!/usr/bin/env python3
"""
SPOTDL GUI v3.0.0 — Deluxe Spotify Downloader GUI

Author: Minxify_ig
Website: https://minxie.likesyou.org
Github: https://github.com/Minxify/Spotify-downloader-GUI
Year: 2026
"""

import os, sys, csv, time, json, shutil, threading, subprocess, re, uuid
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta
from queue import Queue, Empty
from dataclasses import dataclass, asdict, field
from typing import Optional
import webbrowser
import html

def _find_spotdl() -> list[str]:
    which = shutil.which("spotdl")
    if which:
        return [which]
    return [sys.executable, "-m", "spotdl"]

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

# Optional: system tray
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# Optional: spotipy (for search + OAuth)
try:
    import spotipy
    from spotipy.oauth2 import SpotifyPKCE
    HAS_SPOTIPY = True
except ImportError:
    HAS_SPOTIPY = False

# ═══════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════

VERSION = "3.0.0"
APP_NAME = "SPOTDL GUI"

DEFAULT_OUTPUT_FOLDER_NAME = "Spotify Downloads"
SPOTDL_CMD = _find_spotdl()
DOWNLOAD_TIMEOUT = 300
MAX_RETRIES = 1
DEFAULT_CONCURRENT_WORKERS = 10
ETA_UPDATE_INTERVAL_SECONDS = 5

CACHE_DIR = Path.home() / ".cache" / "spotdl-gui"
CONFIG_DIR = Path.home() / ".config" / "spotdl-gui"
PRESETS_DIR = CONFIG_DIR / "presets"
RESUME_FILE = CACHE_DIR / "resume.json"
SPOTIFY_CREDS_FILE = CONFIG_DIR / "spotify_creds.json"

FORMATS = ["mp3", "flac", "ogg", "opus", "m4a", "wav"]

BITRATE_GROUPS = {
    "Low (32k-64k)":  ["32k", "48k", "64k"],
    "Medium (80k-128k)":  ["80k", "96k", "112k", "128k"],
    "High (160k-192k)": ["160k", "192k"],
    "Very High (224k-320k)": ["224k", "256k", "320k"],
    "Lossless": None,
}

ALL_BITRATES_FLAT = ["8k", "16k", "24k", "32k", "40k", "48k", "64k",
                     "80k", "96k", "112k", "128k", "160k", "192k",
                     "224k", "256k", "320k"]

NOTIFICATION_OPTIONS = [
    "On complete only",
    "On complete + on error",
    "Every track + done",
]

FOLDER_STRUCTURES = [
    "By playlist",
    "By artist / album",
    "Flat",
]

INPUT_MODES = ["Smart (auto-detect)", "Spotify Link", "Search", "CSV / TXT"]

LYRICS_PROVIDERS = ["genius", "musixmatch", "azlyrics", "synced"]

SIZE_ESTIMATE_BITRATES = {
    "mp3":  320,
    "ogg":  256,
    "opus": 160,
    "m4a":  256,
    "flac": 900,
    "wav":  1411,
}
REF_DURATION_SEC = 195

# ═══════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════

def sanitize_for_filesystem(name: str, replacement: str = "_") -> str:
    if not name:
        return "Unknown"
    name = "".join(c if c.isprintable() else replacement for c in name.strip())
    name = name.replace("/", replacement).replace("\\", replacement).replace(":", replacement)
    return name[:200]

def format_eta(seconds: int) -> str:
    if seconds <= 0:
        return "N/A"
    seconds = max(0, int(round(seconds)))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d > 0: parts.append(f"{d}d")
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    if s > 0 or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def is_tool(name: str) -> bool:
    return shutil.which(name) is not None

def estimate_size_mb(format_: str, bitrate_str: Optional[str], duration_sec: int) -> float:
    if format_ == "wav":
        kbps = 1411
    elif format_ == "flac":
        kbps = 900
    elif bitrate_str and bitrate_str.rstrip("k").isdigit():
        kbps = int(bitrate_str.rstrip("k"))
    else:
        kbps = SIZE_ESTIMATE_BITRATES.get(format_, 320)
    bytes_total = (kbps * 1000 / 8) * duration_sec
    return bytes_total / (1024 * 1024)

def parse_spotify_url(url: str) -> Optional[dict]:
    m = re.search(r"open\.spotify\.com/(track|album|playlist|artist|episode|show)/([a-zA-Z0-9]+)", url)
    if m:
        return {"type": m.group(1), "id": m.group(2)}
    return None

def make_spotdl_cmd(query: str, out_template: str, format_: str, bitrate: Optional[str],
                     lyrics: bool, lyrics_provider: str,
                     overwrite: str = "skip", log_level: str = "ERROR") -> list:
    cmd = [*SPOTDL_CMD, "download", query, "--output", out_template,
           "--overwrite", overwrite, "--log-level", log_level]

    if format_:
        cmd += ["--format", format_]
    if bitrate and bitrate not in ("0", "lossless"):
        cmd += ["--bitrate", bitrate]
    if lyrics and lyrics_provider:
        cmd += ["--lyrics", lyrics_provider, "--generate-lrc"]

    return cmd

def get_default_output_template(folder_struct: str) -> str:
    if folder_struct == "Flat":
        return "{title}.{ext}"
    elif folder_struct == "By artist / album":
        return "{artists}/{album}/{title}.{ext}"
    return "{playlist}/{title}.{ext}"

def send_notification(title: str, message: str):
    try:
        subprocess.run(["notify-send", title, message], timeout=5)
    except Exception:
        pass

# ═══════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════

@dataclass
class TrackItem:
    uid: str = ""
    title: str = ""
    artist: str = ""
    playlist: str = ""
    spotify_id: str = ""
    query: str = ""
    status: str = "pending"
    error: str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = uuid.uuid4().hex[:12]

@dataclass
class Preset:
    name: str = "Default"
    output_folder: str = ""
    subfolder: str = DEFAULT_OUTPUT_FOLDER_NAME
    format_: str = "mp3"
    bitrate: str = "320k"
    concurrent: int = DEFAULT_CONCURRENT_WORKERS
    delete_empty: bool = True
    folder_structure: str = "By playlist"
    lyrics: bool = False
    lyrics_provider: str = "genius"
    notifications: str = "On complete only"
    input_mode: str = "CSV / TXT"

@dataclass
class ResumeState:
    input_mode: str = ""
    input_data: str = ""
    tracks: list = field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    output_folder: str = ""
    subfolder: str = ""
    format_: str = "mp3"
    bitrate: str = "320k"
    folder_structure: str = "By playlist"
    lyrics: bool = False
    lyrics_provider: str = "genius"
    concurrent: int = DEFAULT_CONCURRENT_WORKERS
    delete_empty: bool = True
    timestamp: str = ""

# ═══════════════════════════════════════════════
# PRESET MANAGER
# ═══════════════════════════════════════════════

class PresetManager:
    def __init__(self):
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        self.presets: dict[str, Preset] = {}
        self.load_all()

    def load_all(self):
        self.presets.clear()
        if PRESETS_DIR.exists():
            for f in sorted(PRESETS_DIR.iterdir()):
                if f.suffix == ".json":
                    try:
                        data = json.loads(f.read_text())
                        self.presets[data["name"]] = Preset(**data)
                    except Exception:
                        pass
        if "Default" not in self.presets:
            self.presets["Default"] = Preset()

    def save(self, preset: Preset):
        path = PRESETS_DIR / f"{sanitize_for_filesystem(preset.name)}.json"
        path.write_text(json.dumps(asdict(preset), indent=2))
        self.presets[preset.name] = preset

    def delete(self, name: str):
        if name in self.presets and name != "Default":
            path = PRESETS_DIR / f"{sanitize_for_filesystem(name)}.json"
            if path.exists():
                path.unlink()
            del self.presets[name]

    def get_names(self) -> list[str]:
        return list(self.presets.keys())

    def get(self, name: str) -> Optional[Preset]:
        return self.presets.get(name)

# ═══════════════════════════════════════════════
# RESUME MANAGER
# ═══════════════════════════════════════════════

class ResumeManager:
    @staticmethod
    def save(state: ResumeState):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(state)
        data["tracks"] = [asdict(t) if isinstance(t, TrackItem) else t for t in state.tracks]
        RESUME_FILE.write_text(json.dumps(data, indent=2))

    @staticmethod
    def load() -> Optional[ResumeState]:
        if RESUME_FILE.exists():
            try:
                data = json.loads(RESUME_FILE.read_text())
                state = ResumeState(**{k: v for k, v in data.items() if k != "tracks"})
                state.tracks = [TrackItem(**t) for t in data.get("tracks", [])]
                return state
            except Exception as e:
                print(f"Failed to load resume state: {e}")
        return None

    @staticmethod
    def clear():
        if RESUME_FILE.exists():
            RESUME_FILE.unlink()

    @staticmethod
    def exists() -> bool:
        return RESUME_FILE.exists()

# ═══════════════════════════════════════════════
# SPOTIFY AUTH / API
# ═══════════════════════════════════════════════

class SpotifyHelper:
    """Handles Spotify OAuth via PKCE (browser sign-in, no Client Secret needed)."""

    REDIRECT_URI = "http://localhost:8888/callback"

    def __init__(self, root=None):
        self.root = root
        self.client: Optional[spotipy.Spotify] = None
        self.sp_oauth: Optional[SpotifyPKCE] = None
        self.client_id: str = ""
        self.auth_mode = "none"
        self._load_config()

    def _load_config(self):
        if SPOTIFY_CREDS_FILE.exists():
            try:
                creds = json.loads(SPOTIFY_CREDS_FILE.read_text())
                self.client_id = creds.get("client_id", "")
                if self.client_id:
                    self._init_pkce()
            except Exception:
                pass

    def _init_pkce(self):
        if not HAS_SPOTIPY:
            return
        try:
            self.sp_oauth = SpotifyPKCE(
                client_id=self.client_id,
                redirect_uri=self.REDIRECT_URI,
                scope="playlist-read-private playlist-read-collaborative user-library-read user-follow-read",
                cache_path=str(CONFIG_DIR / ".spotify_token"),
                open_browser=True,
            )
            token = self.sp_oauth.get_cached_token()
            if token:
                self.client = spotipy.Spotify(auth=token["access_token"])
                self.auth_mode = "oauth"
        except Exception:
            pass

    def save_client_id(self, client_id: str):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {"client_id": client_id, "redirect_uri": self.REDIRECT_URI}
        SPOTIFY_CREDS_FILE.write_text(json.dumps(data, indent=2))
        self.client_id = client_id
        self._init_pkce()

    def sign_in(self, on_done):
        """Run PKCE OAuth flow in a thread. on_done(success, display_name) is called on the main thread."""
        def _run():
            try:
                token = self.sp_oauth.get_access_token()
                if token:
                    self.client = spotipy.Spotify(auth=token["access_token"])
                    self.auth_mode = "oauth"
                    name = self._get_user_display()
                    self._tk_schedule(lambda: on_done(True, name))
                else:
                    self._tk_schedule(lambda: on_done(False, ""))
            except Exception as e:
                self._tk_schedule(lambda: on_done(False, str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _tk_schedule(self, fn):
        if self.root:
            self.root.after(0, fn)
        else:
            fn()

    def sign_in_blocking(self) -> bool:
        """Run PKCE OAuth blocking (for CLI). Returns True on success."""
        if not self.sp_oauth:
            return False
        try:
            token = self.sp_oauth.get_access_token()
            if token:
                self.client = spotipy.Spotify(auth=token["access_token"])
                self.auth_mode = "oauth"
                return True
        except Exception:
            pass
        return False

    def sign_out(self):
        token_path = CONFIG_DIR / ".spotify_token"
        if token_path.exists():
            token_path.unlink()
        self.client = None
        self.auth_mode = "none"

    def has_auth(self) -> bool:
        return self.client is not None

    def _get_user_display(self) -> str:
        if not self.client:
            return ""
        try:
            me = self.client.current_user()
            return me.get("display_name") or me.get("id") or ""
        except Exception:
            return ""

    def get_user_display(self) -> str:
        if not self.client:
            return ""
        # This might block briefly, but it's cached by spotipy
        try:
            me = self.client.current_user()
            return me.get("display_name") or me.get("id") or ""
        except Exception:
            return ""

    def search(self, query: str, types: list = None, limit: int = 20) -> list[dict]:
        if not self.client:
            return []
        if types is None:
            types = ["track", "album", "artist"]
        try:
            results = self.client.search(q=query, type=",".join(types), limit=limit)
            items = []
            if "tracks" in results:
                for t in results["tracks"]["items"]:
                    items.append({
                        "type": "track",
                        "id": t["id"],
                        "title": t["name"],
                        "artist": t["artists"][0]["name"] if t["artists"] else "",
                        "album": t["album"]["name"] if t["album"] else "",
                        "url": f"https://open.spotify.com/track/{t['id']}",
                    })
            if "albums" in results:
                for a in results["albums"]["items"]:
                    items.append({
                        "type": "album",
                        "id": a["id"],
                        "title": a["name"],
                        "artist": a["artists"][0]["name"] if a["artists"] else "",
                        "url": f"https://open.spotify.com/album/{a['id']}",
                    })
            if "artists" in results:
                for ar in results["artists"]["items"]:
                    items.append({
                        "type": "artist",
                        "id": ar["id"],
                        "title": ar["name"],
                        "url": f"https://open.spotify.com/artist/{ar['id']}",
                    })
            return items
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def resolve_url(self, url: str) -> Optional[dict]:
        parsed = parse_spotify_url(url)
        if not parsed or not self.client:
            return parsed
        try:
            if parsed["type"] == "track":
                t = self.client.track(parsed["id"])
                return {"type": "track", "id": parsed["id"],
                        "title": t["name"], "artist": t["artists"][0]["name"],
                        "url": url}
            elif parsed["type"] == "album":
                a = self.client.album(parsed["id"])
                return {"type": "album", "id": parsed["id"],
                        "title": a["name"], "artist": a["artists"][0]["name"],
                        "tracks": a["total_tracks"], "url": url}
            elif parsed["type"] == "playlist":
                p = self.client.playlist(parsed["id"])
                return {"type": "playlist", "id": parsed["id"],
                        "title": p["name"], "tracks": p["tracks"]["total"],
                        "url": url}
            elif parsed["type"] == "artist":
                ar = self.client.artist(parsed["id"])
                return {"type": "artist", "id": parsed["id"],
                        "title": ar["name"], "url": url}
            return parsed
        except Exception:
            return parsed

# ═══════════════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════════════

class Scheduler:
    def __init__(self, on_trigger):
        self.on_trigger = on_trigger
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.scheduled_time: Optional[datetime] = None
        self.watch_url: str = ""
        self.watch_interval: int = 60

    def schedule_one_time(self, dt: datetime):
        self.scheduled_time = dt
        self._stop.clear()
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def watch_playlist(self, url: str, interval_minutes: int = 60):
        self.watch_url = url
        self.watch_interval = interval_minutes
        self._stop.clear()
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_watch, daemon=True)
        self._thread.start()

    def cancel(self):
        self._stop.set()
        self.scheduled_time = None
        self.watch_url = ""

    def _run(self):
        while not self._stop.is_set() and self.scheduled_time:
            wait = (self.scheduled_time - datetime.now()).total_seconds()
            if wait <= 0:
                self.on_trigger("scheduled")
                self.scheduled_time = None
                break
            self._stop.wait(min(wait, 10))

    def _run_watch(self):
        while not self._stop.is_set() and self.watch_url:
            self.on_trigger("watch")
            self._stop.wait(self.watch_interval * 60)

# ═══════════════════════════════════════════════
# MAIN GUI
# ═══════════════════════════════════════════════

class SpotDLGUI:
    def __init__(self):
        # ── Threading / State ──
        self.queue = Queue()
        self.result_queue = Queue()
        self.tracks: list[TrackItem] = []
        self.total_tracks = 0
        self.completed_tracks = 0
        self.error_count = 0
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event()
        self.executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self.active_futures: dict[concurrent.futures.Future, str] = {}
        self.executor_thread: Optional[threading.Thread] = None
        self.log_file_path: Optional[Path] = None
        self.download_start_time: Optional[datetime] = None
        self.last_eta_update = datetime.min
        self.batch_queue: list[dict] = []
        self._downloading = False

        # ── Setup UI ──
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("1024x820")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.minsize(800, 600)

        # ── Subsystems ──
        self.spotify = SpotifyHelper(root=self.root)
        self.preset_mgr = PresetManager()
        self.scheduler = Scheduler(self._on_scheduler_trigger)
        self._was_paused = False

        self._build_ui()
        self._check_resume()
        self.root.mainloop()

    # ───────────────────────────────────────────────
    # UI BUILDING
    # ───────────────────────────────────────────────

    def _build_ui(self):
        self.config_frame = ctk.CTkFrame(self.root)
        self.download_frame = ctk.CTkFrame(self.root)

        self._build_top_bar()
        self._build_search_section()
        self._build_input_section()
        self._build_output_section()
        self._build_options_section()
        self._build_batch_section()
        self._build_action_buttons()
        self._build_progress_section()
        self._build_track_list()
        self._build_footer()
        self._build_download_ui()

        self._switch_to_config()
        self._enable_drag_drop()

    def _build_top_bar(self):
        top = ctk.CTkFrame(self.config_frame)
        top.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(top, text="Input:", font=("", 13)).pack(side="left", padx=(5, 5))
        self.input_mode_var = ctk.StringVar(value=INPUT_MODES[0])
        self.input_mode_dd = ctk.CTkComboBox(top, values=INPUT_MODES, variable=self.input_mode_var,
                                              command=self._on_input_mode_change, width=180)
        self.input_mode_dd.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(top, text="Preset:", font=("", 13)).pack(side="left", padx=(5, 5))
        self.preset_var = ctk.StringVar(value="Default")
        self.preset_dd = ctk.CTkComboBox(top, values=self.preset_mgr.get_names(),
                                          variable=self.preset_var, command=self._on_preset_select, width=180)
        self.preset_dd.pack(side="left", padx=(0, 5))
        self.save_preset_btn = ctk.CTkButton(top, text="Save", width=50, command=self._save_preset_dialog)
        self.save_preset_btn.pack(side="left", padx=2)
        self.del_preset_btn = ctk.CTkButton(top, text="Del", width=40, command=self._delete_preset)
        self.del_preset_btn.pack(side="left", padx=2)

        self.auth_btn = ctk.CTkButton(top, text="Sign in with Spotify ▸",
                                       fg_color="#1e3a5f", hover_color="#2d4f7a",
                                       command=self._show_signin_dialog)
        self.auth_btn.pack(side="right", padx=(5, 5))
        self._update_auth_button()

    def _build_input_section(self):
        self.input_frame = ctk.CTkFrame(self.config_frame)
        self.input_frame.pack(fill="x", pady=(0, 6))

        # Smart / Link input
        self.smart_frame = ctk.CTkFrame(self.input_frame)
        self.smart_label = ctk.CTkLabel(self.smart_frame, text="Paste Spotify URL:")
        self.smart_label.pack(side="left", padx=(5, 5))
        self.smart_var = ctk.StringVar()
        self.smart_entry = ctk.CTkEntry(self.smart_frame, textvariable=self.smart_var, width=500)
        self.smart_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.smart_type_label = ctk.CTkLabel(self.smart_frame, text="", text_color="gray")
        self.smart_type_label.pack(side="left", padx=5)
        self.smart_btn = ctk.CTkButton(self.smart_frame, text="Add", width=60, command=self._smart_add)
        self.smart_btn.pack(side="left", padx=5)
        self.smart_frame.pack(fill="x")

        # CSV frame
        self.csv_frame = ctk.CTkFrame(self.input_frame)
        self.csv_var = ctk.StringVar()
        csv_entry = ctk.CTkEntry(self.csv_frame, textvariable=self.csv_var, width=500)
        csv_entry.pack(side="left", padx=(5, 5), fill="x", expand=True)
        ctk.CTkButton(self.csv_frame, text="Select CSV / TXT", command=self._select_csv).pack(side="left", padx=5)
        self.csv_frame.pack_forget()

        self._on_input_mode_change()

    def _build_search_section(self):
        self.search_frame = ctk.CTkFrame(self.config_frame)
        self.search_frame.pack(fill="x", pady=(0, 6))
        self.search_frame.pack_forget()

        search_row = ctk.CTkFrame(self.search_frame)
        search_row.pack(fill="x")
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_row, textvariable=self.search_var, width=400, placeholder_text="Search tracks / albums / artists...")
        search_entry.pack(side="left", padx=(5, 5), fill="x", expand=True)
        ctk.CTkButton(search_row, text="Search", command=self._do_search, width=80).pack(side="left", padx=5)
        self.search_status_label = ctk.CTkLabel(search_row, text="")
        self.search_status_label.pack(side="left", padx=5)

        self.search_results_frame = ctk.CTkScrollableFrame(self.search_frame, height=150)
        self.search_results_frame.pack(fill="x", pady=(4, 0))
        search_btn_row = ctk.CTkFrame(self.search_frame)
        search_btn_row.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(search_btn_row, text="Add Selected to Queue", command=self._add_search_selected).pack(side="left", padx=5)
        ctk.CTkLabel(search_btn_row, text="(check boxes above)").pack(side="left", padx=5)
        self._search_checkboxes: list[tuple[tk.BooleanVar, dict]] = []

    def _build_output_section(self):
        out_frame = ctk.CTkFrame(self.config_frame)
        out_frame.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(out_frame, text="Output Folder:").pack(side="left", padx=(5, 5))
        self.dest_var = ctk.StringVar(value=str(Path.home() / "Downloads"))
        out_entry = ctk.CTkEntry(out_frame, textvariable=self.dest_var, width=400)
        out_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
        ctk.CTkButton(out_frame, text="Browse", command=self._select_out, width=70).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(out_frame, text="Subfolder:").pack(side="left", padx=(5, 5))
        self.subfolder_var = ctk.StringVar(value=DEFAULT_OUTPUT_FOLDER_NAME)
        ctk.CTkEntry(out_frame, textvariable=self.subfolder_var, width=180).pack(side="left", padx=(0, 5))

    def _build_options_section(self):
        opt_frame = ctk.CTkFrame(self.config_frame)
        opt_frame.pack(fill="x", pady=(0, 6))

        # Row 1: Format, Bitrate
        row1 = ctk.CTkFrame(opt_frame)
        row1.pack(fill="x", pady=(3, 2))

        ctk.CTkLabel(row1, text="Format:").pack(side="left", padx=(5, 3))
        self.format_var = ctk.StringVar(value="mp3")
        self.format_dd = ctk.CTkComboBox(row1, values=FORMATS, variable=self.format_var,
                                          command=self._on_format_change, width=80)
        self.format_dd.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row1, text="Bitrate:").pack(side="left", padx=(5, 3))
        self.bitrate_group_var = ctk.StringVar(value="Very High (224k-320k)")
        group_names = list(BITRATE_GROUPS.keys())
        self.bitrate_group_dd = ctk.CTkComboBox(row1, values=group_names, variable=self.bitrate_group_var,
                                                  command=self._on_bitrate_group_change, width=170)
        self.bitrate_group_dd.pack(side="left", padx=(0, 5))

        self.bitrate_fine_btn = ctk.CTkButton(row1, text="Fine tune ▾", width=80, command=self._toggle_bitrate_fine)
        self.bitrate_fine_btn.pack(side="left", padx=(0, 15))

        self.bitrate_exact_var = ctk.StringVar(value="320k")
        self.bitrate_exact_frame = ctk.CTkFrame(row1)
        ctk.CTkLabel(self.bitrate_exact_frame, text="Exact:").pack(side="left", padx=(0, 3))
        self.bitrate_exact_dd = ctk.CTkComboBox(self.bitrate_exact_frame, values=ALL_BITRATES_FLAT,
                                                  variable=self.bitrate_exact_var, width=80,
                                                  command=self._on_exact_bitrate_change)
        self.bitrate_exact_dd.pack(side="left")
        self.bitrate_exact_frame.pack_forget()

        # Size estimate label
        self.size_estimate_label = ctk.CTkLabel(row1, text="", text_color="gray")
        self.size_estimate_label.pack(side="left", padx=(10, 5))

        # Row 2: Folder, Lyrics, Concurrent, Notifications
        row2 = ctk.CTkFrame(opt_frame)
        row2.pack(fill="x", pady=(2, 3))

        ctk.CTkLabel(row2, text="Folder:").pack(side="left", padx=(5, 3))
        self.folder_struct_var = ctk.StringVar(value="By playlist")
        ctk.CTkComboBox(row2, values=FOLDER_STRUCTURES, variable=self.folder_struct_var, width=140,
                         command=self._update_size_estimate).pack(side="left", padx=(0, 15))

        self.lyrics_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, text="Lyrics", variable=self.lyrics_var, command=self._on_lyrics_toggle).pack(side="left", padx=(0, 3))
        self.lyrics_provider_var = ctk.StringVar(value="genius")
        self.lyrics_provider_dd = ctk.CTkComboBox(row2, values=LYRICS_PROVIDERS, variable=self.lyrics_provider_var, width=100)
        self.lyrics_provider_dd.pack(side="left", padx=(0, 15))
        self.lyrics_provider_dd.configure(state="disabled")

        ctk.CTkLabel(row2, text="Concurrent:").pack(side="left", padx=(5, 3))
        self.concurrent_var = ctk.IntVar(value=DEFAULT_CONCURRENT_WORKERS)
        ctk.CTkEntry(row2, textvariable=self.concurrent_var, width=50).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row2, text="Notify:").pack(side="left", padx=(5, 3))
        self.notify_var = ctk.StringVar(value="On complete only")
        ctk.CTkComboBox(row2, values=NOTIFICATION_OPTIONS, variable=self.notify_var, width=160).pack(side="left", padx=(0, 5))

        # Row 3: Delete empty, schedule
        row3 = ctk.CTkFrame(opt_frame)
        row3.pack(fill="x", pady=(2, 3))

        self.delete_empty_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row3, text="Delete empty folders", variable=self.delete_empty_var).pack(side="left", padx=(5, 20))

        ctk.CTkButton(row3, text="Schedule...", width=90, command=self._schedule_dialog).pack(side="left", padx=5)

        self.schedule_status_label = ctk.CTkLabel(row3, text="", text_color="gray")
        self.schedule_status_label.pack(side="left", padx=5)

    def _build_batch_section(self):
        self.batch_frame = ctk.CTkFrame(self.config_frame)
        self.batch_frame.pack(fill="x", pady=(0, 6))

        header = ctk.CTkFrame(self.batch_frame)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Batch Queue", font=("", 13, "bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="URL:").pack(side="left", padx=(20, 3))
        self.batch_url_var = ctk.StringVar()
        ctk.CTkEntry(header, textvariable=self.batch_url_var, width=350).pack(side="left", padx=(0, 3), fill="x", expand=True)
        ctk.CTkButton(header, text="Add to Queue", command=self._batch_add, width=100).pack(side="left", padx=5)
        self.batch_mode_var = ctk.StringVar(value="Sequential")
        ctk.CTkComboBox(header, values=["Sequential", "Parallel"], variable=self.batch_mode_var, width=110).pack(side="left", padx=5)
        ctk.CTkButton(header, text="Clear All", command=self._batch_clear, width=70).pack(side="left", padx=5)

        self.batch_list_frame = ctk.CTkScrollableFrame(self.batch_frame, height=60)
        self.batch_list_frame.pack(fill="x", pady=(3, 3))
        self._batch_widgets: list[ctk.CTkFrame] = []
        self._refresh_batch_list()

    def _build_action_buttons(self):
        btn_frame = ctk.CTkFrame(self.config_frame)
        btn_frame.pack(fill="x", pady=(6, 6))

        self.start_btn = ctk.CTkButton(btn_frame, text="▶  Start Download", command=self._start_downloads, width=140)
        self.start_btn.pack(side="left", padx=(5, 5))

        self.pause_btn = ctk.CTkButton(btn_frame, text="⏸  Pause", command=self._toggle_pause, width=90, state="disabled")
        self.pause_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹  Stop", command=self._stop_downloads, width=90, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        ctk.CTkButton(btn_frame, text="Export .sh", command=self._export_sh, width=90).pack(side="left", padx=(20, 5))

        if HAS_TRAY:
            self.tray_btn = ctk.CTkButton(btn_frame, text="Minimize to Tray", command=self._minimize_to_tray, width=120)
            self.tray_btn.pack(side="right", padx=5)

    def _build_progress_section(self):
        prog_frame = ctk.CTkFrame(self.config_frame)
        prog_frame.pack(fill="x", pady=(0, 6))

        self.progress_var = ctk.DoubleVar()
        self.progressbar = ctk.CTkProgressBar(prog_frame, variable=self.progress_var)
        self.progressbar.pack(fill="x", padx=10, pady=(5, 2))
        self.progressbar.set(0)

        info_row = ctk.CTkFrame(prog_frame)
        info_row.pack(fill="x", padx=10, pady=(0, 2))

        self.progress_label = ctk.CTkLabel(info_row, text="0 / 0 (0%)", width=150)
        self.progress_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(info_row, text="ETA: Ready", width=150)
        self.eta_label.pack(side="left", padx=(20, 0))

        self.size_label = ctk.CTkLabel(info_row, text="Est. size: —", text_color="gray", width=350)
        self.size_label.pack(side="left", padx=(20, 0))

        self.current_track_label = ctk.CTkLabel(prog_frame, text="Current: —")
        self.current_track_label.pack(anchor="w", padx=10)

        self.status_label = ctk.CTkLabel(prog_frame, text="Status: Ready")
        self.status_label.pack(anchor="w", padx=10)

    def _build_track_list(self):
        tl_frame = ctk.CTkFrame(self.config_frame)
        tl_frame.pack(fill="both", expand=True, pady=(0, 6))

        header = ctk.CTkFrame(tl_frame)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Track Queue", font=("", 13, "bold")).pack(side="left", padx=5)
        self.track_count_label = ctk.CTkLabel(header, text="(0 tracks)")
        self.track_count_label.pack(side="left", padx=5)

        self.track_list_frame = ctk.CTkScrollableFrame(tl_frame, height=120)
        self.track_list_frame.pack(fill="x", pady=(3, 3))
        self._track_widgets: dict[str, ctk.CTkFrame] = {}

    def _build_footer(self):
        foot = ctk.CTkFrame(self.config_frame)
        foot.pack(fill="x", pady=(4, 0))
        lbl1 = ctk.CTkLabel(foot, text="minxie.likesyou.org", text_color="cyan", cursor="hand2")
        lbl1.pack(side="left", padx=5)
        lbl1.bind("<Button-1>", lambda e: webbrowser.open("https://minxie.likesyou.org"))
        lbl2 = ctk.CTkLabel(foot, text="GitHub project", text_color="cyan", cursor="hand2")
        lbl2.pack(side="left", padx=5)
        lbl2.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Minxify/Spotify-downloader-GUI"))
        ctk.CTkLabel(foot, text=f"v{VERSION}", text_color="gray").pack(side="right", padx=5)

    # ───────────────────────────────────────────────
    # DOWNLOAD VIEW (simplified, shown during download)
    # ───────────────────────────────────────────────

    def _build_download_ui(self):
        """Build the minimal download-progress view (settings hidden)."""
        header = ctk.CTkFrame(self.download_frame)
        header.pack(fill="x", pady=(8, 4))

        ctk.CTkLabel(header, text="Download Progress", font=("", 16, "bold")).pack(side="left", padx=10)

        prog_frame = ctk.CTkFrame(self.download_frame)
        prog_frame.pack(fill="x", padx=10, pady=(0, 6))

        self.dl_progressbar = ctk.CTkProgressBar(prog_frame)
        self.dl_progressbar.pack(fill="x", pady=(5, 2))
        self.dl_progressbar.set(0)

        info_row = ctk.CTkFrame(prog_frame)
        info_row.pack(fill="x", pady=(0, 2))

        self.dl_progress_label = ctk.CTkLabel(info_row, text="0 / 0 (0%)", width=150)
        self.dl_progress_label.pack(side="left")

        self.dl_eta_label = ctk.CTkLabel(info_row, text="ETA: --", width=150)
        self.dl_eta_label.pack(side="left", padx=(20, 0))

        self.dl_size_label = ctk.CTkLabel(info_row, text="", text_color="gray", width=350)
        self.dl_size_label.pack(side="left", padx=(20, 0))

        self.dl_errors_label = ctk.CTkLabel(info_row, text="", text_color="#ff6666", width=120)
        self.dl_errors_label.pack(side="right", padx=5)

        self.dl_current_track_label = ctk.CTkLabel(prog_frame, text="Current: --", font=("", 13))
        self.dl_current_track_label.pack(anchor="w", padx=5, pady=(2, 0))

        self.dl_status_label = ctk.CTkLabel(prog_frame, text="Status: --")
        self.dl_status_label.pack(anchor="w", padx=5)

        # Culled track queue — only current + next 5
        tl_frame = ctk.CTkFrame(self.download_frame)
        tl_frame.pack(fill="both", expand=True, pady=(6, 6))

        ctk.CTkLabel(tl_frame, text="Track Queue", font=("", 13, "bold")).pack(anchor="w", padx=5, pady=(3, 0))

        self.dl_track_list_frame = ctk.CTkScrollableFrame(tl_frame, height=180)
        self.dl_track_list_frame.pack(fill="x", pady=(3, 3))
        self.dl_track_widgets: dict[str, ctk.CTkFrame] = {}
        self.dl_more_label = ctk.CTkLabel(tl_frame, text="", text_color="gray")
        self.dl_more_label.pack(anchor="w", padx=5)

        # Buttons
        btn_frame = ctk.CTkFrame(self.download_frame)
        btn_frame.pack(fill="x", pady=(6, 8))

        self.dl_pause_btn = ctk.CTkButton(btn_frame, text="⏸  Pause", command=self._toggle_pause, width=90, state="disabled")
        self.dl_pause_btn.pack(side="left", padx=(10, 5))

        self.dl_stop_btn = ctk.CTkButton(btn_frame, text="⏹  Stop", command=self._stop_downloads, width=90, state="disabled")
        self.dl_stop_btn.pack(side="left", padx=5)

        self.dl_back_btn = ctk.CTkButton(btn_frame, text="✕ Back to Settings", command=self._back_to_config, width=120)
        self.dl_back_btn.pack(side="right", padx=10)
        self.dl_back_btn.pack_forget()  # hidden until download finishes

        if HAS_TRAY:
            self.dl_tray_btn = ctk.CTkButton(btn_frame, text="Minimize to Tray", command=self._minimize_to_tray, width=120)
            self.dl_tray_btn.pack(side="right", padx=5)

    def _switch_to_config(self):
        self.download_frame.pack_forget()
        self.config_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._current_view = "config"

    def _switch_to_download(self):
        self.config_frame.pack_forget()
        self.download_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._current_view = "download"

    def _back_to_config(self):
        self.dl_back_btn.pack_forget()
        self._switch_to_config()

    # ───────────────────────────────────────────────
    # INPUT MODE HANDLING
    # ───────────────────────────────────────────────

    def _on_input_mode_change(self, value=None):
        mode = self.input_mode_var.get()
        self.smart_frame.pack_forget()
        self.csv_frame.pack_forget()
        self.search_frame.pack_forget()

        if mode == "Smart (auto-detect)" or mode == "Spotify Link":
            self.smart_frame.pack(fill="x")
            self.smart_label.configure(text="Paste Spotify URL:" if mode == "Spotify Link" else "Paste any Spotify URL (auto-detects):")
            self.smart_btn.configure(text="Add")
            if mode == "Smart (auto-detect)":
                self.smart_entry.bind("<KeyRelease>", self._on_smart_typing, add="+")
        elif mode == "Search":
            self.search_frame.pack(fill="x")
        elif mode == "CSV / TXT":
            self.csv_frame.pack(fill="x")

    def _on_smart_typing(self, event=None):
        url = self.smart_var.get().strip()
        parsed = parse_spotify_url(url)
        if parsed:
            type_names = {"track": "Track", "album": "Album", "playlist": "Playlist",
                          "artist": "Artist", "episode": "Episode", "show": "Podcast"}
            label = type_names.get(parsed["type"], "Link")
            self.smart_type_label.configure(text=f"({label})", text_color="#4ade80")
        else:
            self.smart_type_label.configure(text="")

    def _smart_add(self):
        url = self.smart_var.get().strip()
        if not url:
            return
        parsed = parse_spotify_url(url)
        if not parsed and self.input_mode_var.get() == "Spotify Link":
            messagebox.showerror("Error", "Not a valid Spotify URL")
            return
        if parsed:
            if self.input_mode_var.get() == "Smart (auto-detect)":
                if parsed["type"] == "track":
                    self.tracks.append(TrackItem(
                        query=url, title=url, status="pending", spotify_id=parsed["id"]
                    ))
                elif parsed["type"] in ("album", "playlist", "artist"):
                    self.batch_queue.append({"url": url, "type": parsed["type"]})
                    self._refresh_batch_list()
                    self.smart_var.set("")
                    return
            else:
                self.tracks.append(TrackItem(query=url, title=url, status="pending"))
        else:
            self.tracks.append(TrackItem(query=url, title=url, status="pending"))
        self._refresh_track_list()
        self.smart_var.set("")
        self.smart_type_label.configure(text="")

    # ───────────────────────────────────────────────
    # SEARCH
    # ───────────────────────────────────────────────

    def _do_search(self):
        query = self.search_var.get().strip()
        if not query:
            return
        if not self.spotify.has_auth():
            if messagebox.askyesno("Search Unavailable",
                                    "Search requires signing in with Spotify.\n\n"
                                    "Sign in now?"):
                self._show_signin_dialog()
            return

        self.search_status_label.configure(text="Searching...")
        self.search_var.set("")
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query: str):
        results = self.spotify.search(query)
        self.root.after(0, lambda: self._display_search_results(results))

    def _display_search_results(self, results: list):
        self.search_status_label.configure(text=f"Found {len(results)} results")

        for w in self.search_results_frame.winfo_children():
            w.destroy()
        self._search_checkboxes = []

        if not results:
            ctk.CTkLabel(self.search_results_frame, text="No results found.", text_color="gray").pack()
            return

        for item in results:
            row = ctk.CTkFrame(self.search_results_frame)
            row.pack(fill="x", pady=1)
            var = tk.BooleanVar()
            type_icon = {"track": "🎵", "album": "💿", "artist": "👤"}.get(item["type"], "•")
            label_text = f"{type_icon} {item['title']}"
            if item.get("artist"):
                label_text += f" — {item['artist']}"
            if item.get("album"):
                label_text += f"  [{item['album']}]"
            cb = ctk.CTkCheckBox(row, text=label_text, variable=var, checkbox_width=18)
            cb.pack(side="left", padx=5, fill="x", expand=True)
            self._search_checkboxes.append((var, item))

    def _add_search_selected(self):
        added = 0
        for var, item in self._search_checkboxes:
            if var.get():
                if item["type"] == "track":
                    self.tracks.append(TrackItem(
                        title=item["title"],
                        artist=item.get("artist", ""),
                        query=item["url"],
                        spotify_id=item["id"],
                        status="pending"
                    ))
                    added += 1
                elif item["type"] in ("album", "artist"):
                    self.batch_queue.append({"url": item["url"], "type": item["type"],
                                              "title": item["title"]})
        if added > 0:
            self._refresh_track_list()
        self._refresh_batch_list()

    # ───────────────────────────────────────────────
    # CSV / OUTPUT SELECTION
    # ───────────────────────────────────────────────

    def _select_csv(self):
        start_dir = str(Path.home() / "Desktop") if os.name == "nt" else str(Path.home())
        path = filedialog.askopenfilename(initialdir=start_dir, filetypes=[("CSV/TXT Files", "*.csv *.txt")])
        if path:
            self.csv_var.set(path)

    def _select_out(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_var.set(path)

    # ───────────────────────────────────────────────
    # FORMAT / BITRATE
    # ───────────────────────────────────────────────

    def _on_format_change(self, value=None):
        fmt = self.format_var.get()
        if fmt in ("flac", "wav"):
            self.bitrate_group_dd.configure(state="disabled")
            self.bitrate_exact_frame.pack_forget()
            self.bitrate_fine_btn.configure(text="Lossless")
            self.bitrate_group_var.set("Lossless")
            self.bitrate_exact_var.set("lossless")
        else:
            self.bitrate_group_dd.configure(state="normal")
            self.bitrate_fine_btn.configure(text="Fine tune ▾")
            self.bitrate_group_var.set("Very High (224k-320k)")
            self.bitrate_exact_var.set("320k")
        self._update_size_estimate()

    def _on_bitrate_group_change(self, value=None):
        group = self.bitrate_group_var.get()
        brs = BITRATE_GROUPS.get(group)
        if brs is None:
            self.bitrate_exact_var.set("lossless")
            self.bitrate_exact_frame.pack_forget()
            if self.format_var.get() not in ("flac", "wav"):
                self.format_var.set("flac")
                self._on_format_change()
        else:
            last = brs[-1]
            self.bitrate_exact_var.set(last)
            self.bitrate_exact_dd.configure(values=brs)
        self._update_size_estimate()

    def _toggle_bitrate_fine(self):
        if self.format_var.get() in ("flac", "wav"):
            return
        if self.bitrate_exact_frame.winfo_viewable():
            self.bitrate_exact_frame.pack_forget()
        else:
            self.bitrate_exact_frame.pack(side="left", padx=(0, 15))

    def _on_exact_bitrate_change(self, value=None):
        self._update_size_estimate()

    def _on_lyrics_toggle(self):
        state = "normal" if self.lyrics_var.get() else "disabled"
        self.lyrics_provider_dd.configure(state=state)

    # ───────────────────────────────────────────────
    # SIZE ESTIMATION
    # ───────────────────────────────────────────────

    def _update_size_estimate(self, *args):
        fmt = self.format_var.get()
        br = self.bitrate_exact_var.get()
        if fmt in ("flac", "wav"):
            br_str = None
        else:
            br_str = br

        per_track = estimate_size_mb(fmt, br_str, REF_DURATION_SEC)
        n = len(self.tracks)
        total = per_track * n if n > 0 else 0

        text = f"Est. size: ~{per_track:.1f}MB/track" + (f" · ~{total:.0f}MB total" if n > 0 else "")
        self.size_label.configure(text=text)
        self.size_estimate_label.configure(text=f"~{per_track:.1f}MB/3min")
        if hasattr(self, 'dl_size_label'):
            self.dl_size_label.configure(text=text)

    # ───────────────────────────────────────────────
    # TRACK LIST
    # ───────────────────────────────────────────────

    def _refresh_track_list(self):
        status_icons = {"pending": "⬜", "downloading": "▶", "completed": "✅",
                        "failed": "❌", "cancelled": "⏹"}

        # Track which UIDs we still have
        seen = set()
        track_map = {t.uid: t for t in self.tracks}

        # Remove widgets for tracks no longer in the list
        for uid in list(self._track_widgets.keys()):
            if uid not in track_map:
                self._track_widgets[uid].destroy()
                del self._track_widgets[uid]

        # Update or create widgets
        for t in self.tracks:
            seen.add(t.uid)
            if t.uid in self._track_widgets:
                row = self._track_widgets[t.uid]
                # Update existing label text
                children = row.winfo_children()
                if children:
                    lbl = children[0]
                    icon = status_icons.get(t.status, "⬜")
                    label = f"{icon} {t.title}"
                    if t.artist:
                        label += f" — {t.artist}"
                    lbl.configure(text=label)
            else:
                row = ctk.CTkFrame(self.track_list_frame)
                row.pack(fill="x", pady=1)
                icon = status_icons.get(t.status, "⬜")
                label = f"{icon} {t.title}"
                if t.artist:
                    label += f" — {t.artist}"
                ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=5, fill="x", expand=True)

                if t.status in ("pending", "downloading"):
                    ctk.CTkButton(row, text="×", width=28, fg_color="#aa3333", hover_color="#cc4444",
                                   command=lambda uid=t.uid: self._cancel_track(uid)).pack(side="right", padx=2)

                self._track_widgets[t.uid] = row

            # Update cancel button visibility
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton) and child.cget("text") == "×":
                    if t.status in ("pending", "downloading"):
                        child.pack(side="right", padx=2)
                    else:
                        child.pack_forget()

        self.track_count_label.configure(text=f"({len(self.tracks)} tracks)")
        self.root.after(10, self._update_size_estimate)

    def _cancel_track(self, uid: str):
        for t in self.tracks:
            if t.uid == uid and t.status in ("pending", "downloading"):
                t.status = "cancelled"
                break
        self._refresh_track_list()
        self._refresh_download_view()

    # ── Download-view track list (culled: current + next 5) ──

    def _refresh_download_view(self):
        status_icons = {"pending": "⬜", "downloading": "▶", "completed": "✅",
                        "failed": "❌", "cancelled": "⏹"}

        downloading = [t for t in self.tracks if t.status == "downloading"]
        pending = [t for t in self.tracks if t.status == "pending"]
        visible = downloading + pending[:5]
        remaining = max(0, len(pending) - 5)
        track_map = {t.uid: t for t in visible}

        for uid in list(self.dl_track_widgets.keys()):
            if uid not in track_map:
                self.dl_track_widgets[uid].destroy()
                del self.dl_track_widgets[uid]

        for t in visible:
            if t.uid in self.dl_track_widgets:
                row = self.dl_track_widgets[t.uid]
                children = row.winfo_children()
                if children:
                    lbl = children[0]
                    icon = status_icons.get(t.status, "⬜")
                    label = f"{icon} {t.title}"
                    if t.artist:
                        label += f" — {t.artist}"
                    lbl.configure(text=label)
            else:
                row = ctk.CTkFrame(self.dl_track_list_frame)
                row.pack(fill="x", pady=1)
                icon = status_icons.get(t.status, "⬜")
                label = f"{icon} {t.title}"
                if t.artist:
                    label += f" — {t.artist}"
                ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=5, fill="x", expand=True)
                if t.status in ("pending", "downloading"):
                    ctk.CTkButton(row, text="×", width=28, fg_color="#aa3333", hover_color="#cc4444",
                                   command=lambda uid=t.uid: self._cancel_track(uid)).pack(side="right", padx=2)
                self.dl_track_widgets[t.uid] = row

            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton) and child.cget("text") == "×":
                    if t.status in ("pending", "downloading"):
                        child.pack(side="right", padx=2)
                    else:
                        child.pack_forget()

        self.dl_more_label.configure(
            text=f"+ {remaining} more pending" if remaining > 0 else ""
        )

    # ───────────────────────────────────────────────
    # BATCH QUEUE
    # ───────────────────────────────────────────────

    def _batch_add(self):
        url = self.batch_url_var.get().strip()
        if not url:
            return
        parsed = parse_spotify_url(url)
        if not parsed:
            messagebox.showerror("Error", "Not a valid Spotify URL")
            return
        self.batch_queue.append({"url": url, "type": parsed["type"]})
        self.batch_url_var.set("")
        self._refresh_batch_list()

    def _batch_clear(self):
        self.batch_queue.clear()
        self._refresh_batch_list()

    def _refresh_batch_list(self):
        for w in self._batch_widgets:
            w.destroy()
        self._batch_widgets.clear()

        for i, entry in enumerate(self.batch_queue):
            row = ctk.CTkFrame(self.batch_list_frame)
            row.pack(fill="x", pady=1)
            title = entry.get("title", entry["url"])
            ctk.CTkLabel(row, text=f"{entry['type']}: {title}", anchor="w").pack(side="left", padx=5, fill="x", expand=True)
            ctk.CTkButton(row, text="×", width=28, fg_color="#aa3333", hover_color="#cc4444",
                           command=lambda idx=i: self._batch_remove(idx)).pack(side="right", padx=2)
            self._batch_widgets.append(row)

    def _batch_remove(self, idx: int):
        if 0 <= idx < len(self.batch_queue):
            self.batch_queue.pop(idx)
            self._refresh_batch_list()

    # ───────────────────────────────────────────────
    # DRAG & DROP
    # ───────────────────────────────────────────────

    def _enable_drag_drop(self):
        try:
            self.root.tk.eval('''
                proc ::tk::dnd::drag {W X Y} {}
                proc ::tk::dnd::drop {W X Y} {}
            ''')
            self.root.tk.createcommand("::tk::dnd::drag", self._on_drag)
            self.root.tk.createcommand("::tk::dnd::drop", self._on_drop)
        except Exception:
            pass

    def _on_drag(self, *args):
        pass

    def _on_drop(self, path, *args):
        path = path.strip("{}")
        if os.path.isfile(path) and path.lower().endswith((".csv", ".txt")):
            self.csv_var.set(path)
            self.input_mode_var.set("CSV / TXT")
            self._on_input_mode_change()
        elif parse_spotify_url(path):
            self.smart_var.set(path)
            self.input_mode_var.set("Smart (auto-detect)")
            self._on_input_mode_change()

    # ───────────────────────────────────────────────
    # PRESETS
    # ───────────────────────────────────────────────

    def _save_preset_dialog(self):
        dialog = ctk.CTkInputDialog(text="Preset name:", title="Save Preset")
        name = dialog.get_input()
        if not name:
            return
        preset = Preset(
            name=name,
            output_folder=self.dest_var.get(),
            subfolder=self.subfolder_var.get(),
            format_=self.format_var.get(),
            bitrate=self.bitrate_exact_var.get(),
            concurrent=self.concurrent_var.get(),
            delete_empty=self.delete_empty_var.get(),
            folder_structure=self.folder_struct_var.get(),
            lyrics=self.lyrics_var.get(),
            lyrics_provider=self.lyrics_provider_var.get(),
            notifications=self.notify_var.get(),
            input_mode=self.input_mode_var.get(),
        )
        self.preset_mgr.save(preset)
        self.preset_dd.configure(values=self.preset_mgr.get_names())
        self.preset_var.set(name)

    def _delete_preset(self):
        name = self.preset_var.get()
        if name == "Default":
            messagebox.showinfo("Info", "Cannot delete the Default preset.")
            return
        if messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?"):
            self.preset_mgr.delete(name)
            self.preset_dd.configure(values=self.preset_mgr.get_names())
            self.preset_var.set("Default")

    def _on_preset_select(self, value=None):
        name = self.preset_var.get()
        preset = self.preset_mgr.get(name)
        if not preset:
            return
        if preset.output_folder:
            self.dest_var.set(preset.output_folder)
        self.subfolder_var.set(preset.subfolder)
        if preset.format_ in FORMATS:
            self.format_var.set(preset.format_)
        self.bitrate_exact_var.set(preset.bitrate)
        self.concurrent_var.set(preset.concurrent)
        self.delete_empty_var.set(preset.delete_empty)
        if preset.folder_structure in FOLDER_STRUCTURES:
            self.folder_struct_var.set(preset.folder_structure)
        self.lyrics_var.set(preset.lyrics)
        self._on_lyrics_toggle()
        if preset.lyrics_provider in LYRICS_PROVIDERS:
            self.lyrics_provider_var.set(preset.lyrics_provider)
        if preset.notifications in NOTIFICATION_OPTIONS:
            self.notify_var.set(preset.notifications)
        if preset.input_mode in INPUT_MODES:
            self.input_mode_var.set(preset.input_mode)
            self._on_input_mode_change()
        self._update_size_estimate()

    # ───────────────────────────────────────────────
    # SCHEDULER
    # ───────────────────────────────────────────────

    def _schedule_dialog(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Schedule Downloads")
        win.geometry("400x300")
        win.resizable(False, False)

        ctk.CTkLabel(win, text="One-Time Schedule", font=("", 14, "bold")).pack(pady=(10, 5))
        tf = ctk.CTkFrame(win)
        tf.pack(pady=5)
        ctk.CTkLabel(tf, text="Time (HH:MM):").pack(side="left", padx=5)
        self.sched_time_var = ctk.StringVar()
        ctk.CTkEntry(tf, textvariable=self.sched_time_var, width=80).pack(side="left", padx=5)
        ctk.CTkLabel(tf, text="  Date (YYYY-MM-DD):").pack(side="left", padx=5)
        self.sched_date_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ctk.CTkEntry(tf, textvariable=self.sched_date_var, width=100).pack(side="left", padx=5)

        ctk.CTkButton(win, text="Set Schedule", command=self._apply_schedule).pack(pady=5)

        ctk.CTkLabel(win, text="Playlist Watcher", font=("", 14, "bold")).pack(pady=(15, 5))
        wf = ctk.CTkFrame(win)
        wf.pack(pady=5)
        ctk.CTkLabel(wf, text="Playlist URL:").pack(side="left", padx=5)
        self.watch_url_var = ctk.StringVar()
        ctk.CTkEntry(wf, textvariable=self.watch_url_var, width=250).pack(side="left", padx=5)

        ctk.CTkButton(win, text="Watch Playlist", command=self._apply_watch).pack(pady=5)
        ctk.CTkButton(win, text="Cancel Schedule/Watch", fg_color="#aa3333", command=self._cancel_schedule).pack(pady=5)

    def _apply_schedule(self):
        try:
            dt_str = f"{self.sched_date_var.get()} {self.sched_time_var.get()}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if dt < datetime.now():
                messagebox.showerror("Error", "Time is in the past")
                return
            self.scheduler.schedule_one_time(dt)
            self.schedule_status_label.configure(text=f"Scheduled at {dt.strftime('%H:%M')}", text_color="#4ade80")
        except ValueError:
            messagebox.showerror("Error", "Invalid date/time format")

    def _apply_watch(self):
        url = self.watch_url_var.get().strip()
        if not parse_spotify_url(url):
            messagebox.showerror("Error", "Invalid Spotify playlist URL")
            return
        self.scheduler.watch_playlist(url)
        self.schedule_status_label.configure(text="Watching playlist...", text_color="#4ade80")

    def _cancel_schedule(self):
        self.scheduler.cancel()
        self.schedule_status_label.configure(text="", text_color="gray")

    def _on_scheduler_trigger(self, trigger_type: str):
        self.root.after(0, lambda: self.status_label.configure(text=f"Status: Triggered by {trigger_type}"))
        if not self._downloading:
            self.root.after(100, self._start_downloads)

    # ───────────────────────────────────────────────
    # SPOTIFY OAUTH
    # ───────────────────────────────────────────────

    def _show_signin_dialog(self):
        """Two-step dialog: link Spotify account → sign in with browser."""
        if self.spotify.has_auth():
            name = self.spotify.get_user_display()
            if messagebox.askyesno("Signed In",
                                    f"Already signed in as {name}.\n\nSign out?"):
                self.spotify.sign_out()
                self._update_auth_button()
            return

        if not self.spotify.client_id:
            self._show_setup_wizard()
        else:
            self._do_oauth_signin()

    def _show_setup_wizard(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Link your Spotify Account")
        win.geometry("580x400")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(win, text="Link Spotify Account", font=("", 16, "bold")).pack(pady=(12, 5))
        ctk.CTkLabel(win, text="This lets the app search Spotify and access your playlists.",
                      wraplength=500, justify="center").pack(pady=(0, 10))

        # Step 1
        step1 = ctk.CTkFrame(win)
        step1.pack(fill="x", padx=25, pady=5)
        ctk.CTkLabel(step1, text="Step 1: Create a Spotify App", font=("", 13, "bold")).pack(anchor="w")
        ctk.CTkLabel(step1,
                      text="1. Go to developer.spotify.com/dashboard and click \"Create App\"\n"
                           "2. Enter any name and description\n"
                           "3. Set the Redirect URI to: http://localhost:8888/callback\n"
                           "4. Check \"Web API\" and click \"Save\"\n"
                           "5. Copy the Client ID from the app page",
                      justify="left", wraplength=500).pack(anchor="w", padx=10, pady=3)

        btn_row = ctk.CTkFrame(step1)
        btn_row.pack(pady=5)
        ctk.CTkButton(btn_row, text="Open Spotify Developer Dashboard",
                       command=lambda: webbrowser.open("https://developer.spotify.com/dashboard")).pack(side="left", padx=5)

        # Step 2: Enter Client ID
        step2 = ctk.CTkFrame(win)
        step2.pack(fill="x", padx=25, pady=10)
        ctk.CTkLabel(step2, text="Step 2: Enter Client ID", font=("", 13, "bold")).pack(anchor="w")
        ctk.CTkLabel(step2, text="Paste the Client ID from your Spotify App:", wraplength=500).pack(anchor="w", padx=10, pady=3)

        cid_frame = ctk.CTkFrame(step2)
        cid_frame.pack(fill="x", padx=10, pady=5)
        self.setup_cid_var = ctk.StringVar()
        ctk.CTkEntry(cid_frame, textvariable=self.setup_cid_var, width=400).pack(side="left", padx=(0, 10), fill="x", expand=True)

        def on_save():
            cid = self.setup_cid_var.get().strip()
            if not cid:
                messagebox.showerror("Error", "Please enter a Client ID")
                return
            self.spotify.save_client_id(cid)
            if self.spotify.sp_oauth:
                win.destroy()
                self._do_oauth_signin()
            else:
                messagebox.showerror("Error", "Invalid Client ID. Make sure the Spotify App exists.")

        ctk.CTkButton(cid_frame, text="Save & Sign In", command=on_save).pack(side="right")

    def _do_oauth_signin(self):
        """Opens browser for Spotify authorization."""
        win = ctk.CTkToplevel(self.root)
        win.title("Signing in...")
        win.geometry("400x150")
        win.transient(self.root)
        win.resizable(False, False)

        ctk.CTkLabel(win, text="Sign in with Spotify", font=("", 15, "bold")).pack(pady=(20, 10))
        status_lbl = ctk.CTkLabel(win, text="Opening browser for authorization...")
        status_lbl.pack(pady=5)
        ctk.CTkLabel(win, text="If the browser doesn't open, check your default browser settings.",
                      wraplength=350, text_color="gray").pack(pady=5)
        ctk.CTkButton(win, text="Cancel", command=win.destroy).pack(pady=10)

        def on_oauth_done(success, info):
            try:
                win.destroy()
            except Exception:
                pass
            if success:
                self._update_auth_button()
                messagebox.showinfo("Signed In", f"Signed in as {info}!")
            else:
                if info:
                    messagebox.showerror("Sign In Failed", f"Could not sign in: {info}")
                else:
                    messagebox.showerror("Sign In Failed", "Authorization was cancelled or failed.")

        self.spotify.sign_in(on_oauth_done)

    def _update_auth_button(self):
        if hasattr(self, 'auth_btn'):
            if self.spotify.has_auth():
                name = self.spotify.get_user_display() or "Spotify"
                self.auth_btn.configure(text=f"✓ {name}", fg_color="#2d6a4f", hover_color="#40916c")
            else:
                self.auth_btn.configure(text="Sign in with Spotify ▸", fg_color="#1e3a5f", hover_color="#2d4f7a")

    # ───────────────────────────────────────────────
    # DOWNLOAD LIFECYCLE
    # ───────────────────────────────────────────────

    def _start_downloads(self):
        workers = self.concurrent_var.get()
        if workers <= 0:
            workers = DEFAULT_CONCURRENT_WORKERS

        self._downloading = True
        self.error_count = 0
        self.completed_tracks = 0
        self.stop_flag.clear()
        self.pause_flag.clear()
        self._was_paused = False

        # Build track list if empty
        if not self.tracks:
            input_mode = self.input_mode_var.get()
            if input_mode == "CSV / TXT":
                path = self.csv_var.get()
                if not os.path.exists(path):
                    messagebox.showerror("Error", "Invalid CSV/TXT path")
                    self._downloading = False
                    return
                self._load_csv(path)
            elif input_mode == "Spotify Link":
                url = self.smart_var.get().strip()
                if not url:
                    messagebox.showerror("Error", "Enter a Spotify URL")
                    self._downloading = False
                    return
                self.tracks.append(TrackItem(query=url, title=url, status="pending"))
            elif input_mode == "Smart (auto-detect)":
                url = self.smart_var.get().strip()
                if url:
                    parsed = parse_spotify_url(url)
                    if parsed and parsed["type"] == "track":
                        self.tracks.append(TrackItem(query=url, title=url, status="pending"))
                    elif parsed:
                        self.batch_queue.append({"url": url, "type": parsed["type"]})
                        self._refresh_batch_list()
                    self.smart_var.set("")

        # Add batch items
        if self.batch_queue:
            for entry in self.batch_queue:
                self.tracks.append(TrackItem(query=entry["url"], title=entry["url"], status="pending"))

        if not self.tracks:
            messagebox.showinfo("Info", "No tracks to download.")
            self._downloading = False
            return

        # Reset status of pending/cancelled tracks
        for t in self.tracks:
            if t.status in ("pending", "cancelled", "failed"):
                t.status = "pending"
                t.error = ""

        self.total_tracks = len(self.tracks)
        self._refresh_track_list()

        self.progress_var.set(0)
        self.progress_label.configure(text=f"0 / {self.total_tracks} (0%)")

        notify_mode = self.notify_var.get()
        if notify_mode == "Every track + done" and self.total_tracks > 10:
            if not messagebox.askyesno("Large Playlist Warning",
                                       f"You selected 'Every track + done' notifications for {self.total_tracks} tracks.\n"
                                       "This may overwhelm your system with notifications.\n\nContinue anyway?"):
                self.notify_var.set("On complete + on error")

        self.download_start_time = datetime.now()
        self.last_eta_update = datetime.now()

        # Switch to download view
        self._switch_to_download()

        # Init download view widgets
        self.dl_progressbar.set(0)
        self.dl_progress_label.configure(text=f"0 / {self.total_tracks} (0%)")
        self.dl_eta_label.configure(text="ETA: Calculating...")
        self.dl_current_track_label.configure(text="Current: Starting...")
        self.dl_status_label.configure(text=f"Status: Initializing {workers} workers.")
        self.dl_errors_label.configure(text="")
        self.dl_size_label.configure(text="")
        self._refresh_download_view()
        self.dl_back_btn.pack_forget()

        self._update_size_estimate()

        # Start download thread
        self.executor_thread = threading.Thread(target=self._download_coordinator, args=(workers,))
        self.executor_thread.start()

        self.root.after(200, self._check_download_status)

        self.start_btn.configure(state="disabled", text="▶  Start")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.dl_pause_btn.configure(state="normal", text="⏸  Pause")
        self.dl_stop_btn.configure(state="normal")

    def _stop_downloads(self):
        self.stop_flag.set()
        self.dl_status_label.configure(text="Status: Stopping...")
        self.dl_eta_label.configure(text="ETA: Stopping...")
        self.dl_pause_btn.configure(state="disabled")
        self.dl_stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")

    def _toggle_pause(self):
        if self.pause_flag.is_set():
            self.pause_flag.clear()
            self.pause_btn.configure(text="⏸  Pause")
            self.dl_pause_btn.configure(text="⏸  Pause")
            self.dl_status_label.configure(text="Status: Resuming...")
            self._was_paused = True
        else:
            self.pause_flag.set()
            self.pause_btn.configure(text="▶  Resume")
            self.dl_pause_btn.configure(text="▶  Resume")
            self.dl_status_label.configure(text="Status: Paused")

    def _load_csv(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            try:
                first_lines = "".join(f.readline() for _ in range(5))
                f.seek(0)
                has_header = 'Track name' in first_lines or 'track name' in first_lines or 'Track Name' in first_lines
            except Exception:
                f.seek(0)
                has_header = False

            if has_header:
                reader = csv.DictReader(f)
                for row in reader:
                    t = TrackItem(
                        title=row.get("Track name") or row.get("track name") or row.get("Track Name") or "",
                        artist=row.get("Artist name") or row.get("artist name") or "",
                        playlist=row.get("Playlist name") or row.get("playlist name") or "Default",
                        spotify_id=row.get("Spotify - id") or row.get("spotify - id") or "",
                        status="pending"
                    )
                    tid = t.spotify_id
                    if tid:
                        t.query = f"https://open.spotify.com/track/{tid}"
                    elif t.title:
                        t.query = f"{t.artist} - {t.title}"
                    self.tracks.append(t)
            else:
                reader = csv.reader(f)
                for row in reader:
                    query = row[0].strip() if row else ""
                    if query:
                        self.tracks.append(TrackItem(title=query, query=query, status="pending"))

    def _download_coordinator(self, workers: int):
        root_out = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get())
        root_out.mkdir(parents=True, exist_ok=True)
        log_name = datetime.now().strftime("ERROR_%y_%m_%d-%H-%M-%S.log")
        self.log_file_path = root_out.parent / log_name

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        pending_tracks = [t for t in self.tracks if t.status == "pending"]

        for t in pending_tracks:
            if self.stop_flag.is_set():
                break
            while self.pause_flag.is_set() and not self.stop_flag.is_set():
                time.sleep(0.2)
            if self.stop_flag.is_set():
                break

            future = self.executor.submit(self._download_single, t, root_out)
            self.active_futures[future] = t.uid

        for future in concurrent.futures.as_completed(list(self.active_futures.keys())):
            if self.stop_flag.is_set():
                break
            while self.pause_flag.is_set() and not self.stop_flag.is_set():
                time.sleep(0.2)
            if self.stop_flag.is_set():
                break
            try:
                result = future.result()
                self.result_queue.put({"type": "result", "data": result})
            except Exception as e:
                self.result_queue.put({"type": "error", "message": str(e)})
            finally:
                uid = self.active_futures.pop(future, None)

        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None

        self.result_queue.put({"type": "finished"})

    def _download_single(self, track: TrackItem, root_out: Path) -> dict:
        if self.stop_flag.is_set():
            return {"uid": track.uid, "success": False, "skipped": True}

        track.status = "downloading"
        self.result_queue.put({"type": "refresh"})

        query = track.query if track.query else f"{track.artist} - {track.title}"
        folder_struct = self.folder_struct_var.get()

        if folder_struct == "By playlist":
            playlist_folder = root_out / sanitize_for_filesystem(track.playlist)
        elif folder_struct == "By artist / album":
            playlist_folder = root_out / sanitize_for_filesystem(track.artist)
        else:
            playlist_folder = root_out

        playlist_folder.mkdir(parents=True, exist_ok=True)
        out_template = str(playlist_folder / "{title}.{ext}")

        fmt = self.format_var.get()
        br = self.bitrate_exact_var.get()
        bitrate = br if fmt not in ("flac", "wav") else None
        lyrics = self.lyrics_var.get()
        lp = self.lyrics_provider_var.get() if lyrics else ""

        cmd = make_spotdl_cmd(query, out_template, fmt, bitrate, lyrics, lp)

        self.result_queue.put({"type": "current_track", "info": f"{track.artist} — {track.title}"})

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=DOWNLOAD_TIMEOUT)
            success = proc.returncode == 0
            error_msg = proc.stderr[:500] if not success else ""
        except subprocess.TimeoutExpired:
            success = False
            error_msg = f"Timeout ({DOWNLOAD_TIMEOUT}s)"
        except subprocess.CalledProcessError as e:
            success = False
            error_msg = f"spotdl failed ({e.returncode}): {e.stderr[:300]}"
        except Exception as e:
            success = False
            error_msg = str(e)

        if not success:
            with open(root_out.parent / self.log_file_path, "a", encoding="utf-8") as f:
                f.write(f"{track.title} by {track.artist} failed. Query: '{query}'. Error: {error_msg}\n")

        return {"uid": track.uid, "success": success, "skipped": self.stop_flag.is_set(), "error": error_msg if not success else ""}

    def _check_download_status(self):
        keep_polling = True

        while not self.result_queue.empty():
            try:
                item = self.result_queue.get_nowait()

                if item["type"] == "finished":
                    self._final_cleanup()
                    keep_polling = False
                    break

                elif item["type"] == "current_track":
                    self.dl_current_track_label.configure(text=f"Current: {item['info']}")

                elif item["type"] == "refresh":
                    self._refresh_download_view()

                elif item["type"] == "result":
                    result = item["data"]
                    uid = result["uid"]
                    success = result["success"]
                    skipped = result.get("skipped", False)

                    for t in self.tracks:
                        if t.uid == uid:
                            if success:
                                t.status = "completed"
                            elif skipped:
                                t.status = "cancelled"
                            else:
                                t.status = "failed"
                                t.error = result.get("error", "")
                            break

                    if not success and not skipped:
                        self.error_count += 1
                    if not skipped:
                        self.completed_tracks += 1

                    pct = (self.completed_tracks / self.total_tracks) * 100 if self.total_tracks else 0
                    self.dl_progressbar.set(pct / 100)
                    self.dl_progress_label.configure(text=f"{self.completed_tracks} / {self.total_tracks} ({pct:.1f}%)")
                    self.dl_errors_label.configure(text=f"Errors: {self.error_count}" if self.error_count else "")
                    self.dl_status_label.configure(text=f"Status: Downloading...")
                    self._refresh_download_view()

                    notify = self.notify_var.get()
                    if notify == "Every track + done" and not skipped:
                        send_notification("Track Downloaded", f"{result.get('title', '')} completed")

                elif item["type"] == "error":
                    self.error_count += 1
                    self.dl_errors_label.configure(text=f"Errors: {self.error_count}")
                    self.dl_status_label.configure(text="Status: Error!")

            except Empty:
                break

        if keep_polling:
            now = datetime.now()
            if (now - self.last_eta_update).total_seconds() >= ETA_UPDATE_INTERVAL_SECONDS:
                self._update_eta()
            self.root.after(500, self._check_download_status)

    def _update_eta(self):
        if self.completed_tracks == 0 or self.stop_flag.is_set() or self.total_tracks == 0:
            self.dl_eta_label.configure(text="ETA: Calculating...")
            return

        elapsed = (datetime.now() - self.download_start_time).total_seconds()
        if self.completed_tracks > 0 and elapsed > 0:
            avg = elapsed / self.completed_tracks
            remaining = self.total_tracks - self.completed_tracks
            eta_sec = avg * remaining
            self.dl_eta_label.configure(text=f"ETA: {format_eta(eta_sec)}")
        self.last_eta_update = datetime.now()

    def _final_cleanup(self):
        self._downloading = False

        # Update download view with final status
        self.dl_status_label.configure(text="Status: Complete")
        self.dl_eta_label.configure(text="ETA: Done")
        self.dl_pause_btn.configure(state="disabled")
        self.dl_stop_btn.configure(state="disabled")
        self.dl_back_btn.pack(side="right", padx=10)

        # Update config view widgets before switching back
        pct = (self.completed_tracks / self.total_tracks) * 100 if self.total_tracks else 0
        self.progress_var.set(pct / 100)
        self.progress_label.configure(text=f"{self.completed_tracks} / {self.total_tracks} ({pct:.1f}%)")
        self.eta_label.configure(text="ETA: Complete")
        self.status_label.configure(text=f"Status: Done ({self.error_count} errors)" if self.error_count else "Status: Done")
        self._refresh_track_list()

        root_out = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get())

        if self.delete_empty_var.get():
            try:
                for f in root_out.iterdir():
                    if f.is_dir() and not any(f.iterdir()):
                        f.rmdir()
            except Exception:
                pass

        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="⏸  Pause")
        self.stop_btn.configure(state="disabled")

        notify = self.notify_var.get()
        if notify in ("On complete only", "On complete + on error", "Every track + done"):
            if self.error_count > 0:
                send_notification("Downloads Complete", f"{self.completed_tracks} done, {self.error_count} errors")
            else:
                send_notification("Downloads Complete", f"All {self.completed_tracks} tracks downloaded!")

    # ───────────────────────────────────────────────
    # EXPORT .SH
    # ───────────────────────────────────────────────

    def _export_sh(self):
        if not self.tracks:
            all_t = []
            input_mode = self.input_mode_var.get()
            if input_mode == "CSV / TXT":
                path = self.csv_var.get()
                if os.path.exists(path):
                    old_tracks = list(self.tracks)
                    self._load_csv(path)
                    all_t = list(self.tracks)
                    self.tracks.clear()
                    self.tracks.extend(old_tracks)
            elif input_mode in ("Spotify Link", "Smart (auto-detect)"):
                url = self.smart_var.get().strip()
                if url:
                    all_t = [TrackItem(query=url, title=url, status="pending")]
            elif input_mode == "Search":
                pass

            for entry in self.batch_queue:
                all_t.append(TrackItem(query=entry["url"], title=entry.get("title", entry["url"]), status="pending"))
        else:
            all_t = [t for t in self.tracks if t.status in ("pending", "failed")]

        if not all_t:
            messagebox.showinfo("Info", "No tracks to export.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".sh",
                                             filetypes=[("Shell Script", "*.sh")],
                                             initialfile="download.sh")
        if not path:
            return

        fmt = self.format_var.get()
        br = self.bitrate_exact_var.get()
        bitrate = br if fmt not in ("flac", "wav") else None
        lyrics = self.lyrics_var.get()
        lp = self.lyrics_provider_var.get() if lyrics else ""
        out_folder = Path(self.dest_var.get()) / sanitize_for_filesystem(self.subfolder_var.get()) if self.dest_var.get() else "./spotify-downloads"

        lines = ["#!/bin/bash",
                 f"# Generated by {APP_NAME} v{VERSION} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 "# scp this to your server: scp <script> user@host:/tmp/ && ssh user@host bash /tmp/<script>",
                 "",
                 "set -e",
                 "",
                 'command -v spotdl >/dev/null 2>&1 || { echo "spotdl not found"; exit 1; }',
                 'command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not found"; exit 1; }',
                 "",
                 f'OUTPUT_DIR="{out_folder}"',
                 "mkdir -p \"$OUTPUT_DIR\"",
                 "",
                 f'echo "=== Downloading {len(all_t)} track(s) ==="',
                 ""]

        for t in all_t:
            query = t.query if t.query else f"{t.artist} - {t.title}"
            cmd_parts = ["spotdl", "download", f'"{query}"',
                         '--output', '"$OUTPUT_DIR/{title}.{ext}"',
                         "--overwrite", "skip", "--log-level", "ERROR"]
            if fmt:
                cmd_parts.append(f"--format {fmt}")
            if bitrate and bitrate not in ("0", "lossless"):
                cmd_parts.append(f"--bitrate {bitrate}")
            if lyrics and lp:
                cmd_parts.append(f"--lyrics {lp}")
                cmd_parts.append("--generate-lrc")
            lines.append(" ".join(cmd_parts))

        lines.extend(["", 'echo "=== Done! ==="'])

        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(path, 0o755)

        messagebox.showinfo("Exported", f"Script saved to:\n{path}\n\nTo run on a server:\nscp {path} user@server:/tmp/ && ssh user@server bash /tmp/{os.path.basename(path)}")

    # ───────────────────────────────────────────────
    # SYSTEM TRAY
    # ───────────────────────────────────────────────

    def _minimize_to_tray(self):
        if not HAS_TRAY:
            return
        self.root.withdraw()
        icon_img = self._make_tray_icon()
        menu = (pystray.MenuItem("Show", self._restore_from_tray),
                pystray.MenuItem("Quit", self._tray_quit))
        self.tray_icon = pystray.Icon("spdl", icon_img, "SPOTDL GUI", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _restore_from_tray(self, icon=None):
        if icon:
            icon.stop()
        self.root.deiconify()
        self.root.lift()

    def _tray_quit(self, icon):
        icon.stop()
        self.root.quit()
        self.root.destroy()

    def _make_tray_icon(self) -> Image.Image:
        img = Image.new("RGB", (64, 64), "#1e1e2e")
        draw = ImageDraw.Draw(img)
        draw.ellipse([12, 12, 52, 52], fill="#4ade80")
        draw.polygon([(28, 22), (28, 42), (44, 32)], fill="#1e1e2e")
        return img

    # ───────────────────────────────────────────────
    # RESUME
    # ───────────────────────────────────────────────

    def _check_resume(self):
        if not ResumeManager.exists():
            return
        try:
            state = ResumeManager.load()
            if not state or not state.tracks:
                return
            if messagebox.askyesno("Unfinished Download Found!",
                                    f"An incomplete download was found from {state.timestamp[:16] if state.timestamp else 'earlier'}.\n"
                                    f"{state.completed_count} / {state.total_count} tracks completed.\n\n"
                                    "Would you like to resume?"):
                self._restore_resume_state(state)
            else:
                ResumeManager.clear()
        except Exception:
            ResumeManager.clear()

    def _restore_resume_state(self, state: ResumeState):
        self.tracks = state.tracks
        self.total_tracks = state.total_count
        self.completed_tracks = state.completed_count
        self.dest_var.set(state.output_folder)
        self.subfolder_var.set(state.subfolder)
        self.format_var.set(state.format_)
        self.bitrate_exact_var.set(state.bitrate)
        self.folder_struct_var.set(state.folder_structure)
        self.lyrics_var.set(state.lyrics)
        self.lyrics_provider_var.set(state.lyrics_provider)
        self.concurrent_var.set(state.concurrent)
        self.delete_empty_var.set(state.delete_empty)
        self.input_mode_var.set(state.input_mode)
        self._on_input_mode_change()
        self._refresh_track_list()
        self._update_size_estimate()

        self.progress_label.configure(text=f"{state.completed_count} / {state.total_count} ({state.completed_count/state.total_count*100:.1f}%)")
        self.progress_var.set(state.completed_count / state.total_count if state.total_count else 0)

    def _save_resume_state(self):
        state = ResumeState(
            input_mode=self.input_mode_var.get(),
            output_folder=self.dest_var.get(),
            subfolder=self.subfolder_var.get(),
            format_=self.format_var.get(),
            bitrate=self.bitrate_exact_var.get(),
            folder_structure=self.folder_struct_var.get(),
            lyrics=self.lyrics_var.get(),
            lyrics_provider=self.lyrics_provider_var.get(),
            concurrent=self.concurrent_var.get(),
            delete_empty=self.delete_empty_var.get(),
            completed_count=self.completed_tracks,
            total_count=self.total_tracks,
            tracks=self.tracks,
            timestamp=datetime.now().isoformat(),
        )
        ResumeManager.save(state)

    # ───────────────────────────────────────────────
    # CLOSE
    # ───────────────────────────────────────────────

    def on_close(self):
        if hasattr(self, '_downloading') and self._downloading:
            if messagebox.askyesno("Download in Progress",
                                    "Downloads are still running.\n\n"
                                    "Save progress and resume later?"):
                self.stop_flag.set()
                if self.executor:
                    self.executor.shutdown(wait=False, cancel_futures=True)
                self._save_resume_state()
                self.root.destroy()
                return
            elif messagebox.askyesno("Quit", "Exit and lose all progress?"):
                self.stop_flag.set()
                if self.executor:
                    self.executor.shutdown(wait=False, cancel_futures=True)
                ResumeManager.clear()
                self.root.destroy()
                return
            else:
                return
        if messagebox.askokcancel("Quit", "Exit SPOTDL GUI?"):
            ResumeManager.clear()
            self.root.destroy()

# ═══════════════════════════════════════════════
# MAIN ENTRY
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    SpotDLGUI()
