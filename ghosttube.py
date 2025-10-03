#!/usr/bin/env python3
"""
YouTube Collector Agent with Tor Integration
Combines DuckDuckGo search + yt-dlp download with Tor identity rotation.
1. Checks prerequisites (including Tor)
2. Searches DuckDuckGo for YouTube content (via Tor)
3. Saves results to urls.txt (overwrites each run)
4. Downloads media with identity rotation before each download
"""

import os
import sys
import subprocess
import requests
import re
import urllib.parse
import time
from pathlib import Path
from urllib.parse import quote_plus
from stem import Signal
from stem.control import Controller

# --- Tor Configuration ---
TOR_PROXY = 'socks5://127.0.0.1:9050'
TOR_CONTROL_PORT = 9051
PROXIES = {'http': TOR_PROXY, 'https': TOR_PROXY}

# --- Working directories ---
SCRIPT_DIR = Path.cwd()
VENV_DIR = SCRIPT_DIR / ".venv"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_AUDIO = OUTPUT_DIR / "audio"
OUTPUT_VIDEO = OUTPUT_DIR / "video"
OUTPUT_TRANSCRIPTS = OUTPUT_DIR / "transcripts"
URLS_FILE = SCRIPT_DIR / "urls.txt"


def sanitize_query_for_dir(query):
    """Sanitize search query to create a valid directory name."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', query).replace(' ', '_').strip()
    if not sanitized:
        sanitized = "search_results"
    return sanitized


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def ensure_directories():
    """Create output and venv directories if they don't exist."""
    for directory in [VENV_DIR, OUTPUT_AUDIO, OUTPUT_VIDEO, OUTPUT_TRANSCRIPTS]:
        directory.mkdir(parents=True, exist_ok=True)


def get_current_ip():
    """Fetch current IP via Tor."""
    try:
        resp = requests.get('https://ident.me', proxies=PROXIES, timeout=10)
        return resp.text.strip()
    except Exception as e:
        return f"Error: {e}"


def renew_tor_identity():
    """Rotate Tor circuit for a new identity."""
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
            ctrl.authenticate()
            ctrl.signal(Signal.NEWNYM)
        time.sleep(5)  # Wait for new circuit to establish
        return True
    except Exception as e:
        print(f"  [WARNING] Identity rotation failed: {e}")
        return False


def check_tor_connection():
    """Verify Tor is running and accessible."""
    try:
        ip = get_current_ip()
        if "Error" in ip:
            return False, ip
        return True, ip
    except:
        return False, "Connection failed"


