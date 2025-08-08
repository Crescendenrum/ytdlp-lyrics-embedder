import os
import sys
import re
import yt_dlp
from PIL import Image
from mutagen.mp4 import MP4, MP4Cover
import html
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, error
from mutagen.flac import FLAC, Picture
import argparse


# === CONFIGURATION ===

EXPORT_DIR = os.path.join(os.path.expandvars(r'%USERPROFILE%'), 'Music', 'yt_dlp_downloader')
os.makedirs(EXPORT_DIR, exist_ok=True)

ENABLE_EMBED_COVER = True
ENABLE_EMBED_LYRICS = True
ENABLE_CONVERT_WEBP = True
ENABLE_MOVE_FILES = True
ENABLE_CLEANUP = True

YDL_FORMAT = "m4a"  # audio format to extract & embed metadata into

SUBTITLE_LANGS = ['en']
SUBTITLE_FORMAT = 'vtt'

# === FUNCTIONS ===

def embed_metadata(file_path, jpg_path=None, lrc_path=None):
    ext = file_path.split('.')[-1].lower()
    try:
        if ext == 'm4a' or ext == 'mp4':
            audio = MP4(file_path)
            if jpg_path and os.path.exists(jpg_path):
                with open(jpg_path, 'rb') as img_file:
                    cover = MP4Cover(img_file.read(), imageformat=MP4Cover.FORMAT_JPEG)
                    audio["covr"] = [cover]
            if lrc_path and os.path.exists(lrc_path):
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                    audio["©lyr"] = [lyrics]
            audio.save()

        elif ext == 'mp3':
            audio = MP3(file_path, ID3=ID3)
            try:
                audio.add_tags()
            except error:
                pass
            if jpg_path and os.path.exists(jpg_path):
                with open(jpg_path, 'rb') as img_file:
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,  # cover(front)
                            desc='Cover',
                            data=img_file.read()
                        )
                    )
            if lrc_path and os.path.exists(lrc_path):
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                    audio.tags.add(
                        USLT(encoding=3, lang='eng', desc='Lyrics', text=lyrics)
                    )
            audio.save()

        elif ext == 'flac':
            audio = FLAC(file_path)
            if jpg_path and os.path.exists(jpg_path):
                with open(jpg_path, 'rb') as img_file:
                    pic = Picture()
                    pic.data = img_file.read()
                    pic.type = 3  # front cover
                    pic.mime = 'image/jpeg'
                    audio.clear_pictures()
                    audio.add_picture(pic)
            if lrc_path and os.path.exists(lrc_path):
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                    audio['lyrics'] = lyrics
            audio.save()

        else:
            print(f"⚠️ Unsupported format for embedding metadata: {ext}")
            return False

        return True
    except Exception as e:
        print(f"Error embedding metadata into {file_path}: {e}")
        return False


def convert_webp_to_jpg(title):
    if not ENABLE_CONVERT_WEBP:
        return None
    webp_path = f"{title}.webp"
    jpg_path = f"{title}.jpg"
    if os.path.exists(webp_path):
        try:
            img = Image.open(webp_path).convert("RGB")
            img.save(jpg_path, "JPEG")
            print(f"🖼️ Converted {webp_path} to {jpg_path}")
            return jpg_path
        except Exception as e:
            print(f"⚠️ Failed to convert thumbnail: {e}")
    else:
        print("ℹ️ No .webp thumbnail to convert.")
    return None


def clean_text(text):
    text = html.unescape(text)
    text = re.sub(r'<.*?>', '', text)
    text = text.replace('♪', '').strip()
    return text


def vtt_to_lrc(vtt_path):
    lrc_lines = []
    timestamp_re = re.compile(r'(\d+):(\d+):(\d+)\.(\d+) --> (\d+):(\d+):(\d+)\.(\d+)')
    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = timestamp_re.match(line)
        if match:
            h, m, s, ms = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            total_minutes = h * 60 + m
            ms_2d = int(ms / 10)
            time_tag = f"[{total_minutes:02d}:{s:02d}.{ms_2d:02d}]"
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() != '':
                cleaned_line = clean_text(lines[i].strip())
                if cleaned_line:
                    text_lines.append(cleaned_line)
                i += 1
            text = ' '.join(text_lines).strip()
            if text:
                lrc_lines.append(f"{time_tag}{text}")
        else:
            i += 1
    return "\n".join(lrc_lines)


def move_file_to_export(file_path):
    if not ENABLE_MOVE_FILES:
        return False
    if not file_path or not os.path.exists(file_path):
        print(f"ℹ️ File not found for moving: {file_path}")
        return False
    dest = os.path.join(EXPORT_DIR, os.path.basename(file_path))
    try:
        os.replace(file_path, dest)
        print(f"📁 Moved {file_path} to {dest}")
        return True
    except Exception as e:
        print(f"⚠️ Failed to move {file_path}: {e}")
        return False


def find_audio_file(title, ext):
    for file in os.listdir('.'):
        if file.startswith(title) and file.endswith(f".{ext}"):
            return file
    return None

