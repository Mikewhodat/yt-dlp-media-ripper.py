#!/usr/bin/env python3
"""
YouTube Collector Agent
Combines DuckDuckGo search + yt-dlp download into one workflow.
1. Checks prerequisites
2. Searches DuckDuckGo for YouTube content
3. Saves results to urls.txt (overwrites each run)
4. Downloads media using yt-dlp
"""

import os
import sys
import subprocess
import requests
import re
import urllib.parse
from pathlib import Path
from urllib.parse import quote_plus

# --- Working directories ---
SCRIPT_DIR = Path.cwd()
VENV_DIR = SCRIPT_DIR / ".venv"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_AUDIO = OUTPUT_DIR / "audio"
OUTPUT_VIDEO = OUTPUT_DIR / "video"
OUTPUT_SUBS = OUTPUT_DIR / "subtitles"
URLS_FILE = SCRIPT_DIR / "urls.txt"


def print_header(text):
    """Print a nice header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def ensure_directories():
    """Create output and venv directories if they don't exist."""
    for directory in [VENV_DIR, OUTPUT_AUDIO, OUTPUT_VIDEO, OUTPUT_SUBS]:
        directory.mkdir(parents=True, exist_ok=True)


def check_prerequisites():
    """Check and install all prerequisites."""
    print_header("STEP 1: Checking Prerequisites")
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("[ERROR] Python 3.7+ required")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Setup virtual environment
    if not (VENV_DIR / "bin" / "python").exists() and not (VENV_DIR / "Scripts" / "python.exe").exists():
        print("[INFO] Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print("✓ Virtual environment exists")
    
    python_bin = VENV_DIR / "bin" / "python" if os.name != "nt" else VENV_DIR / "Scripts" / "python.exe"
    pip_bin = VENV_DIR / "bin" / "pip" if os.name != "nt" else VENV_DIR / "Scripts" / "pip.exe"
    
    # Check/install requests
    try:
        subprocess.run([pip_bin, "show", "requests"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("✓ requests library installed")
    except subprocess.CalledProcessError:
        print("[INFO] Installing requests library...")
        subprocess.check_call([pip_bin, "install", "requests"])
    
    # Check/install yt-dlp
    try:
        subprocess.run([pip_bin, "show", "yt-dlp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("✓ yt-dlp installed")
    except subprocess.CalledProcessError:
        print("[INFO] Installing yt-dlp...")
        subprocess.check_call([pip_bin, "install", "--upgrade", "yt-dlp"])
    
    # Upgrade pip silently
    print("[INFO] Ensuring pip is up-to-date...")
    subprocess.run([pip_bin, "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓ pip is up-to-date")
    
    print("\n[✓] All prerequisites checked and ready!\n")
    return str(python_bin)


def search_youtube(query, max_results=10):
    """Search DuckDuckGo for YouTube results."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)} site:youtube.com OR site:music.youtube.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"'
        raw_urls = re.findall(pattern, response.text)
        
        clean_urls, seen = [], set()
        for u in raw_urls:
            if u.startswith("//"):
                u = "https:" + u
            if "uddg=" in u:
                parsed = urllib.parse.urlparse(u)
                qs = urllib.parse.parse_qs(parsed.query)
                if "uddg" in qs:
                    u = urllib.parse.unquote(qs["uddg"][0])
            
            # Only keep YouTube domains
            if not ("youtube.com" in u or "youtu.be" in u):
                continue
            if u not in seen:
                seen.add(u)
                clean_urls.append(u)
            if len(clean_urls) >= max_results:
                break
        
        return clean_urls
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return []


def save_urls_to_file(urls):
    """Save URLs to urls.txt (overwrites existing file)."""
    with URLS_FILE.open("w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    print(f"[✓] Saved {len(urls)} URLs to {URLS_FILE}")


def get_download_options():
    """Ask user for download preferences."""
    print("\nDownload options:")
    print("1 - Audio only (MP3)")
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
        print("[ERROR] Invalid choice. Defaulting to audio only.")
        audio, video = True, False
    
    subtitles_choice = input("Download subtitles if available? (y/n): ").strip().lower()
    download_subtitles = subtitles_choice == "y"
    
    return audio, video, download_subtitles


def build_yt_dlp_command(python_bin, url, audio, video, download_subs):
    """Build yt-dlp command based on user preferences."""
    base_cmd = [python_bin, "-m", "yt_dlp"]
    
    if audio and not video:
        # Audio only (MP3)
        outtmpl = str(OUTPUT_AUDIO / "%(title)s.%(ext)s")
        cmd = base_cmd + [
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
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
        # Both (merged video+audio)
        outtmpl = str(OUTPUT_VIDEO / "%(title)s.%(ext)s")
        cmd = base_cmd + [
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", outtmpl
        ]
    else:
        raise ValueError("Invalid download options")
    
    cmd.append(url)
    return cmd


def download_media(python_bin, url, audio, video, download_subs):
    """Download media using yt-dlp."""
    if download_subs:
        # Download media first
        cmd_media = build_yt_dlp_command(python_bin, url, audio, video, False)
        print(f"[INFO] Downloading media...")
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
        print(f"[INFO] Downloading subtitles...")
        subprocess.run(cmd_subs, check=True)
    else:
        cmd = build_yt_dlp_command(python_bin, url, audio, video, False)
        print(f"[INFO] Downloading...")
        subprocess.run(cmd, check=True)


def main():
    print_header("YouTube Collector Agent")
    
    # Step 1: Prerequisites
    ensure_directories()
    python_bin = check_prerequisites()
    
    # Step 2: Search
    print_header("STEP 2: Search YouTube Content")
    query = input("🔍 Enter search query: ").strip()
    if not query:
        print("[ERROR] No query provided.")
        sys.exit(1)
    
    print(f"\n[INFO] Searching DuckDuckGo for: {query}")
    results = search_youtube(query, max_results=10)
    
    if not results:
        print("[ERROR] No YouTube results found.")
        sys.exit(1)
    
    print(f"\n[✓] Found {len(results)} YouTube results:")
    for idx, url in enumerate(results, 1):
        print(f"  {idx}. {url}")
    
    # Step 3: Save URLs
    print_header("STEP 3: Saving URLs")
    save_urls_to_file(results)
    
    # Step 4: Download
    print_header("STEP 4: Download Media")
    audio, video, download_subs = get_download_options()
    
    print(f"\n[INFO] Starting downloads for {len(results)} URLs...\n")
    
    for idx, url in enumerate(results, 1):
        print(f"\n--- [{idx}/{len(results)}] Processing: {url} ---")
        try:
            download_media(python_bin, url, audio, video, download_subs)
            print(f"[✓] Completed!")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Download failed: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
    
    # Final summary
    print_header("COMPLETE!")
    print(f"URLs saved to: {URLS_FILE}")
    print(f"Media saved to:\n  - Audio: {OUTPUT_AUDIO}\n  - Video: {OUTPUT_VIDEO}")
    if download_subs:
        print(f"  - Subtitles: {OUTPUT_SUBS}")
    print("\n")


if __name__ == "__main__":
    main()
