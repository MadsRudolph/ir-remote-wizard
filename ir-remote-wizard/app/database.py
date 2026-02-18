"""SQLite database access layer for the IR code database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Device:
    id: int
    device_type: str
    brand: str
    model: str | None


@dataclass
class Code:
    id: int
    device_id: int
    button_name: str
    protocol: str
    address: str | None
    command: str | None
    raw_data: str | None


class IRDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_device_types(self) -> list[str]:
        """Return all distinct device types, sorted."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT device_type FROM devices ORDER BY device_type"
            ).fetchall()
        return [row["device_type"] for row in rows]

    def get_brands(self, device_type: str) -> list[str]:
        """Return all brands for a device type, sorted."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT brand FROM devices WHERE device_type = ? ORDER BY brand",
                (device_type,),
            ).fetchall()
        return [row["brand"] for row in rows]

    def get_device_type_counts(self) -> dict[str, int]:
        """Return device counts per type."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT device_type, COUNT(*) as cnt FROM devices GROUP BY device_type ORDER BY cnt DESC"
            ).fetchall()
        return {row["device_type"]: row["cnt"] for row in rows}

    def get_power_codes_grouped(
        self, device_type: str, brand: str | None = None
    ) -> list[dict]:
        """Get unique power codes grouped by (protocol, address, command).

        Returns a list of dicts with protocol, address, command, device_ids, and brands.
        Used for Phase 1 discovery — send each unique power code and see which one works.
        """
        sql = """
            SELECT c.protocol, c.address, c.command, c.raw_data,
                   d.id as device_id, d.brand, d.model
            FROM codes c
            JOIN devices d ON d.id = c.device_id
            WHERE d.device_type = ?
              AND LOWER(c.button_name) IN ('power', 'power_on')
        """
        params: list = [device_type]

        if brand:
            sql += " AND d.brand = ?"
            params.append(brand)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        # Group by (protocol, address, command) to deduplicate
        groups: dict[tuple, dict] = {}
        for row in rows:
            key = (row["protocol"], row["address"], row["command"])
            if key not in groups:
                groups[key] = {
                    "protocol": row["protocol"],
                    "address": row["address"],
                    "command": row["command"],
                    "raw_data": row["raw_data"],
                    "device_ids": [],
                    "brands": set(),
                    "models": [],
                }
            groups[key]["device_ids"].append(row["device_id"])
            groups[key]["brands"].add(row["brand"])
            if row["model"]:
                groups[key]["models"].append(row["model"])

        result = []
        for group in groups.values():
            group["brands"] = sorted(group["brands"])
            result.append(group)

        return result

    def get_codes_for_devices(self, device_ids: list[int]) -> list[Code]:
        """Get all codes for a list of device IDs."""
        if not device_ids:
            return []

        placeholders = ",".join("?" * len(device_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM codes WHERE device_id IN ({placeholders})",
                device_ids,
            ).fetchall()

        return [
            Code(
                id=row["id"],
                device_id=row["device_id"],
                button_name=row["button_name"],
                protocol=row["protocol"],
                address=row["address"],
                command=row["command"],
                raw_data=row["raw_data"],
            )
            for row in rows
        ]

    def get_unique_buttons_for_devices(self, device_ids: list[int]) -> list[dict]:
        """Get unique button codes for the matching devices.

        For each button name, picks the most common (protocol, address, command) combo.
        """
        if not device_ids:
            return []

        placeholders = ",".join("?" * len(device_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT button_name, protocol, address, command, raw_data,
                           COUNT(*) as cnt
                    FROM codes
                    WHERE device_id IN ({placeholders})
                    GROUP BY button_name, protocol, address, command
                    ORDER BY button_name, cnt DESC""",
                device_ids,
            ).fetchall()

        # Pick the most common code per button name
        seen: dict[str, dict] = {}
        for row in rows:
            name = row["button_name"]
            if name not in seen:
                seen[name] = {
                    "button_name": name,
                    "protocol": row["protocol"],
                    "address": row["address"],
                    "command": row["command"],
                    "raw_data": row["raw_data"],
                }

        return list(seen.values())

    def get_stats(self) -> dict:
        """Return database statistics."""
        with self._connect() as conn:
            devices = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
            codes = conn.execute("SELECT COUNT(*) FROM codes").fetchone()[0]
            types = conn.execute("SELECT COUNT(DISTINCT device_type) FROM devices").fetchone()[0]
            brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM devices").fetchone()[0]
        return {
            "devices": devices,
            "codes": codes,
            "device_types": types,
            "brands": brands,
        }
