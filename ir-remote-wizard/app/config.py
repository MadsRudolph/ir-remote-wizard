"""Add-on configuration — reads HA add-on options from /data/options.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

OPTIONS_PATH = "/data/options.json"
DB_PATH = "/data/irdb.sqlite3"
HA_CONFIG_DIR = "/homeassistant"


@dataclass
class Config:
    esp32_host: str = ""
    esp32_port: int = 6053
    api_encryption_key: str = ""
    ingress_path: str = ""
    db_path: str = DB_PATH
    ha_config_dir: str = HA_CONFIG_DIR

    @classmethod
    def load(cls) -> Config:
        """Load configuration from HA add-on options file."""
        config = cls()

        if os.path.exists(OPTIONS_PATH):
            with open(OPTIONS_PATH) as f:
                options = json.load(f)
            config.esp32_host = options.get("esp32_host", "")
            config.esp32_port = options.get("esp32_port", 6053)
            config.api_encryption_key = options.get("api_encryption_key", "")

        # HA ingress path from environment
        config.ingress_path = os.environ.get("INGRESS_PATH", "")

        return config
