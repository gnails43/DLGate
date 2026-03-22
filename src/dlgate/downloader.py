from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Known audio file signatures (magic bytes)
AUDIO_SIGNATURES = {
    b"\xff\xfb": "mp3",
    b"\xff\xf3": "mp3",
    b"\xff\xf2": "mp3",
    b"ID3": "mp3",
    b"RIFF": "wav",
    b"fLaC": "flac",
    b"OggS": "ogg",
}


def is_audio_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(12)
        return any(header.startswith(sig) for sig in AUDIO_SIGNATURES)
    except Exception:
        return False


def file_exists(output_dir: str, filename: str) -> bool:
    return Path(output_dir, filename).exists()


def sanitize_filename(name: str) -> str:
    # Remove/replace invalid characters
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip(". ")
