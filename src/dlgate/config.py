from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class UserConfig:
    name: str = ""
    email: str = ""


@dataclass
class DownloadConfig:
    output_dir: str = "./downloads"
    skip_existing: bool = True


@dataclass
class BrowserConfig:
    profile_dir: str = "./.browser_profile"
    headless: bool = False
    slow_mo: int = 100
    timeout: int = 30000
    channel: str = ""


@dataclass
class Config:
    user: UserConfig = field(default_factory=UserConfig)
    comments: list[str] = field(
        default_factory=lambda: ["Great track!", "Yeah", "Nice one", "Fire", "Love this"]
    )
    download: DownloadConfig = field(default_factory=DownloadConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        if path is None:
            path = Path("config.yaml")
        path = Path(path)

        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        if user := data.get("user"):
            config.user = UserConfig(
                name=user.get("name", ""),
                email=user.get("email", ""),
            )

        if comments := data.get("comments"):
            config.comments = list(comments)

        if dl := data.get("download"):
            config.download = DownloadConfig(
                output_dir=dl.get("output_dir", "./downloads"),
                skip_existing=dl.get("skip_existing", True),
            )

        if br := data.get("browser"):
            config.browser = BrowserConfig(
                profile_dir=br.get("profile_dir", "./.browser_profile"),
                headless=br.get("headless", False),
                slow_mo=br.get("slow_mo", 100),
                timeout=br.get("timeout", 30000),
                channel=br.get("channel", ""),
            )

        return config

    def ensure_dirs(self) -> None:
        os.makedirs(self.download.output_dir, exist_ok=True)
        os.makedirs(self.browser.profile_dir, exist_ok=True)
