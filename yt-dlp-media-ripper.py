#!/usr/bin/env python3

"""
dataprep.py

Media downloader using yt-dlp.

- All output folders created inside the directory where the script runs.
- Supports audio-only (WAV), video-only, or both.
- Optionally downloads subtitles.
- Creates and uses a virtual environment in the script folder.
- Automatically installs yt-dlp if missing.
"""

import os
import sys
import subprocess
from pathlib import Path

# --- Working directories relative to script location ---
SCRIPT_DIR = Path.cwd()  # Directory where script is executed
VENV_DIR = SCRIPT_DIR / ".venv"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_AUDIO = OUTPUT_DIR / "audio"
OUTPUT_VIDEO = OUTPUT_DIR / "video"
OUTPUT_SUBS = OUTPUT_DIR / "subtitles"

def ensure_directories():
    """
    Create output and venv directories if they don't exist.
    """
    for directory in [VENV_DIR, OUTPUT_AUDIO, OUTPUT_VIDEO, OUTPUT_SUBS]:
        directory.mkdir(parents=True, exist_ok=True)

def setup_virtualenv():
    """
    Create Python virtual environment and install yt-dlp if needed.
    """
    if not (VENV_DIR / "bin" / "python").exists() and not (VENV_DIR / "Scripts" / "python.exe").exists():
        print("[INFO] Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    python_bin = VENV_DIR / "bin" / "python" if os.name != "nt" else VENV_DIR / "Scripts" / "python.exe"
    pip_bin = VENV_DIR / "bin" / "pip" if os.name != "nt" else VENV_DIR / "Scripts" / "pip.exe"

    try:
        subprocess.run([pip_bin, "show", "yt-dlp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("[INFO] yt-dlp already installed in virtual environment.")
    except subprocess.CalledProcessError:
        print("[INFO] Installing yt-dlp in virtual environment...")
        subprocess.check_call([pip_bin, "install", "--upgrade", "pip", "yt-dlp"])

    return str(python_bin)

def prompt_user_options():
    """
    Ask user for input file and download preferences.
    """
    file_path = input("Enter path to TXT file with URLs: ").strip()
    url_file = Path(file_path)
    if not url_file.is_file():
        print(f"[ERROR] File not found: {url_file}")
        sys.exit(1)

    print("\nDownload options:")
    print("1 - Audio only (WAV)")
    print("2 - Video only")
    print("3 - Both audio and video")
    choice = input("Choose 1, 2 or 3: ").strip()

    if choice == "1":
        audio, video = True, False
    elif choice == "2":
        audio, video = False, True
    elif choice == "3":
        audio, video = True, True
    else:
        print("[ERROR] Invalid choice.")
        sys.exit(1)

    subtitles_choice = input("Download subtitles if available? (y/n): ").strip().lower()
    download_subtitles = subtitles_choice == "y"

    return url_file, audio, video, download_subtitles

def build_yt_dlp_command(python_bin, url, audio, video, download_subs):
    """
    Build yt-dlp command based on user preferences.
    """
    base_cmd = [python_bin, "-m", "yt_dlp"]

    if audio and not video:
        # Audio only
        outtmpl = str(OUTPUT_AUDIO / "%(title)s.%(ext)s")
        cmd = base_cmd + [
            "-x",
            "--audio-format", "wav",
            "-o", outtmpl
        ]
    elif video and not audio:
        # Video only
        outtmpl = str(OUTPUT_VIDEO / "%(title)s.%(ext)s")
        cmd = base_cmd + [
            "-f", "bestvideo+bestaudio/best",
            "-o", outtmpl
        ]
    elif audio and video:
        # Both (merged)
        outtmpl = str(OUTPUT_VIDEO / "%(title)s.%(ext)s")
        cmd = base_cmd + [
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", outtmpl
        ]
    else:
        raise ValueError("Invalid download options: audio and video flags.")

    if download_subs:
        # Save subtitles to subtitles folder
        subs_outtmpl = str(OUTPUT_SUBS / "%(title)s.%(ext)s")
        cmd += [
            "--write-sub",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--convert-subs", "srt",
            "--sub-format", "srt",
            "-o", outtmpl,
            "--output", subs_outtmpl  # Note: yt-dlp may not accept multiple -o flags; workaround needed below
        ]

    cmd.append(url)
    return cmd

def run_download(python_bin, url, audio, video, download_subs):
    """
    Run yt-dlp with the constructed command.
    """
    # yt-dlp only accepts one output template, so handle subs output differently
    # We'll run yt-dlp twice if subtitles requested for separate output directory

    if download_subs:
        # Download video/audio first
        cmd_media = build_yt_dlp_command(python_bin, url, audio, video, False)
        print(f"[INFO] Running media download: {' '.join(cmd_media)}")
        subprocess.run(cmd_media, check=True)

        # Download subtitles separately
        cmd_subs = [
            python_bin, "-m", "yt_dlp",
            "--skip-download",
            "--write-sub",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--convert-subs", "srt",
            "-o", str(OUTPUT_SUBS / "%(title)s.%(ext)s"),
            url
        ]
        print(f"[INFO] Running subtitles download: {' '.join(cmd_subs)}")
        subprocess.run(cmd_subs, check=True)

    else:
        # Download only media
        cmd = build_yt_dlp_command(python_bin, url, audio, video, False)
        print(f"[INFO] Running download: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

def main():
    ensure_directories()
    python_bin = setup_virtualenv()
    url_file, audio, video, download_subs = prompt_user_options()

    with url_file.open("r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print("[ERROR] No URLs found in file.")
        sys.exit(1)

    for url in urls:
        print(f"\n[INFO] Processing URL: {url}")
        try:
            run_download(python_bin, url, audio, video, download_subs)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Download failed for URL: {url}\n{e}")

    print("\n[INFO] All downloads completed.")
    print(f"Media saved under:\n - {OUTPUT_AUDIO}\n - {OUTPUT_VIDEO}")
    if download_subs:
        print(f"Subtitles saved under:\n - {OUTPUT_SUBS}")

if __name__ == "__main__":
    main()
