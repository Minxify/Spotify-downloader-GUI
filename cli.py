#!/usr/bin/env python3
"""
SPOTDL GUI v3.0.0 — CLI Downloader

Headless download mode for server/remote usage.
Usage:
    python cli.py --input playlist.csv --format flac --output ./music
    python cli.py --input "https://open.spotify.com/playlist/..." --format mp3 --bitrate 320
    python cli.py --input "saved" --format opus

Author: Minxify_ig
Year: 2026
"""

import os, sys, csv, time, json, subprocess, concurrent.futures, argparse, shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


def _find_spotdl() -> list[str]:
    which = shutil.which("spotdl")
    if which:
        return [which]
    return [sys.executable, "-m", "spotdl"]


SPOTDL_CMD = _find_spotdl()
DOWNLOAD_TIMEOUT = 300


def sanitize(name: str) -> str:
    if not name:
        return "Unknown"
    safe = "".join(c if c.isprintable() else "_" for c in name.strip())
    safe = safe.replace("/", "_").replace("\\", "_")
    return safe[:200]


def is_tool(name: str) -> bool:
    return shutil.which(name) is not None


def make_cmd(query: str, out_template: str, fmt: str, bitrate: Optional[str],
             lyrics: bool, lyrics_provider: str) -> list:
    cmd = [*SPOTDL_CMD, "download", query, "--output", out_template,
           "--overwrite", "skip", "--log-level", "ERROR"]
    if fmt:
        cmd += ["--format", fmt]
    if bitrate and bitrate not in ("0", "lossless"):
        cmd += ["--bitrate", bitrate]
    if lyrics and lyrics_provider:
        cmd += ["--lyrics", lyrics_provider, "--generate-lrc"]
    return cmd


def load_tracks(csv_path: str) -> list[dict]:
    tracks = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        first = "".join(f.readline() for _ in range(5))
        f.seek(0)
        has_header = any(h in first for h in ["Track name", "track name", "Track Name"])
        if has_header:
            import csv as csv_mod
            reader = csv_mod.DictReader(f)
            for row in reader:
                t = {
                    "title": row.get("Track name") or row.get("track name") or "",
                    "artist": row.get("Artist name") or row.get("artist name") or "",
                    "playlist": row.get("Playlist name") or "Default",
                    "spotify_id": row.get("Spotify - id") or row.get("spotify - id") or "",
                }
                tracks.append(t)
        else:
            for line in f:
                line = line.strip()
                if line:
                    tracks.append({"title": line, "artist": "", "playlist": "Default", "spotify_id": ""})
    return tracks


def download_track(track: dict, out_folder: Path, fmt: str, bitrate: Optional[str],
                   lyrics: bool, lyrics_provider: str, idx: int, total: int, log_file: Path) -> dict:
    title = track.get("title", "")
    artist = track.get("artist", "")
    spotify_id = track.get("spotify_id", "")

    playlist_folder = out_folder / sanitize(track.get("playlist", "Default"))
    playlist_folder.mkdir(parents=True, exist_ok=True)
    out_template = str(playlist_folder / "{title}.{ext}")

    query = f"https://open.spotify.com/track/{spotify_id}" if spotify_id else f"{artist} - {title}"
    cmd = make_cmd(query, out_template, fmt, bitrate, lyrics, lyrics_provider)

    print(f"[{idx}/{total}] {title}" + (f" — {artist}" if artist else ""))

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT)
        success = proc.returncode == 0
        err = proc.stderr[:300] if not success else ""
    except subprocess.TimeoutExpired:
        success, err = False, f"Timeout ({DOWNLOAD_TIMEOUT}s)"
    except Exception as e:
        success, err = False, str(e)

    if not success:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{title} by {artist} failed. Error: {err}\n")
        print(f"  ✗ Failed: {err}")
    else:
        print(f"  ✓ Done")

    return {"title": title, "success": success}


def run_downloads(tracks: list[dict], output: str, fmt: str, bitrate: Optional[str],
                  workers: int, lyrics: bool, lyrics_provider: str):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    log_name = datetime.now().strftime("ERROR_%y_%m_%d-%H-%M-%S.log")
    log_file = root.parent / log_name

    total = len(tracks)
    completed = 0
    errors = 0

    print(f"\nDownloading {total} track(s) to {root}")
    print(f"Format: {fmt}" + (f" @ {bitrate}" if bitrate and bitrate != "lossless" else ""))
    print(f"Workers: {workers}")
    print()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i, track in enumerate(tracks, 1):
            f = executor.submit(download_track, track, root, fmt, bitrate,
                                lyrics, lyrics_provider, i, total, log_file)
            futures.append(f)

        for f in concurrent.futures.as_completed(futures):
            try:
                result = f.result()
                if result["success"]:
                    completed += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                print(f"Thread error: {e}")

    print(f"\n{'='*40}")
    print(f"Complete: {completed}/{total} | Errors: {errors}")
    if errors > 0:
        print(f"Error log: {log_file}")


def main():
    parser = argparse.ArgumentParser(
        description="SPOTDL GUI — CLI Downloader (headless)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --input playlist.csv --format flac --output ./music
  python cli.py --input "https://open.spotify.com/playlist/..." --bitrate 320
  python cli.py --input "saved" --format opus --lyrics genius
        """
    )

    parser.add_argument("--input", "-i", required=True,
                        help="CSV/TXT file path or Spotify URL (playlist/album/artist/track) or 'saved' for liked songs")
    parser.add_argument("--output", "-o", default="./spotify-downloads",
                        help="Output directory (default: ./spotify-downloads)")
    parser.add_argument("--format", "-f", default="mp3",
                        choices=["mp3", "flac", "ogg", "opus", "m4a", "wav"],
                        help="Audio format (default: mp3)")
    parser.add_argument("--bitrate", "-b", default=None,
                        help="Bitrate for lossy formats: 128, 192, 256, 320, etc. (default: 320 for mp3)")
    parser.add_argument("--workers", "-w", type=int, default=5,
                        help="Concurrent downloads (default: 5)")
    parser.add_argument("--lyrics", "-l", default=None,
                        choices=["genius", "musixmatch", "azlyrics", "synced"],
                        help="Download lyrics with specified provider")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress per-track output")

    args = parser.parse_args()

    if not is_tool(SPOTDL_CMD[0]):
        print("Error: spotdl not found. Install with: pip install spotdl")
        sys.exit(1)
    if not is_tool("ffmpeg"):
        print("Warning: ffmpeg not found. Audio processing may fail.")

    tracks = []

    if os.path.isfile(args.input):
        tracks = load_tracks(args.input)
    else:
        tracks = [{"title": args.input, "artist": "", "playlist": "Download", "spotify_id": ""}]

    if not tracks:
        print("Error: No tracks found.")
        sys.exit(1)

    bitrate = args.bitrate
    if not bitrate and args.format not in ("flac", "wav"):
        bitrate = "320k"

    run_downloads(tracks, args.output, args.format, bitrate,
                  args.workers, bool(args.lyrics), args.lyrics or "genius")


if __name__ == "__main__":
    main()
