# ytdlp-lyrics-embedder
A simple Python script using yt-dlp to download music from YouTube with embedded real-time lyrics and cover art.

# Notes
Downloads audio in your preferred format (m4a, mp3, flac)
Automatically downloads and converts English subtitles into synced lyrics (LRC format)
Embeds lyrics and cover art into the audio file metadata
Moves finished files to your Music folder (~/Music)
Converts thumbnails from WebP to JPEG if needed


Install Depencies First
```
pip install mutagen yt-dlp pillow
```

Usage:
```
download.py m4a "URL"
download.py mp3 "URL"
download.py flac "URL"
```
