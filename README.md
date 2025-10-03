# yt-dlp-media-ripper.py
Python script that automates media downloads with yt-dlp, creating a local virtual environment if missing. Supports batch URLs from a TXT file , audio-only (WAV), video, or merged MP4, with optional subtitles. Organizes output into audio, video, and subtitle folders for clean, structured storage.



GhostTube: Anonymous YouTube Collector Agent![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Tor Integration](https://img.shields.io/badge/Tor-Enabled-green.svg)GhostTube is a privacy-focused Python script that automates searching DuckDuckGo for YouTube content and downloading media (audio, video, or transcripts) using yt-dlp. It routes everything through Tor for anonymity, with automatic identity rotation every 10 downloads to evade tracking—perfect for users who want to stay off Big Brother's radar without doing anything shady.Coded identity switching through Tor: The script automatically rotates your Tor identity every 10 downloads to boost anonymity and evade potential tracking. Note that initial setup is required—install Tor (pkg install tor in Termux), start the daemon (nohup tor -f $PREFIX/etc/tor/torrc > tor.log 2>&1 &), and uncomment the two key lines in the torrc file to enable the control interface: ControlPort 9051 (opens port 9051 for Stem to send rotation signals) and CookieAuthentication 1 (enables secure local cookie-based auth for those signals). You can do this manually with Nano (nano $PREFIX/etc/tor/torrc, then jump to lines 57 and 61 with Ctrl+_, delete the leading # on each, save with Ctrl+O/Enter, and exit with Ctrl+X), or via sed commands (sed -i '57s/^#//' $PREFIX/etc/tor/torrc and sed -i '61s/^#//' $PREFIX/etc/tor/torrc)—but the script now automates this process (including torrc edits and daemon launch) in Termux/Android environments for seamless one-click operation.Tested on Termux (Android) as of October 03, 2025—runs headless, no root needed. Your ISP sees only Tor traffic, not your downloads.FeaturesPrivacy-First: All searches and downloads proxied through Tor; auto-rotates circuits every 10 downloads.
Smart Search: Uses DuckDuckGo (via Tor) to find YouTube videos, filters to 10 results max.
Flexible Downloads: Audio (MP3), video (MP4), both, or transcripts—your call.
Organized Output: Saves URLs to urls.txt; media in output/{type}/{sanitized_query}/.
Auto-Setup: Handles venv, deps (yt-dlp, requests[socks], stem), and Tor in Termux.
Error-Resilient: Graceful fallbacks for flaky Tor or failed downloads.

Quick Start (Termux on Android)Install Dependencies:

pkg update && pkg install python tor nano sed
pip install requests[socks] stem yt-dlp  # Or let the script handle it

Run the Script:

chmod +x ghosttube.py
./ghosttube.py

Enter a query (e.g., "lofi beats").
Choose download type (1=Audio, 2=Video, 3=Both).
Watch it search via Tor, rotate identities, and download.

The script auto-checks/sets up Tor (installs if missing, edits torrc, launches daemon). If it fails, manual fallback: See Tor Setup (#tor-setup) below.Usage

./ghosttube.py

Step 1: Prerequisites (auto-runs Tor setup, installs deps).
Step 2: Enter search query → Gets 10 YouTube URLs via Tor DDG search.
Step 3: Saves URLs to urls.txt.
Step 4: Pick options → Downloads with rotation every 10 (logs old/new IPs for verification).

Example output:

[INFO] Rotating Tor identity...
  Old IP: 185.220.101.108
  New IP: 2001:67c:289c:2::36
  ✓ Identity changed: True

📥 Downloading: https://www.youtube.com/watch?v=example
[✓] Download completed!

Tor Setup (Manual, if Auto Fails)Tor is key for privacy—your ISP can't snoop content. In Termux:Install: pkg install tor
Edit torrc (uncomment lines 57 & 61 for control port):Nano: nano $PREFIX/etc/tor/torrc → Ctrl+_ → 57 → Delete # → Repeat for 61 → Ctrl+O/Enter → Ctrl+X.
Or Sed: 

sed -i '57s/^#//' $PREFIX/etc/tor/torrc
sed -i '61s/^#//' $PREFIX/etc/tor/torrc

Start: pkill tor && nohup tor -f $PREFIX/etc/tor/torrc > tor.log 2>&1 &
Verify: netstat -tlnp | grep 905 (both 9050 & 9051 should listen). Test IP: curl --socks5 127.0.0.1:9050 https://ident.me

Logs: tail -f tor.log (look for "Bootstrapped 100%" and "Opening Control listener").TroubleshootingTor Connection Refused: Restart daemon; check torrc lines aren't commented.
Slow Downloads: Tor latency—normal on mobile; try WiFi.
No Results: DDG blocks some Tor exits; rotate manually (renew_tor_identity() in script).
Deps Fail: Run pip install --upgrade pip in venv.
Windows/macOS: Manual Tor install (e.g., Homebrew brew install tor); script adapts paths.

Privacy NotesTor hides your activity from ISPs/sites, but:Use HTTPS everywhere.
Rotate often for bulk downloads.
Legal: Fine for personal use; respect YouTube ToS.

ContributingFork, PR, or issues welcome! Focus: More formats, playlist support, or VPN chaining.LicenseMIT—free as in beer (and speech). See LICENSE.Built with  for privacy warriors. Questions? Open an issue.

