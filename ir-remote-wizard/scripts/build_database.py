#!/usr/bin/env python3
"""Build a SQLite database from the Flipper-IRDB repository.

Parses all .ir files in the Flipper-IRDB directory tree and produces a
normalized SQLite database with devices and codes tables.

Usage:
    python build_database.py <irdb_path> <output_db_path>

The Flipper-IRDB directory structure is:
    Flipper-IRDB/
    ├── TVs/
    │   ├── Samsung/
    │   │   ├── model1.ir
    │   │   └── model2.ir
    │   └── LG/
    │       └── model.ir
    ├── ACs/
    │   └── ...
    └── ...

Each .ir file contains one or more IR code entries in this format:
    name: Power
    type: parsed
    protocol: NEC
    address: 04 00 00 00
    command: 08 00 00 00
    #
    name: Vol_up
    type: raw
    frequency: 38000
    duty_cycle: 0.330000
    data: 9024 4512 564 564 ...
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path


# Map Flipper-IRDB top-level directory names to normalized device types
DEVICE_TYPE_MAP = {
    "TVs": "TV",
    "ACs": "AC",
    "Audio_and_Video_Receivers": "Audio Receiver",
    "Blu-Ray": "Blu-ray Player",
    "Cable_Boxes": "Cable Box",
    "Cameras": "Camera",
    "CD_Players": "CD Player",
    "DVD_Players": "DVD Player",
    "Fans": "Fan",
    "Fireplaces": "Fireplace",
    "Heaters": "Heater",
    "LED_Lighting": "LED Lighting",
    "Monitors": "Monitor",
    "Projectors": "Projector",
    "SoundBars": "Soundbar",
    "Speakers": "Speaker",
    "Streaming_Devices": "Streaming Device",
    "VCRs": "VCR",
}

# Directories to skip — these have non-standard structure or duplicate data
SKIP_DIRS = {"_Converted_", "Miscellaneous"}


def parse_ir_file(filepath: Path) -> list[dict]:
    """Parse a Flipper .ir file and return a list of code entries."""
    codes = []
    current: dict = {}

    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return codes

    for line in text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            if current.get("name"):
                codes.append(current)
            current = {}
            continue

        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if key == "name":
            if current.get("name"):
                codes.append(current)
            current = {"name": value}
        elif key == "type":
            current["type"] = value
        elif key == "protocol":
            current["protocol"] = value
        elif key == "address":
            current["address"] = value
        elif key == "command":
            current["command"] = value
        elif key == "frequency":
            current["frequency"] = value
        elif key == "data":
            current["raw_data"] = value

    if current.get("name"):
        codes.append(current)

    return codes


def infer_device_type(path: Path, irdb_root: Path) -> str | None:
    """Infer device type from the directory structure."""
    try:
        relative = path.relative_to(irdb_root)
    except ValueError:
        return None

    top_dir = relative.parts[0] if relative.parts else None
    if not top_dir or top_dir in SKIP_DIRS:
        return None
    return DEVICE_TYPE_MAP.get(top_dir, top_dir.replace("_", " "))


def infer_brand(path: Path, irdb_root: Path) -> str | None:
    """Infer brand from the directory structure (second level)."""
    try:
        relative = path.relative_to(irdb_root)
    except ValueError:
        return None

    if len(relative.parts) >= 2:
        return relative.parts[1].replace("_", " ")
    return None


def infer_model(path: Path) -> str | None:
    """Infer model from the filename."""
    stem = path.stem
    if stem.lower() in ("unknown", "misc", "default"):
        return None
    return stem


def build_database(irdb_path: str, db_path: str) -> None:
    """Build the SQLite database from Flipper-IRDB files."""
    irdb_root = Path(irdb_path)
    if not irdb_root.is_dir():
        print(f"Error: {irdb_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY,
            device_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            model TEXT
        );

        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY,
            device_id INTEGER NOT NULL REFERENCES devices(id),
            button_name TEXT NOT NULL,
            protocol TEXT NOT NULL,
            address TEXT,
            command TEXT,
            raw_data TEXT,
            UNIQUE(device_id, button_name)
        );

        CREATE INDEX IF NOT EXISTS idx_devices_type_brand ON devices(device_type, brand);
        CREATE INDEX IF NOT EXISTS idx_codes_device ON codes(device_id);
        CREATE INDEX IF NOT EXISTS idx_codes_button ON codes(button_name);
    """)

    device_count = 0
    code_count = 0
    skipped = 0

    ir_files = list(irdb_root.rglob("*.ir"))
    print(f"Found {len(ir_files)} .ir files")

    for ir_file in ir_files:
        device_type = infer_device_type(ir_file, irdb_root)
        brand = infer_brand(ir_file, irdb_root)
        model = infer_model(ir_file)

        if not device_type or not brand:
            skipped += 1
            continue

        codes = parse_ir_file(ir_file)
        if not codes:
            skipped += 1
            continue

        cursor.execute(
            "INSERT INTO devices (device_type, brand, model) VALUES (?, ?, ?)",
            (device_type, brand, model),
        )
        device_id = cursor.lastrowid
        device_count += 1

        for code in codes:
            name = code.get("name", "")
            code_type = code.get("type", "")
            protocol = code.get("protocol", "")
            address = code.get("address")
            command = code.get("command")
            raw_data = code.get("raw_data")

            if code_type == "raw":
                protocol = "raw"

            if not protocol:
                continue

            try:
                cursor.execute(
                    """INSERT OR IGNORE INTO codes
                       (device_id, button_name, protocol, address, command, raw_data)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (device_id, name, protocol, address, command, raw_data),
                )
                code_count += 1
            except sqlite3.Error:
                pass

    db.commit()
    db.close()

    print(f"Database built: {device_count} devices, {code_count} codes ({skipped} files skipped)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <irdb_path> <output_db_path>", file=sys.stderr)
        sys.exit(1)
    build_database(sys.argv[1], sys.argv[2])
