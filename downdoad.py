import os
import sys
import re
import yt_dlp
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, USLT, APIC
from mutagen.flac import FLAC, Picture


def find_audio_file(title, ext):
    for file in os.listdir('.'):
        if file.startswith(title) and file.endswith(f".{ext}"):
            return file
    return None

from PIL import Image

def convert_webp_to_jpg(title):
    webp_path = f"{title}.webp"
    jpg_path = f"{title}.jpg"
    if os.path.exists(webp_path):
        try:
            img = Image.open(webp_path).convert("RGB")
            img.save(jpg_path, "JPEG")
            print(f"🖼️ Converted {webp_path} to {jpg_path}")
        except Exception as e:
            print(f"⚠️ Failed to convert thumbnail: {e}")

EXPORT_DIR = os.path.join(os.path.expanduser("~"), "Music", "Export")
os.makedirs(EXPORT_DIR, exist_ok=True)

def move_to_export(audio_path):
    dest_audio = os.path.join(EXPORT_DIR, os.path.basename(audio_path))
    try:
        os.replace(audio_path, dest_audio)
        print(f"📁 Moved audio to: {dest_audio}")
    except Exception as e:
        print(f"⚠️ Failed to move audio: {e}")
        dest_audio = audio_path

    # Move cover art if it exists
    cover_path = os.path.splitext(audio_path)[0] + '.jpg'
    if os.path.exists(cover_path):
        dest_cover = os.path.join(EXPORT_DIR, os.path.basename(cover_path))
        try:
            os.replace(cover_path, dest_cover)
            print(f"🖼️ Moved cover art to: {dest_cover}")
        except Exception as e:
            print(f"⚠️ Failed to move cover art: {e}")

    return dest_audio


def download_audio_and_subs(format, url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'final_ext': format,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
            'preferredquality': '192',
        }],
        'postprocessor_args': ['-ar', '44100'],
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'subtitlesformat': 'vtt',
        'embedthumbnail': True,
        'writethumbnail': True,
        'prefer_ffmpeg': True,
        'quiet': False,
        'verbose': True,
        'no_warnings': True,
        
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'output')
        audio_filename = find_audio_file(title, format)

        # Fallback: scan for subtitle file manually
        subtitle_filename = None
        for file in os.listdir('.'):
            if file.startswith(title) and file.endswith('.en.vtt'):
                subtitle_filename = file
                break

        return audio_filename, subtitle_filename, title




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
                text_lines.append(lines[i].strip())
                i += 1
            text = ' '.join(text_lines).strip()
            if text:
                lrc_lines.append(f"{time_tag}{text}")
        else:
            i += 1
    return "\n".join(lrc_lines)

def embed_lyrics_and_art(audio_path, lrc_text):
    ext = os.path.splitext(audio_path)[1].lower()
    cover_path = os.path.splitext(audio_path)[0] + '.jpg'

    if ext in ['.m4a', '.mp4']:
        audio = MP4(audio_path)
        audio['©lyr'] = lrc_text
        if os.path.exists(cover_path):
            with open(cover_path, 'rb') as f:
                audio['covr'] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
        audio.save()

    elif ext == '.mp3':
        audio = ID3(audio_path)
        audio.delall('USLT')
        audio.add(USLT(encoding=3, lang='eng', desc='Lyrics', text=lrc_text))
        if os.path.exists(cover_path):
            with open(cover_path, 'rb') as f:
                audio.delall('APIC')
                audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=f.read()))
        audio.save()

    elif ext == '.flac':
        audio = FLAC(audio_path)
        # Embed lyrics as a Vorbis comment
        audio["LYRICS"] = lrc_text

        # Embed cover art
        if os.path.exists(cover_path):
            with open(cover_path, 'rb') as f:
                image = Picture()
                image.data = f.read()
                image.type = 3  # front cover
                image.mime = "image/jpeg"
                image.desc = "Cover"
                # Clear existing pictures
                audio.clear_pictures()
                audio.add_picture(image)

        audio.save()

    else:
        print(f"Embedding not supported for {ext} files.")


def cleanup_files(title):
    leftovers = [
        f"{title}.en.vtt",
        f"{title}.lrc",
    ]
    for file in leftovers:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"🗑️ Deleted leftover: {file}")
            except Exception as e:
                print(f"⚠️ Could not delete {file}: {e}")


def check_lyrics_embedded(audio_path, lrc_text):
    ext = os.path.splitext(audio_path)[1].lower()
    try:
        if ext in ['.m4a', '.mp4']:
            audio = MP4(audio_path)
            return '©lyr' in audio and lrc_text in audio['©lyr'][0]
        elif ext == '.mp3':
            audio = ID3(audio_path)
            return any(lrc_text in tag.text for tag in audio.getall('USLT'))
        elif ext == '.flac':
            audio = FLAC(audio_path)
            return "LYRICS" in audio and lrc_text in audio["LYRICS"][0]
        else:
            print(f"Cannot check lyrics for {ext} files.")
            return False
    except Exception as e:
        print(f"Error checking lyrics: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python export.py <format> <youtube_url>")
        sys.exit(1)

    format = sys.argv[1].lower()
    url = sys.argv[2]

    print(f"Downloading audio as {format} from: {url}")
    audio_path, subtitle_path, title = download_audio_and_subs(format, url)

    if not audio_path or not os.path.exists(audio_path):
        print(f"\nError: Audio file not found.")
        sys.exit(1)

    if subtitle_path and os.path.exists(subtitle_path):
        print(f"Converting subtitles {subtitle_path} to LRC...")
        lrc_text = vtt_to_lrc(subtitle_path)

        lrc_file = f"{title}.lrc"
        with open(lrc_file, 'w', encoding='utf-8') as f:
            f.write(lrc_text)

        # 🔄 Convert thumbnail before embedding
        convert_webp_to_jpg(title)

        print(f"Embedding lyrics into {audio_path}...")
        embed_lyrics_and_art(audio_path, lrc_text)

        if check_lyrics_embedded(audio_path, lrc_text):
            print(f"\n✅ Success! Lyrics embedded in '{audio_path}'.")
            cleanup_files(title)
            audio_path = move_to_export(audio_path)
        else:
            print(f"\n⚠️ Warning: Lyrics not found in '{audio_path}'.")
    else:
        print("No subtitles found, skipping lyrics embedding.")

    input("\nPress any key to exit...")

if __name__ == "__main__":
    main()
