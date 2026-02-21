"""Maps Flipper-IRDB protocol names to ESPHome IR transmitter services.

Flipper stores addresses/commands as space-separated hex bytes in little-endian order.
For example: "34 DB 00 00" → 0xDB34 (16-bit NEC extended address).

Key differences between Flipper and ESPHome encodings:

NEC family: Flipper stores only the meaningful bytes without complements.
  Standard NEC stores 8-bit address + 8-bit command; the complement bytes
  (~address, ~command) are implicit.  ESPHome expects the full 16-bit values
  with complements already included (e.g. address 0x04 → 0xFB04).

Samsung32: Flipper stores address/command in LSB-first logical order, but
  ESPHome's Samsung transmitter sends bits MSB-first.  Each byte must be
  bit-reversed before building the 32-bit data word.  The Samsung frame is
  address, address (repeated), command, ~command.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ESPHomeIRCommand:
    """An IR command ready to send via an ESPHome API service call."""
    service: str
    data: dict[str, int | list[int]]
    repeat: int = 1  # Sony SIRC requires ≥3 transmissions


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


def _add_complement(byte_val: int) -> int:
    """Build a 16-bit value from an 8-bit byte and its complement.

    0x04 → 0xFB04  (low byte = value, high byte = ~value)
    """
    return byte_val | ((~byte_val & 0xFF) << 8)


def _reverse_bits(b: int) -> int:
    """Reverse the bits of an 8-bit value.

    0x07 (00000111) → 0xE0 (11100000)
    """
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def _reverse_bits_n(value: int, n: int) -> int:
    """Reverse the bit order of an n-bit value.

    _reverse_bits_n(0x95, 12) → 0xA90
    (000010010101 → 101010010000)
    """
    result = 0
    for _ in range(n):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


# Protocol name → (ESPHome service, converter function)
# The converter takes (address_hex, command_hex) and returns ESPHomeIRCommand

def _convert_nec(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    """Standard NEC: 8-bit address + complement, 8-bit command + complement."""
    addr_byte = _hex_bytes_to_int(address_hex, 1)
    cmd_byte = _hex_bytes_to_int(command_hex, 1)
    address = _add_complement(addr_byte)
    command = _add_complement(cmd_byte)
    return ESPHomeIRCommand("send_ir_nec", {"address": address, "command": command})


def _convert_necext(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    """Extended NEC: 16-bit address (no complement), 8-bit command + complement."""
    address = _hex_bytes_to_int(address_hex, 2)
    cmd_byte = _hex_bytes_to_int(command_hex, 1)
    command = _add_complement(cmd_byte)
    return ESPHomeIRCommand("send_ir_nec", {"address": address, "command": command})


def _convert_samsung32(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    """Samsung32: bit-reverse bytes, frame = addr, addr, cmd, ~cmd."""
    addr = _reverse_bits(_hex_bytes_to_int(address_hex, 1))
    cmd = _reverse_bits(_hex_bytes_to_int(command_hex, 1))
    data = (addr << 24) | (addr << 16) | (cmd << 8) | (~cmd & 0xFF)
    return ESPHomeIRCommand("send_ir_samsung", {"data": data})


def _convert_samsung36(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = int(address_hex, 16)
    command = int(command_hex, 16)
    return ESPHomeIRCommand("send_ir_samsung36", {"address": address, "command": command})


def _convert_rc5(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    return ESPHomeIRCommand("send_ir_rc5", {"address": address, "command": command})


def _convert_rc6(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    return ESPHomeIRCommand("send_ir_rc6", {"address": address, "command": command})


def _convert_sirc(address_hex: str, command_hex: str, nbits: int = 12) -> ESPHomeIRCommand:
    """Sony SIRC: build logical word then bit-reverse for ESPHome.

    ESPHome represents Sony data with first-transmitted bit as MSB,
    but SIRC sends LSB-first.  Flipper stores address=0x01, command=0x15
    for TV power → logical 0x95 → reversed 12-bit → 0xA90.
    """
    address = _hex_bytes_to_int(address_hex, 2)
    command = _hex_bytes_to_int(command_hex, 1)
    logical = (address << 7) | (command & 0x7F)
    data = _reverse_bits_n(logical, nbits)
    return ESPHomeIRCommand("send_ir_sony", {"data": data, "nbits": nbits}, repeat=3)


def _convert_lg(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    """Convert LG protocol. ESPHome expects a single data word + nbits."""
    data = _hex_bytes_to_full_int(address_hex)
    # LG typically uses 28 or 32 bits; infer from hex length
    hex_len = len(address_hex.strip().replace(" ", ""))
    nbits = max(28, hex_len * 4)
    return ESPHomeIRCommand("send_ir_lg", {"data": data, "nbits": nbits})


def _convert_panasonic(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 2)
    command = _hex_bytes_to_full_int(command_hex)
    return ESPHomeIRCommand("send_ir_panasonic", {"address": address, "command": command})


def _convert_pioneer(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    rc_code_1 = _hex_bytes_to_full_int(address_hex)
    return ESPHomeIRCommand("send_ir_pioneer", {"rc_code_1": rc_code_1})


def _convert_jvc(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    data = _hex_bytes_to_full_int(command_hex)
    return ESPHomeIRCommand("send_ir_jvc", {"data": data})


def _convert_dish(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    address = _hex_bytes_to_int(address_hex, 1)
    command = _hex_bytes_to_int(command_hex, 1)
    return ESPHomeIRCommand("send_ir_dish", {"address": address, "command": command})


def _convert_coolix(address_hex: str, command_hex: str) -> ESPHomeIRCommand:
    first = _hex_bytes_to_full_int(command_hex)
    return ESPHomeIRCommand("send_ir_coolix", {"first": first})


def _convert_raw(raw_data: str) -> ESPHomeIRCommand:
    """Convert raw timing data (space-separated integers) to ESPHome raw command."""
    code = [int(x) for x in raw_data.strip().split()]
    return ESPHomeIRCommand("send_ir_raw", {"code": code})


# Mapping from Flipper protocol names to converter functions
PROTOCOL_CONVERTERS: dict[str, callable] = {
    "NEC": _convert_nec,
    "NECext": _convert_necext,
    "NEC42": _convert_nec,
    "NEC42ext": _convert_necext,
    "Samsung32": _convert_samsung32,
    "Samsung36": _convert_samsung36,
    "RC5": _convert_rc5,
    "RC5X": _convert_rc5,
    "RC6": _convert_rc6,
    "SIRC": lambda a, c: _convert_sirc(a, c, 12),
    "SIRC15": lambda a, c: _convert_sirc(a, c, 15),
    "SIRC20": lambda a, c: _convert_sirc(a, c, 20),
    "LG": _convert_lg,
    "LG32": _convert_lg,
    "Panasonic": _convert_panasonic,
    "Kaseikyo": _convert_panasonic,  # Kaseikyo is Panasonic's underlying protocol
    "Pioneer": _convert_pioneer,
    "JVC": _convert_jvc,
    "Dish": _convert_dish,
    "Coolix": _convert_coolix,
}

# Protocols that must be sent as raw timing data
RAW_ONLY_PROTOCOLS = {"RCMM"}


def convert_code(
    protocol: str,
    address: str | None = None,
    command: str | None = None,
    raw_data: str | None = None,
) -> ESPHomeIRCommand | None:
    """Convert a Flipper-IRDB code entry to an ESPHome IR command.

    Returns None if the protocol is unsupported and no raw data is available.
    """
    if protocol == "Pronto" and raw_data:
        return ESPHomeIRCommand("send_ir_pronto", {"data": raw_data})

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
