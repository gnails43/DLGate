from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TrackType(str, Enum):
    SOUNDCLOUD = "soundcloud"
    HYPEDDIT = "hypeddit"


class GateStepType(str, Enum):
    EMAIL = "email"
    SOUNDCLOUD_OAUTH = "soundcloud_oauth"
    COMMENT = "comment"
    SOCIAL_LINK = "social_link"
    DOWNLOAD = "download"


class ProcessStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NO_GATE = "no_gate"


@dataclass
class Track:
    url: str
    title: str = ""
    artist: str = ""
    track_type: TrackType = TrackType.SOUNDCLOUD
    gate_url: Optional[str] = None


@dataclass
class GateResult:
    track: Track
    status: ProcessStatus = ProcessStatus.SKIPPED
    download_path: Optional[str] = None
    error_message: Optional[str] = None
    steps_completed: list[GateStepType] = field(default_factory=list)
