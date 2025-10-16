
-----

# ✨ Spotify Downloader GUI for SpotDL

**Cross-platform GUI Spotify Library Downloader**

*By © 2025 Minxify_ig*

[![License](https://img.shields.io/badge/license-GNU-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)]()


-----
## ⚠️ Disclaimer & Important Notes

Please read this before running the application:

  * **Potential Freezing:** This application **will seem like it's frozen** during downloads, especially when processing large lists. **It is NOT frozen.** Please be patient.
  * **Performance:** Users with **low-end computers** may experience slowdowns or potential crashes.
  * **Liability:** I am not responsible for any damage to your computer from executing this program. Use at your own risk. you can see all the code in this repository tho.

-----

## 🚀 Key Features

  * **Full GUI** with a sleek, dark Spotify aesthetic.
  * **Auto-Setup:** Automatically installs all required dependencies (`spotDL`, `FFmpeg`, and `Mutagen`) on first run.
  * **Robust Logging:** Generates timestamped **JSON logs** with full track info and Spotify URLs for verification and retries.
  * **Cross-Platform:** Works out-of-the-box on **Windows**, **Debian/Ubuntu**, and **Manjaro/Arch**.

-## (only tested on Arch linux! but should work anywhere else!)

-----

## 🖼️ Look and Feel

  * **Intuitive Interface:** A user-friendly UI that anyone can master in seconds.
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/1f1963e3-8bd8-4da3-acce-013921f85a8e" />


-----

## 💾 Logs & Verification

Each download session creates a timestamped log file in the following format:

`download_log_YYYY-MM-DD_HH-MM-SS.json`

This file contains **full track information** and **Spotify URLs**, which is useful for verifying downloads or attempting manual retries.

-----

## 🪩 License & Credits

© 2025 Minxify\_ig. All rights reserved.

Built with 💚 using:

  * [spotDL](https://github.com/spotDL/spotify-downloader) (for the core downloading logic)
  * [Mutagen](https://mutagen.readthedocs.io/) (for audio metadata handling)
