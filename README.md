## ⚠️ CURRENTLY BROKEN DUE TO UPDATE IN SPOTDL!!⚠️
**i will update this programm as soon as i have time for it!**


# ✨ Spotify Downloader GUI for SpotDL

**A Cross-Platform Graphical Interface for Downloading Your Spotify Library**

*By © 2025 Minxify_ig*

## ⚠️ Disclaimer & Important Notes

Please read this before running the application:

* **Potential Freezing:** The application **will appear to freeze** during downloads, especially when processing large lists. **It is NOT frozen.** Please be patient.

* **Performance:** Users with **low-end computers** may experience significant slowdowns or potential crashes.

* **Liability:** Use at your own risk. I am not responsible for any damage to your computer from executing this program. The full source code is available in this repository for review.

## 🖥️ Installation

The installation is straightforward.

1. Head to the [releases page](https://github.com/Minxify/Spotify-downloader-GUI/releases) to download the installer for your system.

2. Download the `Install-Windows.bat` or `Install-Linux.sh` file.

3. **On Windows:** Double-click the `.bat` file to run the installer.

4. **On Linux:** You may need to make the script executable. Open your terminal and run the following commands:

   ```bash
   cd Downloads #or wherever you have saved the file!
   chmod +x Install-Linux.sh
   ./Install-Linux.sh
   ```

## 🎧 How to Download Playlists

This tool works by using a playlist exported as a **CSV** file. If you already have a compatible `.CSV` file, skip to Part 2.

### **Part 1: Exporting Your Playlist (via TuneMyMusic)**

1. Go to [**TuneMyMusic**](https://www.tunemymusic.com) and select **Spotify** as the source.

   <img width="1914" height="958" alt="image" src="https://github.com/user-attachments/assets/86294d76-b438-4172-b88a-7193a4d6229b" />

2. Log into Spotify. (This service is verified and safe; no personal data is transferred outside of the files you choose.) Once logged in, click **"Load from Spotify account"**.

   <img width="943" height="566" alt="image" src="https://github.com/user-attachments/assets/4c8d1b34-18c1-4e3d-8155-89afb5381d59" />

3. Select the playlists and/or individual songs you want to download. Click **"Choose Destination"**.

   <img width="943" height="566" alt="image" src="https://github.com/user-attachments/assets/060d8432-12e5-474b-a0eb-4acdf5c753ed" />

4. Scroll down, select **"Export to file"**, and choose **CSV**.

   <img width="891" height="678" alt="image" src="https://github.com/user-attachments/assets/8dafca8d-6ca8-40e8-96e5-c27f0259243d" />
   <img width="719" height="538" alt="image" src="https://github.com/user-attachments/assets/6b08b64d-a00f-478e-82b5-8c388ee188fe" />

5. Click **"Start Transfer"** to download your playlist as a `.csv` file.

   <img width="307" height="300" alt="image" src="https://github.com/user-attachments/assets/eb8159a9-b5c8-4db9-910c-8b5a2edfb440" />

### **Part 2: Using the GUI Downloader**

6. Open the **Spotify Downloader GUI**.

   <img width="458" height="42" alt="image" src="https://github.com/user-attachments/assets/ffa4cb30-9363-4b12-8e60-7dfd8890ff69" />

7. At the top, ensure **CSV/TXT** is selected from the dropdown menu.

   <img width="904" height="71" alt="image" src="https://github.com/user-attachments/assets/c655ce14-5658-4194-a931-4bce73faf4ca" />

8. Click the **Select folder** button and choose your desired output folder.

   <img width="904" height="45" alt="image" src="https://github.com/user-attachments/assets/07c70023-18d2-4c60-af0f-6f716052d640" />

9. Enter a name for the sub-folder that will contain the downloads (Default: `Spotify Downloads`).

   <img width="904" height="31" alt="image" src="https://github.com/user-attachments/assets/a662b15b-0528-43ab-86f6-8e52647f1e19" />

10. Choose whether you want to delete empty folders. **Note:** This option applies to *all* empty folders within the selected output directory.

    <img width="904" height="31" alt="image" src="https://github.com/user-attachments/assets/d9f1a45a-d3aa-4c2f-a2d8-3abc0cad49e3" />


11. Choose if how many songs you want to download concurrently.

   <img width="247" height="38" alt="image" src="https://github.com/user-attachments/assets/dae5a198-d682-461b-b107-3d8f91737c3e" />


12. Finally, click the button to select the **CSV** file you exported earlier.

    <img width="904" height="45" alt="image" src="https://github.com/user-attachments/assets/73d32ca8-efc2-4c67-9c08-c6276475c2f8" />

13. Click **Start Download** and watch it work!

## 🚀 Key Features

* **Full GUI** with a sleek, dark Spotify aesthetic.

* **Auto-Setup:** Automatically installs all required dependencies (`spotDL`, `FFmpeg`, and `Mutagen`) on first run.

* **Robust Logging:** Generates timestamped **JSON logs** with full track info and Spotify URLs for verification and retries.

* **Cross-Platform:** Works out-of-the-box on **Windows**, **Debian/Ubuntu**, and **Manjaro/Arch**. (Tested primarily on Arch Linux!)

## 🖼️ Look and Feel

* **Intuitive Interface:** A user-friendly UI that anyone can master in seconds.

  <img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/1f1963e3-8bd8-4da3-acce-013921f85a8e" />

## 💾 Logs & Verification

Each download session creates a timestamped log file in the following format:

`download_log_YYYY-MM-DD_HH-MM-SS.json`

This file contains **full track information** and **Spotify URLs**, which is useful for verifying downloads or attempting manual retries.

## 🪩 License & Credits

© 2025 Minxify_ig. All rights reserved.

Built with 💚 using:

* [spotDL](https://github.com/spotDL/spotify-downloader) (for the core downloading logic)

* [Mutagen](https://mutagen.readthedocs.io/) (for audio metadata handling)
