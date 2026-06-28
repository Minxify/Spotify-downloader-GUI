# Spotify Downloader GUI for SpotDL

**A cross-platform GUI + CLI for downloading Spotify playlists, albums, artists, and tracks.**  
Search, paste a link, or import CSV — with concurrent downloads, format selection, lyrics, scheduling, and more.

By [Minxify_ig](https://minxie.likesyou.org) | [GitHub](https://github.com/Minxify/Spotify-downloader-GUI)

---
# New! Android is now a supported platform! click [HERE](https://github.com/Minxify/Spotify-downloader-GUI/releases/tag/AV1.0.3)
if on a pc ignore this message!
## Quick Start

```bash
# Linux / macOS
./setup.sh && ./start.sh

# Windows — double-click setup.bat, then start.bat
```

---

## Prerequisites

- **Python 3.9+** ([python.org](https://www.python.org/downloads/))
- **FFmpeg** (audio processing)

### Installing FFmpeg

| OS | Command |
|---|---|
| Arch / Manjaro | `sudo pacman -S ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| macOS (Homebrew) | `brew install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html), add to PATH |

---

## What's new in v3.0

### Two views — settings hidden during download

When you hit download, the app switches from the full settings UI to a **dedicated download view**:

```
┌─ Download Progress ──────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░  12 / 25 (48.0%)        │
│ ETA: 2m 35s  |  Est. ~180MB  |  Errors: 0   │
│ Current: Song Title — Artist                  │
├─ Track Queue ────────────────────────────────┤
│ ▶ Song One — Artist A                [×]    │
│ ⬜ Song Two — Artist B                [×]    │
│ ⬜ Song Three — Artist C              [×]    │
│ ⬜ Song Four — Artist D               [×]    │
│ ⬜ Song Five — Artist E               [×]    │
│ ⬜ Song Six — Artist F                [×]    │
│ + 20 more pending                             │
├──────────────────────────────────────────────┤
│ [⏸ Pause]  [⏹ Stop]  [Minimize to Tray]     │
│                                       [✕ Back]│
└──────────────────────────────────────────────┘
```

- **No settings visible** — no format dropdowns, search bars, or batch panels to slow things down
- **Culled track list** — only the currently-downloading track + next 5 pending; the rest are counted (`+ N more pending`)
- **Dramatically less rendering** — ~80 widgets hidden during download
- **Pause / Stop / Back to Settings** once complete

### spotDL v4 support

Updated for **spotDL 4.5.0** — new CLI syntax, `download` subcommand, `{title}.{ext}` output templates. Auto-detects spotdl even when running from the venv.

### .lrc lyrics files

Checking "Lyrics" now generates standalone `.lrc` files alongside your audio tracks, viewable in VLC, MusicBee, and most players.

---

## Features

### Input methods

| Mode | What it does |
|---|---|
| **Smart (auto-detect)** | Paste any Spotify URL — track, album, playlist, artist — app figures out what to do |
| **Spotify Link** | Paste a playlist URL directly |
| **Search** | Search Spotify by track/album/artist name, pick results, add to queue |
| **CSV / TXT** | Import playlists exported from [TuneMyMusic](https://www.tunemymusic.com) or similar |

### Download options

- **Format**: mp3, flac, ogg, opus, m4a, wav
- **Bitrate**: grouped presets (Low/Medium/High/Very High) with fine-tune expand for exact bitrate
- **Lyrics**: optional download with `.lrc` generation and provider selection (genius, musixmatch, azlyrics, synced)
- **Folder structure**: by playlist / by artist & album / flat
- **Concurrent downloads**: how many tracks to download at once (default: 10)
- **Delete empty folders**: auto-cleanup after download
- **File size estimation**: per-track (~X MB/3min) + total estimated size

### Queue & control

- **Batch queue**: add multiple playlists, choose sequential or parallel mode
- **Per-track control**: cancel individual tracks with a × button
- **Pause / Resume**: pause the entire queue, resume later
- **Stop**: graceful shutdown mid-download
- **Track list**: live status icons (⬜ pending, ▶ downloading, ✅ done, ❌ failed, ⏹ cancelled)

### Scheduling

- **One-time schedule**: set a date/time for downloads to auto-start
- **Playlist watcher**: periodically check a playlist for new tracks

### Presets

- Save your settings (format, bitrate, output folder, etc.) as named presets
- Auto-loads the last used preset on startup
- Switch between presets with a dropdown

### Spotify integration

- **Sign in with Spotify** via browser OAuth (PKCE — no passwords shared)
- Search Spotify's catalog from inside the app
- Access private playlists, liked songs, and saved albums
- Token cached in `~/.config/spotdl-gui/`

### Notifications

Choose when to get desktop alerts:

| Option | Behavior |
|---|---|
| On complete only | One notification when all downloads finish |
| On complete + on error | Notification on finish + per-failure alerts |
| Every track + done | Notification for each track (warning shown for >10 tracks) |

### System tray

Minimize to tray — downloads continue in the background.  
*Requires `pip install pystray` in the venv.*

### Export as shell script

Generate a `.sh` script from your download queue. SCP it to a server and run:

```bash
scp download.sh user@server:/tmp/
ssh user@server bash /tmp/download.sh
```

### Resume

Close the app mid-download? State is saved to `~/.cache/spotdl-gui/resume.json`.  
Next launch shows: *"Unfinished download found! Resume?"* — picks up where you left off, including progress, settings, and queue.

---

## What's in the box

| File | Purpose |
|---|---|
| `SpDL.py` | The GUI application |
| `cli.py` | Headless CLI downloader |
| `setup.sh` | Linux/macOS — one-step install |
| `setup.bat` | Windows — one-step install |
| `start.sh` | Linux/macOS launcher |
| `start.bat` | Windows launcher |
| `requirements.txt` | Python dependencies |
| `setup.html` | Visual setup guide (open in browser) |
| `venv/` | Isolated environment (created by setup) |

---

## How to use

### 1. Sign in (optional — enables search + private playlists)

![Sign in button in top bar](screenshots/signin-button.png)

Click **"Sign in with Spotify ▸"** in the top-right corner. On first run, a wizard guides you through creating a Spotify App and pasting your Client ID. After that, clicking Sign In opens your browser — authorize once and the token is cached.

> **One-time setup**: go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), create an app, set redirect URI to `http://localhost:8888/callback`, copy the Client ID. That's it — no Client Secret needed (PKCE).

### 2. Add tracks

#### Smart mode (recommended)

```
┌──────────────────────────────────────────────┐
│ Input: [Smart (auto-detect) ▼]               │
│ Paste any Spotify URL: [__________________]  │
│                                    (Track)   │
│                                        [Add]  │
└──────────────────────────────────────────────┘
```

Paste any Spotify URL — the app detects whether it's a track, album, playlist, or artist and handles it accordingly. Individual tracks go straight to the queue; albums/playlists/artists are added to the batch queue.

#### Search mode

```
┌──────────────────────────────────────────────┐
│ Input: [Search ▼]                             │
│ Search: [_________________________] [Search]  │
│ ┌─ Results ──────────────────────────────┐   │
│ │ ☐ 🎵 Song One — Artist A               │   │
│ │ ☐ 💿 Album Name — Artist B             │   │
│ │ ☐ 👤 Artist Name                       │   │
│ └────────────────────────────────────────┘   │
│ [Add Selected to Queue]                       │
└──────────────────────────────────────────────┘
```

Switch to **Search** mode, type a query, browse results, check what you want, and add them to the queue.

#### Playlist Link / CSV

Same as before — paste a playlist URL or select a CSV/TXT file exported from TuneMyMusic.

### 3. Configure settings

```
Format: [mp3 ▼]  Bitrate: [Very High (224k-320k) ▼] [Fine tune ▾]
Folder: [By playlist ▼]  Lyrics: [☑] [genius ▼]  Concurrent: [10]
Notify: [On complete only ▼]  ☐ Delete empty folders
```

- Pick audio format and quality
- Choose folder structure
- Toggle lyrics with `.lrc` generation
- Save as a preset for next time

### 4. Batch queue (optional)

```
Batch Queue
URL: [__________________________] [Add to Queue]
[Sequential ▼] [Clear All]
┌─ Queue ────────────────────────────┐
│ • playlist: My Playlist 1    [×]   │
│ • album: Cool Album          [×]   │
└────────────────────────────────────┘
```

Add multiple playlists/albums. Sequential mode processes them one by one; Parallel runs them simultaneously.

### 5. Download

Click **▶ Start Download**. The app switches to download view:

```
┌─ Download Progress ──────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░  12 / 25 (48.0%)        │
│ ETA: 2m 35s  |  Est. ~180MB  |  Errors: 0   │
│ Current: Song Title — Artist                  │
├─ Track Queue ────────────────────────────────┤
│ ▶ Song One — Artist A                [×]    │
│ ⬜ Song Two — Artist B                [×]    │
│ ⬜ Song Three — Artist C              [×]    │
│ ⬜ Song Four — Artist D               [×]    │
│ ⬜ Song Five — Artist E               [×]    │
│ ⬜ Song Six — Artist F                [×]    │
│ + 20 more pending                             │
├──────────────────────────────────────────────┤
│ [⏸ Pause]  [⏹ Stop]  [Minimize to Tray]     │
│                                       [✕ Back]│
└──────────────────────────────────────────────┘
```

No settings visible — just progress, ETA, size estimate, and the active download queue. Click **✕ Back** to return to settings once complete.

### 6. CLI mode

```bash
python cli.py --input playlist.csv --format flac --output ./music
python cli.py --input "https://open.spotify.com/playlist/..." --bitrate 320k
python cli.py --input "saved" --format opus --lyrics genius
```

Headless downloader for servers/remote machines. Same engine as the GUI.

---

## Logs

Errors are written to timestamped `ERROR_*.log` files in the parent of your output directory. Each entry shows which track failed and why.

---

## Notes

- The app uses `customtkinter` for a modern dark UI
- Downloads use [spotDL](https://github.com/spotDL/spotify-downloader) v4 under the hood
- Settings live in `~/.config/spotdl-gui/` (presets, Spotify token, credentials)
- Cache/resume state lives in `~/.cache/spotdl-gui/`
- Large playlists with "Every track + done" notifications show a warning before proceeding
- Pystray system tray support is optional: `pip install pystray` (inside the venv)

---

## Screenshots


| Feature | Screenshot |
|---|---|
| Main window — config view | <img width="1127" height="929" alt="image" src="https://github.com/user-attachments/assets/417b9c8f-6e36-4742-a42f-3bac8d9fe5a5" />
 |
| Download progress view | `screenshots/download-view.png` |
| Search results | `screenshots/search-results.png` |
| Smart URL detection | `screenshots/smart-detect.png` |
| Batch queue with multiple playlists | `screenshots/batch-queue.png` |
| Preset selector | <img width="257" height="170" alt="image" src="https://github.com/user-attachments/assets/f132fb6c-af51-447e-bdb9-95986ba72104" />
 |
| Schedule dialog | <img width="401" height="341" alt="image" src="https://github.com/user-attachments/assets/9b569eaf-b08b-43bf-a6c9-b43232c2996b" />
 |
| Track list with statuses | `screenshots/track-list.png` |
| OAuth sign-in wizard | Currently broken |
| CLI help output | `screenshots/cli-help.png` |

---

© 2026 Minxify_ig
