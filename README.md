Basic ytdlp-lyrics-embedder
Download music from YouTube with embedded cover art and real-time synced lyrics.
Powered by yt-dlp + mutagen + Pillow.

Install dependencies:
pip install mutagen yt-dlp pillow

Basic examples:

```
python export.py m4a "https://youtube.com/..."
python export.py mp3 "https://youtube.com/..."
python export.py flac "https://youtube.com/..."
```

With options:

```
# High quality MP3
python export.py mp3 --quality high "https://youtube.com/..."

# FLAC (lossless)
python export.py flac --quality lossless "https://youtube.com/..."

# Skip subtitles
python export.py m4a --skip-subtitles "https://youtube.com/..."
```

Quality Options
Option	Bitrate / Quality Target	Notes
low	~128 kbps	Fastest download
medium	~192 kbps (default)	Good balance
high	~320 kbps	Highest lossy quality
lossless	FLAC	Ignored for non-FLAC
