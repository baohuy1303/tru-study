"""Video transcription utilities using OpenAI Whisper API."""

import os
import tempfile
from pathlib import Path
from openai import OpenAI

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".wmv", ".flv"}
WHISPER_MAX_BYTES = 25 * 1024 * 1024  # 25MB
MAX_DURATION_MINUTES = 10

# Conservative estimate: ~1MB/min for compressed video audio track
BYTES_PER_MINUTE_ESTIMATE = 1_000_000


def is_video_file(filename: str) -> bool:
    """Check if filename has a video extension."""
    ext = Path(filename).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def estimate_duration_minutes(size_bytes: int) -> float:
    """Rough duration estimate from file size. Intentionally conservative."""
    return size_bytes / BYTES_PER_MINUTE_ESTIMATE


def extract_audio(video_path: str) -> str | None:
    """Extract audio from video to a temp .mp3 file using pydub/ffmpeg.
    Returns path to temp audio file, or None if ffmpeg unavailable."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(video_path)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        audio.export(tmp.name, format="mp3", bitrate="64k")
        return tmp.name
    except Exception as e:
        print(f"  [video] Audio extraction failed (ffmpeg may not be installed): {e}")
        return None


def transcribe_video(video_path: str) -> str:
    """Transcribe a video file using OpenAI Whisper API.

    Always extracts audio first (video -> mp3 at 64kbps) to minimize upload size
    and avoid Whisper's 25MB limit. Falls back to raw file if ffmpeg unavailable.
    Returns transcript text or empty string on failure.
    """
    file_size = os.path.getsize(video_path)
    file_to_send = video_path
    temp_audio = None

    # Always try to extract audio first (much smaller than video)
    print(f"  [video] Extracting audio from {file_size / 1024 / 1024:.1f}MB video...")
    temp_audio = extract_audio(video_path)
    if temp_audio:
        audio_size = os.path.getsize(temp_audio)
        print(f"  [video] Audio extracted: {audio_size / 1024 / 1024:.1f}MB")
        if audio_size > WHISPER_MAX_BYTES:
            print(f"  [video] Audio still too large -- skipping")
            os.unlink(temp_audio)
            return ""
        file_to_send = temp_audio
    else:
        # ffmpeg not available -- try raw file if small enough
        if file_size > WHISPER_MAX_BYTES:
            print(f"  [video] No ffmpeg and file is {file_size / 1024 / 1024:.1f}MB (>{WHISPER_MAX_BYTES / 1024 / 1024}MB) -- skipping")
            return ""
        print(f"  [video] No ffmpeg, sending raw file ({file_size / 1024 / 1024:.1f}MB)")

    try:
        client = OpenAI()  # uses OPENAI_API_KEY from env
        with open(file_to_send, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        return result.strip() if isinstance(result, str) else str(result).strip()
    except Exception as e:
        print(f"  [video] Whisper transcription failed: {e}")
        return ""
    finally:
        if temp_audio and os.path.exists(temp_audio):
            os.unlink(temp_audio)