def check_prerequisites():
    """Check and install all prerequisites including Tor."""
    print_header("STEP 1: Checking Prerequisites")
    
    if sys.version_info < (3, 7):
        print("[ERROR] Python 3.7+ required")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check Tor connection
    print("\n[INFO] Checking Tor connection...")
    tor_ok, tor_ip = check_tor_connection()
    if not tor_ok:
        print("[ERROR] Cannot connect to Tor!")
        print("  Make sure Tor is running with:")
        print("    - SOCKS proxy on 127.0.0.1:9050")
        print("    - ControlPort 9051")
        print("    - CookieAuthentication 1")
        sys.exit(1)
    print(f"✓ Tor is running (IP: {tor_ip})")
    
    if not (VENV_DIR / "bin" / "python").exists() and not (VENV_DIR / "Scripts" / "python.exe").exists():
        print("\n[INFO] Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print("✓ Virtual environment exists")
    
    python_bin = VENV_DIR / "bin" / "python" if os.name != "nt" else VENV_DIR / "Scripts" / "python.exe"
    pip_bin = VENV_DIR / "bin" / "pip" if os.name != "nt" else VENV_DIR / "Scripts" / "pip.exe"
    
    # Check/install required packages
    required_packages = [
        ("requests[socks]", "requests"),
        ("stem", "stem"),
        ("yt-dlp", "yt-dlp")
    ]
    
    for install_name, check_name in required_packages:
        try:
            subprocess.run([pip_bin, "show", check_name], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"✓ {check_name} installed")
        except subprocess.CalledProcessError:
            print(f"[INFO] Installing {install_name}...")
            subprocess.check_call([pip_bin, "install", install_name])
    
    print("\n[INFO] Ensuring pip is up-to-date...")
    subprocess.run([pip_bin, "install", "--upgrade", "pip"], 
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓ pip is up-to-date")
    
    print("\n[✓] All prerequisites checked and ready!\n")
    return str(python_bin)


def search_youtube(query, max_results=10):
    """Search DuckDuckGo for YouTube results via Tor."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)} site:youtube.com OR site:music.youtube.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, proxies=PROXIES, timeout=30)
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
    """Overwrite urls.txt with current run results."""
    with URLS_FILE.open("w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    print(f"[✓] Saved {len(urls)} URLs to {URLS_FILE}")


def get_download_options():
    """Ask user for download preferences."""
    print("\nDownload options:")
    print("1 - Audio only (MP3)")
    print("2 - Video only (MP4)")
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
    
    transcripts_choice = input("Download transcripts if available? (y/n): ").strip().lower()
    download_transcripts = transcripts_choice == "y"
    
    return audio, video, download_transcripts


def download_media(python_bin, url, audio, video, download_transcripts,
                   audio_subdir, video_subdir, transcripts_subdir):
    """Download audio, video, and transcripts with yt-dlp via Tor."""

    # Base yt-dlp args for Tor proxy
    tor_args = ["--proxy", TOR_PROXY]

    if audio and video:
        # Download audio separately
        cmd_audio = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", str(audio_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd_audio, check=True)

        # Download video separately
        cmd_video = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", str(video_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd_video, check=True)

    elif audio:
        cmd = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", str(audio_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd, check=True)

    elif video:
        cmd = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", str(video_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd, check=True)

    if download_transcripts:
        cmd_transcript = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--convert-subs", "txt",
            "-o", str(transcripts_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd_transcript, check=True)


def main():
    print_header("YouTube Collector Agent with Tor")
    
    ensure_directories()
    python_bin = check_prerequisites()
    
    print_header("STEP 2: Search YouTube Content")
    query = input("🔍 Enter search query: ").strip()
    if not query:
        print("[ERROR] No query provided.")
        sys.exit(1)
    
    query_dir = sanitize_query_for_dir(query)
    AUDIO_SUBDIR = OUTPUT_AUDIO / query_dir
    VIDEO_SUBDIR = OUTPUT_VIDEO / query_dir
    TRANSCRIPTS_SUBDIR = OUTPUT_TRANSCRIPTS / query_dir
    for subdir in [AUDIO_SUBDIR, VIDEO_SUBDIR, TRANSCRIPTS_SUBDIR]:
        subdir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[INFO] Searching DuckDuckGo via Tor for: {query}")
    print(f"[INFO] Downloads will go into subfolders named '{query_dir}'")
    results = search_youtube(query, max_results=10)
    
    if not results:
        print("[ERROR] No YouTube results found.")
        sys.exit(1)
    
    print(f"\n[✓] Found {len(results)} YouTube results:")
    for idx, url in enumerate(results, 1):
        print(f"  {idx}. {url}")
    
    print_header("STEP 3: Saving URLs")
    save_urls_to_file(results)
    
    print_header("STEP 4: Download Media with Identity Rotation")
    audio, video, download_transcripts = get_download_options()
    
    print(f"\n[INFO] Starting downloads for {len(results)} URLs...")
    print("[INFO] Rotating Tor identity before each download...\n")
    
    for idx, url in enumerate(results, 1):
        print(f"\n--- [{idx}/{len(results)}] ---")
        
        # Rotate Tor identity before each download
        print("🔄 Rotating Tor identity...")
        old_ip = get_current_ip()
        if renew_tor_identity():
            new_ip = get_current_ip()
            print(f"  Old IP: {old_ip}")
            print(f"  New IP: {new_ip}")
            print(f"  ✓ Identity changed: {new_ip != old_ip}")
        else:
            print("  [WARNING] Proceeding with current identity")
        
        print(f"\n📥 Downloading: {url}")
        try:
            download_media(python_bin, url, audio, video, download_transcripts,
                           AUDIO_SUBDIR, VIDEO_SUBDIR, TRANSCRIPTS_SUBDIR)
            print(f"[✓] Download completed!")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Download failed: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
    
    print_header("COMPLETE!")
    print(f"URLs saved to: {URLS_FILE}")
    print(f"Media saved to:\n  - Audio: {AUDIO_SUBDIR}\n  - Video: {VIDEO_SUBDIR}")
    if download_transcripts:
        print(f"  - Transcripts: {TRANSCRIPTS_SUBDIR}")
    print("\nAll downloads completed with Tor identity rotation!")
    print("\n")


if __name__ == "__main__":
    main()
