#!/usr/bin/env python3
"""
YouTube Collector Agent with Tor Integration

A comprehensive YouTube content collector that combines DuckDuckGo search with 
yt-dlp downloads, all routed through Tor for privacy and anonymity.

Workflow:
    1. Checks system prerequisites (Python, Tor, required packages)
    2. Searches DuckDuckGo for YouTube content via Tor proxy
    3. Saves discovered URLs to urls.txt (overwrites on each run)
    4. Downloads media with automatic Tor identity rotation before each download
    5. Creates subdirectories conditionally based on user selections

Features:
    - Multiple audio format support (MP3, AAC, FLAC, WAV, OGG, Opus, M4A, custom)
    - Video download in MP4 format
    - Optional transcript extraction
    - Tor identity rotation for enhanced privacy
    - Organized output structure with query-based subdirectories

Requirements:
    - Python 3.7+
    - Tor service running with:
        * SOCKS proxy on 127.0.0.1:9050
        * ControlPort 9051
        * CookieAuthentication enabled
    - Internet connection
    - Sufficient disk space for downloads

Author: YouTube Collector Agent
Version: 2.0
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

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Tor proxy configuration for routing all traffic through Tor network
TOR_PROXY = 'socks5://127.0.0.1:9050'  # SOCKS5 proxy address
TOR_CONTROL_PORT = 9051                 # Port for Tor control commands
PROXIES = {
    'http': TOR_PROXY,   # Route HTTP traffic through Tor
    'https': TOR_PROXY   # Route HTTPS traffic through Tor
}

# Directory structure for the application
SCRIPT_DIR = Path.cwd()                              # Current working directory
VENV_DIR = SCRIPT_DIR / ".venv"                     # Python virtual environment
OUTPUT_DIR = SCRIPT_DIR / "output"                  # Root output directory
OUTPUT_AUDIO = OUTPUT_DIR / "audio"                 # Audio files storage
OUTPUT_VIDEO = OUTPUT_DIR / "video"                 # Video files storage
OUTPUT_TRANSCRIPTS = OUTPUT_DIR / "transcripts"     # Transcript files storage
URLS_FILE = SCRIPT_DIR / "urls.txt"                 # URL collection file


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sanitize_query_for_dir(query):
    """
    Sanitize a search query string to create a valid directory name.
    
    Removes or replaces characters that are invalid in directory names across
    different operating systems (Windows, macOS, Linux).
    
    Args:
        query (str): The raw search query string from user input
        
    Returns:
        str: A sanitized string safe for use as a directory name
        
    Example:
        >>> sanitize_query_for_dir("Kiss: Greatest Hits")
        'Kiss_Greatest_Hits'
    """
    # Remove invalid filesystem characters: < > : " / \ | ? *
    sanitized = re.sub(r'[<>:"/\\|?*]', '', query)
    
    # Replace spaces with underscores for cleaner directory names
    sanitized = sanitized.replace(' ', '_').strip()
    
    # Fallback to generic name if sanitization removes everything
    if not sanitized:
        sanitized = "search_results"
    
    return sanitized


def print_header(text):
    """
    Print a formatted section header for better terminal output readability.
    
    Creates a visually distinct header with equal signs border to separate
    different stages of the script execution.
    
    Args:
        text (str): The header text to display
        
    Example output:
        ============================================================
          STEP 1: Checking Prerequisites
        ============================================================
    """
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def ensure_directories():
    """
    Create necessary directories if they don't exist.
    
    Ensures the virtual environment and all output directories are created
    with proper parent directory structure. Uses exist_ok=True to avoid
    errors if directories already exist.
    
    Directories created:
        - .venv/              (virtual environment)
        - output/audio/       (audio downloads)
        - output/video/       (video downloads)
        - output/transcripts/ (transcript files)
    """
    for directory in [VENV_DIR, OUTPUT_AUDIO, OUTPUT_VIDEO, OUTPUT_TRANSCRIPTS]:
        directory.mkdir(parents=True, exist_ok=True)


# ============================================================================
# TOR NETWORK FUNCTIONS
# ============================================================================

def get_current_ip():
    """
    Fetch the current public IP address via Tor proxy.
    
    Makes a request to ident.me service through Tor to determine the current
    exit node's IP address. Useful for verifying Tor connectivity and 
    confirming identity changes after rotation.
    
    Returns:
        str: Current public IP address, or error message if request fails
        
    Example:
        >>> get_current_ip()
        '185.220.101.52'
    """
    try:
        resp = requests.get('https://ident.me', proxies=PROXIES, timeout=10)
        return resp.text.strip()
    except Exception as e:
        return f"Error: {e}"


def renew_tor_identity():
    """
    Request a new Tor circuit to rotate the public IP address.
    
    Sends a NEWNYM signal to the Tor controller, which causes Tor to establish
    a new circuit with a different exit node. This provides a fresh IP address
    for enhanced privacy between downloads.
    
    Returns:
        bool: True if identity rotation succeeded, False otherwise
        
    Note:
        Waits 5 seconds after sending signal to allow new circuit to establish.
        Requires Tor ControlPort to be accessible and authentication to succeed.
    """
    try:
        # Connect to Tor control port and authenticate
        with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
            ctrl.authenticate()
            
            # Request new identity (new circuit/exit node)
            ctrl.signal(Signal.NEWNYM)
        
        # Wait for new circuit to establish before proceeding
        time.sleep(5)
        return True
        
    except Exception as e:
        print(f"  [WARNING] Identity rotation failed: {e}")
        return False


def check_tor_connection():
    """
    Verify that Tor is running and accessible.
    
    Attempts to fetch the current IP through Tor proxy to confirm:
        1. Tor service is running
        2. SOCKS proxy is accessible
        3. Network connectivity through Tor works
    
    Returns:
        tuple: (success: bool, ip_or_error: str)
            - (True, "IP address") if Tor is working
            - (False, "error message") if Tor is not accessible
    """
    try:
        ip = get_current_ip()
        
        # Check if the IP fetch returned an error
        if "Error" in ip:
            return False, ip
            
        return True, ip
        
    except:
        return False, "Connection failed"


# ============================================================================
# SYSTEM PREREQUISITES CHECK
# ============================================================================

def check_prerequisites():
    """
    Verify and setup all system prerequisites for the script.
    
    This function performs a comprehensive check of the runtime environment:
        1. Python version verification (3.7+ required)
        2. Tor connectivity test
        3. Virtual environment creation/verification
        4. Required Python package installation
        5. pip upgrade to latest version
    
    Returns:
        str: Path to the Python binary in the virtual environment
        
    Exits:
        Terminates script if Python version is too old or Tor is unavailable
        
    Packages installed/verified:
        - requests[socks]: HTTP library with SOCKS proxy support
        - stem: Python library for Tor control
        - yt-dlp: YouTube download utility
    """
    print_header("STEP 1: Checking Prerequisites")
    
    # ---- Python Version Check ----
    if sys.version_info < (3, 7):
        print("[ERROR] Python 3.7+ required")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # ---- Tor Connection Check ----
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
    
    # ---- Virtual Environment Setup ----
    # Check for venv existence (cross-platform: Unix uses bin/, Windows uses Scripts/)
    venv_exists = (
        (VENV_DIR / "bin" / "python").exists() or 
        (VENV_DIR / "Scripts" / "python.exe").exists()
    )
    
    if not venv_exists:
        print("\n[INFO] Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print("✓ Virtual environment exists")
    
    # Determine correct paths for current OS
    if os.name != "nt":  # Unix-like (Linux, macOS)
        python_bin = VENV_DIR / "bin" / "python"
        pip_bin = VENV_DIR / "bin" / "pip"
    else:  # Windows
        python_bin = VENV_DIR / "Scripts" / "python.exe"
        pip_bin = VENV_DIR / "Scripts" / "pip.exe"
    
    # ---- Package Installation Check ----
    # Format: (package_name_for_install, package_name_for_verification)
    required_packages = [
        ("requests[socks]", "requests"),  # HTTP with SOCKS support
        ("stem", "stem"),                  # Tor controller
        ("yt-dlp", "yt-dlp")              # YouTube downloader
    ]
    
    for install_name, check_name in required_packages:
        try:
            # Check if package is already installed
            subprocess.run(
                [pip_bin, "show", check_name], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                check=True
            )
            print(f"✓ {check_name} installed")
            
        except subprocess.CalledProcessError:
            # Package not found, install it
            print(f"[INFO] Installing {install_name}...")
            subprocess.check_call([pip_bin, "install", install_name])
    
    # ---- pip Update ----
    print("\n[INFO] Ensuring pip is up-to-date...")
    subprocess.run(
        [pip_bin, "install", "--upgrade", "pip"], 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
    print("✓ pip is up-to-date")
    
    print("\n[✓] All prerequisites checked and ready!\n")
    return str(python_bin)


# ============================================================================
# SEARCH FUNCTIONS
# ============================================================================

def search_youtube(query, max_results=10):
    """
    Search DuckDuckGo for YouTube content via Tor proxy.
    
    Performs a web search on DuckDuckGo specifically targeting YouTube URLs.
    All requests are routed through Tor for privacy. Handles URL extraction
    and cleaning from DuckDuckGo's HTML response.
    
    Args:
        query (str): The search query string
        max_results (int): Maximum number of YouTube URLs to return (default: 10)
        
    Returns:
        list: List of clean YouTube URLs found in search results
              Empty list if search fails or no results found
              
    Example:
        >>> search_youtube("Pink Floyd concerts", max_results=5)
        ['https://www.youtube.com/watch?v=...', ...]
        
    Note:
        - Searches both youtube.com and music.youtube.com
        - Deduplicates results
        - Handles DuckDuckGo's URL obfuscation (uddg parameter)
    """
    # Construct DuckDuckGo search URL with site restriction
    search_url = (
        f"https://html.duckduckgo.com/html/"
        f"?q={quote_plus(query)} site:youtube.com OR site:music.youtube.com"
    )
    
    # Use a common browser user agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        # Make search request through Tor proxy
        response = requests.get(
            search_url, 
            headers=headers, 
            proxies=PROXIES, 
            timeout=30
        )
        response.raise_for_status()
        
        # Extract URLs from search result HTML
        # Pattern matches DuckDuckGo's result link class
        pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"'
        raw_urls = re.findall(pattern, response.text)
        
        # Process and clean URLs
        clean_urls = []
        seen = set()  # Track URLs to prevent duplicates
        
        for url in raw_urls:
            # Handle protocol-relative URLs
            if url.startswith("//"):
                url = "https:" + url
            
            # DuckDuckGo wraps URLs in a redirect - extract the actual URL
            if "uddg=" in url:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                
                if "uddg" in qs:
                    # Decode the actual YouTube URL from the uddg parameter
                    url = urllib.parse.unquote(qs["uddg"][0])
            
            # Filter: only keep YouTube URLs
            if not ("youtube.com" in url or "youtu.be" in url):
                continue
            
            # Add unique URLs only
            if url not in seen:
                seen.add(url)
                clean_urls.append(url)
            
            # Stop when we have enough results
            if len(clean_urls) >= max_results:
                break
        
        return clean_urls
        
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return []


def save_urls_to_file(urls):
    """
    Save discovered YouTube URLs to urls.txt file.
    
    Overwrites the urls.txt file with the current search results. Each URL
    is written on a separate line for easy reading and processing.
    
    Args:
        urls (list): List of YouTube URLs to save
        
    Side effects:
        - Creates or overwrites urls.txt in script directory
        - Prints confirmation message with URL count
        
    Example:
        >>> save_urls_to_file(['https://youtube.com/watch?v=abc', ...])
        [✓] Saved 10 URLs to /path/to/urls.txt
    """
    with URLS_FILE.open("w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    
    print(f"[✓] Saved {len(urls)} URLs to {URLS_FILE}")


# ============================================================================
# USER INPUT FUNCTIONS
# ============================================================================

def get_audio_format():
    """
    Prompt user to select their preferred audio format for downloads.
    
    Displays a menu of common audio formats plus a custom option. Handles
    invalid input by defaulting to MP3. Pressing Enter without input also
    defaults to MP3.
    
    Returns:
        str: Audio format code (e.g., 'mp3', 'flac', 'wav')
        
    Supported formats:
        1. MP3  - Universal compatibility, good compression
        2. AAC  - Modern, efficient compression
        3. FLAC - Lossless, large file size
        4. WAV  - Uncompressed, studio quality
        5. OGG  - Open source alternative
        6. Opus - Best for voice/speech
        7. M4A  - Apple/iTunes standard
        8. Custom - User enters any format code
        
    Example interaction:
        Choose format (1-8, or press Enter for MP3): 3
        [INFO] Selected format: FLAC
    """
    print("\n🎵 Select Audio Format:")
    print("1 - MP3 (default - universal compatibility)")
    print("2 - AAC (modern, efficient)")
    print("3 - FLAC (lossless, archival quality)")
    print("4 - WAV (uncompressed, studio quality)")
    print("5 - OGG (open source)")
    print("6 - Opus (best for voice/speech)")
    print("7 - M4A (Apple/iTunes standard)")
    print("8 - Custom (enter your own format)")
    
    choice = input("Choose format (1-8, or press Enter for MP3): ").strip()
    
    # Map menu choices to format codes
    formats = {
        "1": "mp3",
        "2": "aac",
        "3": "flac",
        "4": "wav",
        "5": "ogg",
        "6": "opus",
        "7": "m4a",
        "8": None  # Custom format flag
    }
    
    # Handle empty input (default to MP3)
    if choice == "":
        print("[INFO] Using default format: MP3")
        return "mp3"
    
    # Handle custom format entry
    elif choice == "8":
        custom = input("Enter custom format (e.g., alac, wma, etc.): ").strip().lower()
        
        if custom:
            print(f"[INFO] Using custom format: {custom.upper()}")
            return custom
        else:
            print("[INFO] No format entered, defaulting to MP3")
            return "mp3"
    
    # Handle numbered menu choices
    elif choice in formats:
        selected = formats[choice]
        print(f"[INFO] Selected format: {selected.upper()}")
        return selected
    
    # Handle invalid input
    else:
        print("[WARNING] Invalid choice. Defaulting to MP3")
        return "mp3"


def get_download_options():
    """
    Prompt user for download preferences (audio, video, transcripts).
    
    Presents a menu for selecting download types and conditionally prompts
    for audio format if audio download is selected. Also asks whether to
    download transcripts.
    
    Returns:
        tuple: (audio: bool, video: bool, download_transcripts: bool, audio_format: str)
            - audio: True if audio should be downloaded
            - video: True if video should be downloaded
            - download_transcripts: True if transcripts should be downloaded
            - audio_format: Audio format code (only relevant if audio=True)
            
    Example interaction:
        Download options:
        1 - Audio only
        2 - Video only (MP4)
        3 - Both audio and video
        Choose 1, 2 or 3: 1
        
        [Audio format menu appears]
        
        Download transcripts if available? (y/n): y
    """
    print("\nDownload options:")
    print("1 - Audio only")
    print("2 - Video only (MP4)")
    print("3 - Both audio and video")
    choice = input("Choose 1, 2 or 3: ").strip()
    
    # Parse user choice into boolean flags
    if choice == "1":
        audio, video = True, False
    elif choice == "2":
        audio, video = False, True
    elif choice == "3":
        audio, video = True, True
    else:
        print("[ERROR] Invalid choice. Defaulting to audio only.")
        audio, video = True, False
    
    # Ask for audio format only if audio download is selected
    audio_format = "mp3"  # Default
    if audio:
        audio_format = get_audio_format()
    
    # Ask about transcript downloads
    transcripts_choice = input("Download transcripts if available? (y/n): ").strip().lower()
    download_transcripts = transcripts_choice == "y"
    
    return audio, video, download_transcripts, audio_format


# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================

def download_media(python_bin, url, audio, video, download_transcripts,
                   audio_subdir, video_subdir, transcripts_subdir, audio_format="mp3"):
    """
    Download audio, video, and/or transcripts from YouTube using yt-dlp.
    
    Constructs and executes yt-dlp commands based on user preferences. All
    downloads are routed through Tor proxy for privacy. Handles three scenarios:
        1. Audio only
        2. Video only
        3. Both audio and video (downloaded separately)
        
    Args:
        python_bin (str): Path to Python binary in virtual environment
        url (str): YouTube URL to download
        audio (bool): Whether to download audio
        video (bool): Whether to download video
        download_transcripts (bool): Whether to download transcripts
        audio_subdir (Path): Directory for audio files (or None)
        video_subdir (Path): Directory for video files (or None)
        transcripts_subdir (Path): Directory for transcripts (or None)
        audio_format (str): Audio format code (default: 'mp3')
        
    Raises:
        subprocess.CalledProcessError: If yt-dlp command fails
        
    Note:
        - Audio quality is set to 0 (best available)
        - Video format is bestvideo+bestaudio merged to MP4
        - Transcripts are auto-generated English subtitles converted to TXT
        - All network traffic routes through Tor proxy
    """
    # Base arguments for all yt-dlp commands (Tor proxy)
    tor_args = ["--proxy", TOR_PROXY]

    # ---- Scenario 1: Both Audio and Video ----
    if audio and video:
        # Download audio separately with format conversion
        cmd_audio = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-x",                           # Extract audio
            "--audio-format", audio_format, # Convert to specified format
            "--audio-quality", "0",         # Best quality
            "-o", str(audio_subdir / "%(title)s.%(ext)s"),  # Output template
            url
        ]
        subprocess.run(cmd_audio, check=True)

        # Download video separately
        cmd_video = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-f", "bestvideo+bestaudio",    # Best quality video + audio
            "--merge-output-format", "mp4", # Merge to MP4 container
            "-o", str(video_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd_video, check=True)

    # ---- Scenario 2: Audio Only ----
    elif audio:
        cmd = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "-x",                           # Extract audio
            "--audio-format", audio_format,
            "--audio-quality", "0",
            "-o", str(audio_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd, check=True)

    # ---- Scenario 3: Video Only ----
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

    # ---- Optional: Download Transcripts ----
    if download_transcripts:
        cmd_transcript = [
            python_bin, "-m", "yt_dlp",
            *tor_args,
            "--skip-download",      # Don't download media
            "--write-auto-sub",     # Get auto-generated subtitles
            "--sub-lang", "en",     # English subtitles
            "--convert-subs", "txt",# Convert to plain text
            "-o", str(transcripts_subdir / "%(title)s.%(ext)s"),
            url
        ]
        subprocess.run(cmd_transcript, check=True)


# ============================================================================
# MAIN EXECUTION FLOW
# ============================================================================

def main():
    """
    Main execution function orchestrating the entire workflow.
    
    Workflow steps:
        1. Setup: Create directories and check prerequisites
        2. Search: Get user query and search DuckDuckGo via Tor
        3. Save: Store URLs to urls.txt
        4. Configure: Get user preferences for downloads
        5. Download: Process each URL with Tor identity rotation
        6. Complete: Display summary of downloaded content
        
    The function handles user interaction, error reporting, and coordinates
    all the helper functions to perform the complete collection workflow.
    """
    print_header("YouTube Collector Agent with Tor")
    
    # ---- Step 1: Setup ----
    ensure_directories()
    python_bin = check_prerequisites()
    
    # ---- Step 2: Search ----
    print_header("STEP 2: Search YouTube Content")
    query = input("🔍 Enter search query: ").strip()
    
    if not query:
        print("[ERROR] No query provided.")
        sys.exit(1)
    
    # Create query-based subdirectory name
    query_dir = sanitize_query_for_dir(query)
    
    print(f"\n[INFO] Searching DuckDuckGo via Tor for: {query}")
    print(f"[INFO] Downloads will go into subfolders named '{query_dir}'")
    
    results = search_youtube(query, max_results=10)
    
    if not results:
        print("[ERROR] No YouTube results found.")
        sys.exit(1)
    
    # Display found URLs
    print(f"\n[✓] Found {len(results)} YouTube results:")
    for idx, url in enumerate(results, 1):
        print(f"  {idx}. {url}")
    
    # ---- Step 3: Save URLs ----
    print_header("STEP 3: Saving URLs")
    save_urls_to_file(results)
    
    # ---- Step 4: Configure Downloads ----
    print_header("STEP 4: Download Media with Identity Rotation")
    audio, video, download_transcripts, audio_format = get_download_options()
    
    # Create subdirectories only for selected options
    AUDIO_SUBDIR = OUTPUT_AUDIO / query_dir if audio else None
    VIDEO_SUBDIR = OUTPUT_VIDEO / query_dir if video else None
    TRANSCRIPTS_SUBDIR = OUTPUT_TRANSCRIPTS / query_dir if download_transcripts else None
    
    # Create directories that will be used
    if AUDIO_SUBDIR:
        AUDIO_SUBDIR.mkdir(parents=True, exist_ok=True)
    if VIDEO_SUBDIR:
        VIDEO_SUBDIR.mkdir(parents=True, exist_ok=True)
    if TRANSCRIPTS_SUBDIR:
        TRANSCRIPTS_SUBDIR.mkdir(parents=True, exist_ok=True)
    
    # ---- Step 5: Download with Identity Rotation ----
    print(f"\n[INFO] Starting downloads for {len(results)} URLs...")
    print("[INFO] Rotating Tor identity before each download...\n")
    
    for idx, url in enumerate(results, 1):
        print(f"\n--- [{idx}/{len(results)}] ---")
        
        # Rotate Tor identity for privacy
        print("🔄 Rotating Tor identity...")
        old_ip = get_current_ip()
        
        if renew_tor_identity():
            new_ip = get_current_ip()
            print(f"  Old IP: {old_ip}")
            print(f"  New IP: {new_ip}")
            print(f"  ✓ Identity changed: {new_ip != old_ip}")
        else:
            print("  [WARNING] Proceeding with current identity")
        
        # Download the content
        print(f"\n📥 Downloading: {url}")
        try:
            download_media(
                python_bin, url, audio, video, download_transcripts,
                AUDIO_SUBDIR, VIDEO_SUBDIR, TRANSCRIPTS_SUBDIR, audio_format
            )
            print(f"[✓] Download completed!")
            
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Download failed: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
    
    # ---- Step 6: Completion Summary ----
    print_header("COMPLETE!")
    print(f"URLs saved to: {URLS_FILE}")
    print(f"Media saved to:")
    
    # Show only directories that were actually used
    if audio:
        print(f"  - Audio: {AUDIO_SUBDIR}")
    if video:
        print(f"  - Video: {VIDEO_SUBDIR}")
    if download_transcripts:
        print(f"  - Transcripts: {TRANSCRIPTS_SUBDIR}")
    
    print("\nAll downloads completed with Tor identity rotation!")
    print("\n")


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
