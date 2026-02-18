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
            log_lines.append(line)
            # ESPHome logs NEC as: "Received NEC: address=0x1234, command=0x5678"
            if re.search(
                r"Received NEC: address=0x1234, command=0x5678",
                line,
                re.IGNORECASE,
            ):
                received.set()

        unsub = await self._client.subscribe_logs(
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

    async def _find_service(self, service_name: str):
        """Find a service by name from the device's service list."""
        services, _ = await self._client.list_entities_services()
        for service in services:
            if service.name == service_name:
                return service
        raise ValueError(f"Service '{service_name}' not found on device")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
