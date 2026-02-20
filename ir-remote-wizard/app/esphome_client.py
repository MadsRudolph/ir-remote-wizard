"""ESPHome API client wrapper for sending IR commands."""

from __future__ import annotations

import asyncio
import logging
import re

from aioesphomeapi import APIClient, APIConnectionError, LogLevel

from .protocol_map import ESPHomeIRCommand, convert_code

logger = logging.getLogger(__name__)


class ESPHomeIRClient:
    """Wrapper around aioesphomeapi for sending IR commands to an ESP32."""

    def __init__(self, host: str, port: int = 6053, password: str = "", noise_psk: str = ""):
        self.host = host
        self.port = port
        self.password = password
        self.noise_psk = noise_psk
        self._client: APIClient | None = None

    async def connect(self) -> None:
        """Connect to the ESP32 device."""
        self._client = APIClient(
            self.host,
            self.port,
            self.password,
            noise_psk=self.noise_psk or None,
        )
        await self._client.connect(login=True)
        logger.info("Connected to ESP32 at %s:%d", self.host, self.port)

    async def disconnect(self) -> None:
        """Disconnect from the ESP32 device."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def test_connection(self) -> dict:
        """Test the connection and return device info."""
        try:
            await self.connect()
            info = await self._client.device_info()
            await self.disconnect()
            return {
                "success": True,
                "name": info.name,
                "model": info.model,
                "esphome_version": info.esphome_version,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_self_check(self) -> dict:
        """Send a known NEC code and check the receiver picks it up via logs.

        Must be called while already connected.
        Returns {success: bool, error: str|None, log_lines: list}.
        """
        if not self._client:
            return {"success": False, "error": "Not connected", "log_lines": []}

        test_address = 0x1234
        test_command = 0x5678
        received = asyncio.Event()
        log_lines: list[str] = []

        def _on_log(msg) -> None:
            line = msg.message
            if isinstance(line, (bytes, bytearray)):
                line = line.decode("utf-8", errors="replace")
            else:
                line = str(line)
            log_lines.append(line)
            # ESPHome logs NEC as: "Received NEC: address=0x1234, command=0x5678"
            if re.search(
                r"Received NEC: address=0x1234, command=0x5678",
                line,
                re.IGNORECASE,
            ):
                received.set()

        unsub = self._client.subscribe_logs(
            _on_log, log_level=LogLevel.LOG_LEVEL_DEBUG
        )

        try:
            # Send test NEC code via the send_ir_nec service
            svc = await self._find_service("send_ir_nec")
            await self._client.execute_service(
                svc, {"address": test_address, "command": test_command}
            )

            # Wait up to 2 seconds for the receiver to echo it back
            try:
                await asyncio.wait_for(received.wait(), timeout=2.0)
                return {"success": True, "error": None, "log_lines": log_lines}
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error": (
                        "IR receiver did not detect the test signal within 2 seconds. "
                        "This may be normal if the transmitter and receiver cannot see "
                        "each other on this board."
                    ),
                    "log_lines": log_lines,
                }
        except Exception as e:
            return {"success": False, "error": str(e), "log_lines": log_lines}
        finally:
            unsub()

    async def test_connection_and_self_check(self) -> dict:
        """Connect, get device info, run self-check, then disconnect.

        Returns {success, name, model, esphome_version, self_check: {...}}.
        """
        try:
            await self.connect()
            info = await self._client.device_info()
            result = {
                "success": True,
                "name": info.name,
                "model": info.model,
                "esphome_version": info.esphome_version,
            }
            result["self_check"] = await self.run_self_check()
            await self.disconnect()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_command(self, cmd: ESPHomeIRCommand) -> bool:
        """Send an IR command via the ESPHome API service call."""
        if not self._client:
            await self.connect()

        try:
            await self._client.execute_service(
                await self._find_service(cmd.service),
                cmd.data,
            )
            return True
        except Exception as e:
            logger.error("Failed to send IR command: %s", e)
            return False

    async def send_ir_code(
        self,
        protocol: str,
        address: str | None = None,
        command: str | None = None,
        raw_data: str | None = None,
    ) -> bool:
        """Convert a Flipper-IRDB code and send it via ESPHome."""
        cmd = convert_code(protocol, address, command, raw_data)
        if not cmd:
            logger.warning("Unsupported protocol: %s", protocol)
            return False
        return await self.send_command(cmd)

    async def send_pronto(self, data: str) -> bool:
        """Send a Pronto hex code via the ESPHome send_ir_pronto service."""
        cmd = convert_code("Pronto", raw_data=data)
        if not cmd:
            return False
        return await self.send_command(cmd)

    async def listen_for_ir(self, timeout: float = 5.0) -> dict:
        """Subscribe to ESP32 logs and capture the first IR code received.

        Waits up to *timeout* seconds.  When the first IR log line appears,
        collects for an additional 500 ms so all decodings of the same button
        press are gathered, then picks the best protocol.

        Returns {success, protocol, address, command, raw_data, pronto, display}.
        """
        if not self._client:
            await self.connect()

        first_ir = asyncio.Event()
        log_lines: list[str] = []

        # Patterns for known protocol log lines
        ir_pattern = re.compile(
            r"Received (NEC|Samsung|Samsung36|Sony|RC5|RC6|LG|Pronto|Pioneer|Panasonic|JVC|Dish|Coolix):",
            re.IGNORECASE,
        )

        def _on_log(msg) -> None:
            line = msg.message
            if isinstance(line, (bytes, bytearray)):
                line = line.decode("utf-8", errors="replace")
            else:
                line = str(line)
            log_lines.append(line)
            if ir_pattern.search(line):
                first_ir.set()

        unsub = self._client.subscribe_logs(
            _on_log, log_level=LogLevel.LOG_LEVEL_DEBUG
        )

        try:
            # Wait for first IR log line
            try:
                await asyncio.wait_for(first_ir.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return {"success": False, "error": "No IR signal detected within timeout."}

            # Collect for 500ms more to get all decodings of same press
            await asyncio.sleep(0.5)

            return self._parse_ir_logs(log_lines)
        finally:
            unsub()

    # --- Protocol priority (lower = preferred) ---
    _PROTOCOL_PRIORITY = {
        "NEC": 1,
        "Samsung": 2,
        "Samsung36": 2,
        "Sony": 3,
        "RC5": 4,
        "RC6": 5,
        "LG": 6,
        "Panasonic": 6,
        "Pioneer": 6,
        "JVC": 6,
        "Dish": 6,
        "Coolix": 6,
        "Pronto": 7,
    }

    def _parse_ir_logs(self, log_lines: list[str]) -> dict:
        """Parse collected log lines and return the best IR code found."""
        parsed: list[dict] = []

        for line in log_lines:
            # NEC: address=0xXXXX, command=0xXXXX
            m = re.search(
                r"Received NEC: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "NEC",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"NEC addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # Samsung: data=0xXXXXXXXX
            m = re.search(
                r"Received Samsung: data=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Samsung",
                    "address": None,
                    "command": None,
                    "raw_data": m.group(1),
                    "display": f"Samsung data=0x{m.group(1)}",
                })
                continue

            # Samsung36: address=0xXXXX, command=0xXXXXXXXX
            m = re.search(
                r"Received Samsung36: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Samsung36",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"Samsung36 addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # Sony: data=0xXXXX, nbits=XX
            m = re.search(
                r"Received Sony: data=0x([0-9A-Fa-f]+), nbits=(\d+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Sony",
                    "address": None,
                    "command": None,
                    "raw_data": f"{m.group(1)}:{m.group(2)}",
                    "display": f"Sony data=0x{m.group(1)} nbits={m.group(2)}",
                })
                continue

            # RC5: address=0xXX, command=0xXX
            m = re.search(
                r"Received RC5: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "RC5",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"RC5 addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # RC6: address=0xXX, command=0xXX
            m = re.search(
                r"Received RC6: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "RC6",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"RC6 addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # LG: data=0xXXXXXXXX, nbits=XX
            m = re.search(
                r"Received LG: data=0x([0-9A-Fa-f]+), nbits=(\d+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "LG",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"LG data=0x{m.group(1)} nbits={m.group(2)}",
                })
                continue

            # Panasonic: address=0xXXXX, command=0xXXXXXXXX
            m = re.search(
                r"Received Panasonic: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Panasonic",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"Panasonic addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # Pioneer: rc_code_1=0xXXXX
            m = re.search(
                r"Received Pioneer: rc_code_1=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Pioneer",
                    "address": m.group(1),
                    "command": None,
                    "raw_data": None,
                    "display": f"Pioneer rc_code=0x{m.group(1)}",
                })
                continue

            # JVC: data=0xXXXX
            m = re.search(
                r"Received JVC: data=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "JVC",
                    "address": None,
                    "command": m.group(1),
                    "raw_data": None,
                    "display": f"JVC data=0x{m.group(1)}",
                })
                continue

            # Dish: address=0xXX, command=0xXX
            m = re.search(
                r"Received Dish: address=0x([0-9A-Fa-f]+), command=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Dish",
                    "address": m.group(1),
                    "command": m.group(2),
                    "raw_data": None,
                    "display": f"Dish addr=0x{m.group(1)} cmd=0x{m.group(2)}",
                })
                continue

            # Coolix: data=0xXXXXXX
            m = re.search(
                r"Received Coolix: data=0x([0-9A-Fa-f]+)",
                line,
            )
            if m:
                parsed.append({
                    "protocol": "Coolix",
                    "address": None,
                    "command": m.group(1),
                    "raw_data": None,
                    "display": f"Coolix data=0x{m.group(1)}",
                })
                continue

            # Pronto: data= followed by hex string(s)
            m = re.search(
                r"Received Pronto: data=\s*(.+)",
                line,
            )
            if m:
                pronto_data = m.group(1).strip()
                # Filter noise: Pronto with < 4 burst pairs is garbage
                parts = pronto_data.split()
                if len(parts) >= 8:  # minimum meaningful Pronto
                    parsed.append({
                        "protocol": "Pronto",
                        "address": None,
                        "command": None,
                        "raw_data": pronto_data,
                        "display": f"Pronto ({len(parts)} words)",
                    })
                continue

        if not parsed:
            return {"success": False, "error": "IR signal detected but could not parse protocol."}

        # Pick best protocol by priority
        parsed.sort(key=lambda p: self._PROTOCOL_PRIORITY.get(p["protocol"], 99))
        best = parsed[0]

        # Also capture the Pronto as fallback if present and best is not Pronto
        pronto = None
        for p in parsed:
            if p["protocol"] == "Pronto":
                pronto = p["raw_data"]
                break

        return {
            "success": True,
            "protocol": best["protocol"],
            "address": best["address"],
            "command": best["command"],
            "raw_data": best["raw_data"],
            "pronto": pronto or best.get("raw_data") if best["protocol"] == "Pronto" else pronto,
            "display": best["display"],
        }

    async def _find_service(self, service_name: str):
        """Find a service by name from the device's service list."""
        _, services = await self._client.list_entities_services()
        for service in services:
            if service.name == service_name:
                return service
        raise ValueError(f"Service '{service_name}' not found on device")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
