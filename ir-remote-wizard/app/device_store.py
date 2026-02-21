"""Persist configured device profiles across sessions."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

STORE_FILENAME = ".ir_wizard_devices.json"


def make_device_id(brand: str, device_type: str) -> str:
    """Generate a stable ID like 'sony_tv' from brand + device type."""
    raw = f"{brand}_{device_type}"
    return re.sub(r"[^a-z0-9_]", "_", raw.lower()).strip("_")


@dataclass
class SavedButton:
    name: str
    protocol: str
    address: str | None = None
    command: str | None = None
    raw_data: str | None = None


@dataclass
class DeviceProfile:
    device_id: str
    device_type: str
    brand: str
    device_name: str = ""
    matched_brand: str = ""
    matched_device_ids: list[int] = field(default_factory=list)
    buttons: list[SavedButton] = field(default_factory=list)


class DeviceStore:
    """Load / save / list / delete device profiles from a JSON file."""

    def __init__(self, ha_config_dir: str):
        self._path = os.path.join(ha_config_dir, STORE_FILENAME)
        self._profiles: dict[str, DeviceProfile] = {}
        self._load()

    # -- public API --

    def list_devices(self) -> list[DeviceProfile]:
        return list(self._profiles.values())

    def get_device(self, device_id: str) -> DeviceProfile | None:
        return self._profiles.get(device_id)

    def save_device(self, profile: DeviceProfile) -> None:
        self._profiles[profile.device_id] = profile
        self._persist()

    def delete_device(self, device_id: str) -> bool:
        if device_id in self._profiles:
            del self._profiles[device_id]
            self._persist()
            return True
        return False

    # -- internals --

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            for did, obj in data.items():
                buttons = [SavedButton(**b) for b in obj.get("buttons", [])]
                self._profiles[did] = DeviceProfile(
                    device_id=obj["device_id"],
                    device_type=obj["device_type"],
                    brand=obj["brand"],
                    device_name=obj.get("device_name", ""),
                    matched_brand=obj.get("matched_brand", ""),
                    matched_device_ids=obj.get("matched_device_ids", []),
                    buttons=buttons,
                )
            logger.info("Loaded %d device profiles from %s", len(self._profiles), self._path)
        except Exception as e:
            logger.warning("Could not load device store %s: %s", self._path, e)

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = {}
        for did, profile in self._profiles.items():
            d = asdict(profile)
            data[did] = d
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved %d device profiles to %s", len(data), self._path)
