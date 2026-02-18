"""Maps Flipper-IRDB protocol names to ESPHome IR transmitter services.

Flipper stores addresses/commands as space-separated hex bytes in little-endian order.
For example: "34 DB 00 00" → 0xDB34 (16-bit NEC extended address).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ESPHomeIRCommand:
    """An IR command ready to send via an ESPHome API service call."""
    service: str
    data: dict[str, int | list[int]]


def _hex_bytes_to_int(hex_str: str, num_bytes: int = 2) -> int:
    """Convert Flipper-style space-separated hex bytes (LE) to an integer.

    "34 DB 00 00" with num_bytes=2 → 0xDB34
    "07 00 00 00" with num_bytes=1 → 0x07
    """
    parts = hex_str.strip().split()
    value = 0
    for i in range(min(num_bytes, len(parts))):
        value |= int(parts[i], 16) << (8 * i)
    return value


def _hex_bytes_to_full_int(hex_str: str) -> int:
    """Convert all hex bytes to a single LE integer."""
    parts = hex_str.strip().split()
    value = 0
    for i, part in enumerate(parts):
        value |= int(part, 16) << (8 * i)
    return value


# Protocol name → (ESPHome service, converter function)
# The converter takes (address_hex, command_hex) and returns ESPHomeIRCommand

def _convert_nec(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 2)
    command = _hex_bytes_to_int(command_hex, 2)
    return ESPHomeIRCommand("send_ir_nec", {"address": address, "command": command})


def _convert_samsung32(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    data = (address << 24) | ((~address & 0xFF) << 16) | (command << 8) | (~command & 0xFF)
    return ESPHomeIRCommand("send_ir_samsung", {"data": data})


def _convert_rc5(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    return ESPHomeIRCommand("send_ir_rc5", {"address": address, "command": command})


def _convert_rc6(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    return ESPHomeIRCommand("send_ir_rc6", {"address": address, "command": command})


def _convert_sirc(address_hex: str, command_hex: str, nbits: int = 12) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 2)
    command = _hex_bytes_to_int(command_hex, 1)
    if nbits == 12:
        data = (address << 7) | (command & 0x7F)
    elif nbits == 15:
        data = (address << 7) | (command & 0x7F)
    else:  # 20
        data = (address << 7) | (command & 0x7F)
    return ESPHomeIRCommand("send_ir_sony", {"data": data, "nbits": nbits})


def _convert_raw(raw_data: str) -> ESPHomeIRCommand:
    """Convert raw timing data (space-separated integers) to ESPHome raw command."""
    code = [int(x) for x in raw_data.strip().split()]
    return ESPHomeIRCommand("send_ir_raw", {"code": code})


# Mapping from Flipper protocol names to converter functions
PROTOCOL_CONVERTERS: dict[str, callable] = {
    "NEC": _convert_nec,
    "NECext": _convert_nec,
    "NEC42": _convert_nec,
    "NEC42ext": _convert_nec,
    "Samsung32": _convert_samsung32,
    "RC5": _convert_rc5,
    "RC5X": _convert_rc5,
    "RC6": _convert_rc6,
    "SIRC": lambda a, c: _convert_sirc(a, c, 12),
    "SIRC15": lambda a, c: _convert_sirc(a, c, 15),
    "SIRC20": lambda a, c: _convert_sirc(a, c, 20),
}

# Protocols that must be sent as raw timing data
RAW_ONLY_PROTOCOLS = {"Kaseikyo", "RCMM", "Pioneer"}


def convert_code(
    protocol: str,
    address: str | None = None,
    command: str | None = None,
    raw_data: str | None = None,
) -> ESPHomeIRCommand | None:
    """Convert a Flipper-IRDB code entry to an ESPHome IR command.

    Returns None if the protocol is unsupported and no raw data is available.
    """
    if protocol == "raw" and raw_data:
        return _convert_raw(raw_data)

    if protocol in RAW_ONLY_PROTOCOLS:
        if raw_data:
            return _convert_raw(raw_data)
        return None

    converter = PROTOCOL_CONVERTERS.get(protocol)
    if converter and address and command:
        return converter(address, command)

    return None


def get_supported_protocols() -> list[str]:
    """Return list of all supported Flipper protocol names."""
    return list(PROTOCOL_CONVERTERS.keys()) + ["raw"] + list(RAW_ONLY_PROTOCOLS)


# Button categories for the discovery wizard
BUTTON_CATEGORIES = {
    "Power": ["Power", "Power_on", "Power_off"],
    "Volume": ["Vol_up", "Vol_down", "Mute"],
    "Channel": ["Ch_up", "Ch_down", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    "Navigation": ["Up", "Down", "Left", "Right", "Ok", "Back", "Menu", "Home", "Guide", "Info"],
    "Input": ["Source", "Input", "Hdmi1", "Hdmi2", "Hdmi3", "Tv", "Aux"],
    "Playback": ["Play", "Pause", "Stop", "Ff", "Rw", "Rec", "Next", "Prev"],
}

# Buttons that should use NEC repeat codes when held
HOLD_BUTTONS = {"Vol_up", "Vol_down", "Ch_up", "Ch_down", "Ff", "Rw"}
