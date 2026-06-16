"""Runtime configuration for FontaineRTC.

Settings come from environment variables (prefix ``FONTAINE_``) and/or a ``.env``
file. The single most important one is ``FONTAINE_ROLE`` which selects whether
this process behaves as a node or as the central admin panel.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role(str, Enum):
    node = "node"
    admin = "admin"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FONTAINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- core ---
    role: Role = Field(default=Role.node, description="node | admin")
    data_dir: Path = Field(default=Path("./data"))
    panel_host: str = "0.0.0.0"
    panel_port: int = 8080

    # --- auth ---
    panel_password: str = ""          # PBKDF2 hash; empty => set on first run
    api_key: str = ""                 # 64-hex; generated on first run if empty

    # --- node role ---
    binary_path: Path = Field(default=Path("./olcrtc-linux-amd64"))
    ffmpeg: str = "ffmpeg"
    dns: str = "1.1.1.1:53"
    debug: bool = True
    full_logs: bool = False
    socks_proxy: str = ""
    socks_proxy_port: str = ""
    push_url: str = ""                # admin push target; empty => disabled

    # --- admin role ---
    poll_interval: int = 30           # fallback poll seconds (5..300)
    panel_url: str = ""               # public URL announced to nodes for push
    tg_bot_token: str = ""
    tg_recipients: str = ""           # newline-separated numeric chat ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
