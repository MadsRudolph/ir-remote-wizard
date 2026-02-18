"""ESPHome API client wrapper for sending IR commands."""

from __future__ import annotations

import asyncio
import logging

from aioesphomeapi import APIClient, APIConnectionError

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