def download_audio_and_subs(format, url, skip_subtitles=False, quality='medium'):
    # Map quality names to kbps values
    quality_map = {
        'low': '128',
        'medium': '192',
        'high': '320',
        'lossless': None  # FLAC will ignore this
    }

    # For lossless FLAC, skip re-encoding
    if format == 'flac' or quality == 'lossless':
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac'
        }]
        post_args = []
    else:
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
            'preferredquality': quality_map[quality]
        }]
        post_args = ['-ar', '44100']

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'postprocessors': postprocessors,
        'postprocessor_args': post_args,
        'writesubtitles': not skip_subtitles,
        'writeautomaticsub': not skip_subtitles,
        'subtitleslangs': SUBTITLE_LANGS if not skip_subtitles else [],
        'subtitlesformat': SUBTITLE_FORMAT,
        'writethumbnail': True,
        'quiet': False,
        'verbose': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'output')

    audio_file = find_audio_file(title, format)
    subtitle_file = None
    if not skip_subtitles:
        for file in os.listdir('.'):
            if file.startswith(title) and file.endswith('.en.vtt'):
                subtitle_file = file
                break
    return audio_file, subtitle_file, title



def cleanup_files(files):
    if not ENABLE_CLEANUP:
        return
    for f in files:
        if f and os.path.exists(f):
            try:
                os.remove(f)
                print(f"🗑️ Removed leftover file: {f}")
            except Exception as e:
                print(f"⚠️ Failed to remove {f}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download and embed metadata from YouTube audio/video.")
    
    parser.add_argument('format', type=str, choices=['m4a', 'mp3', 'flac', 'mp4'],
                        help='Audio/video format to download')
    
    parser.add_argument('urls', nargs='+', help='One or more YouTube URLs to process')
    
    parser.add_argument('--skip-subtitles', action='store_true',
                        help='Skip downloading and embedding subtitles')
    
    parser.add_argument('--quality', type=str,
                        choices=['low', 'medium', 'high', 'lossless'],
                        default='medium',
                        help='Audio quality: low (~128kbps), medium (~192kbps), high (~320kbps), '
                             'lossless (FLAC only, ignores kbps)')
    
    args = parser.parse_args()

    format = args.format.lower()
    urls = args.urls
    skip_subtitles = args.skip_subtitles
    quality = args.quality

    print(f"🎵 Format: {format}")
    print(f"⚙️ Skip subtitles: {skip_subtitles}")
    print(f"⚙️ Quality: {quality}")

    for url in urls:
        print(f"\n🔗 Processing URL: {url}")
        try:
            audio_path, subtitle_path, title = download_audio_and_subs(
                format, url, skip_subtitles=skip_subtitles, quality=quality
            )

            cover_jpg_path = convert_webp_to_jpg(title)

            lrc_file_path = None
            if not skip_subtitles and subtitle_path and os.path.exists(subtitle_path):
                print(f"📝 Converting {subtitle_path} to LRC...")
                lrc_text = vtt_to_lrc(subtitle_path)
                lrc_file_path = f"{title}.lrc"
                with open(lrc_file_path, 'w', encoding='utf-8') as f:
                    f.write(lrc_text)

            moved_audio = move_file_to_export(audio_path)
            moved_jpg = move_file_to_export(cover_jpg_path)
            moved_lrc = move_file_to_export(lrc_file_path)

            print(f"✅ Finished processing '{title}':")
            print(f"   - Audio moved: {'Yes' if moved_audio else 'No'}")
            print(f"   - JPG moved: {'Yes' if moved_jpg else 'No'}")
            print(f"   - LRC moved: {'Yes' if moved_lrc else 'No'}")

            moved_audio_path = os.path.join(EXPORT_DIR, os.path.basename(audio_path)) if audio_path else None
            moved_jpg_path = os.path.join(EXPORT_DIR, os.path.basename(cover_jpg_path)) if cover_jpg_path else None
            moved_lrc_path = os.path.join(EXPORT_DIR, os.path.basename(lrc_file_path)) if lrc_file_path else None

            if moved_audio_path and os.path.exists(moved_audio_path):
                success = embed_metadata(moved_audio_path, moved_jpg_path, moved_lrc_path)
                print(f"🎯 Embedding metadata into '{os.path.basename(moved_audio_path)}': {'Success' if success else 'Failed'}")
                if success:
                    cleanup_files([moved_jpg_path, moved_lrc_path])
            else:
                print("ℹ️ Skipping embedding since audio file not found in export folder.")

            leftover_files = [
                audio_path if not moved_audio else None,
                cover_jpg_path if not moved_jpg else None,
                lrc_file_path if not moved_lrc else None,
                subtitle_path if not skip_subtitles else None,
                f"{title}.webp"
            ]
            cleanup_files([f for f in leftover_files if f])

        except Exception as e:
            print(f"❌ Error processing {url}: {e}")

if __name__ == "__main__":
    main()
