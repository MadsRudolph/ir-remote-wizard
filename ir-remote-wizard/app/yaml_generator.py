"""Generate ESPHome YAML config from confirmed working IR codes."""

from __future__ import annotations

from .discovery import ConfirmedButton, WizardSession
from .protocol_map import HOLD_BUTTONS, convert_code


def generate_yaml(session: WizardSession) -> str:
    """Generate a complete ESPHome YAML config with all confirmed buttons."""
    brand = session.matched_brand or "Unknown"
    device_type = session.device_type or "Device"

    lines = [
        f"# IR Remote — {brand} {device_type}",
        f"# Auto-discovered by IR Remote Wizard",
        "",
        "esphome:",
        "  name: ir-blaster",
        f"  friendly_name: IR Blaster ({brand} {device_type})",
        "",
        "esp32:",
        "  board: esp32dev",
        "",
        "wifi:",
        "  ssid: !secret wifi_ssid",
        "  password: !secret wifi_password",
        "",
        "logger:",
        "",
        "api:",
        "  encryption:",
        "    key: !secret api_key",
        "",
        "ota:",
        "  platform: esphome",
        "",
        "remote_transmitter:",
        "  pin: GPIO4",
        "  carrier_duty_percent: 33%",
        "",
    ]

    if not session.confirmed_buttons:
        lines.append("# No buttons were confirmed during discovery.")
        return "\n".join(lines)

    lines.append("button:")

    for btn in session.confirmed_buttons:
        cmd = convert_code(btn.protocol, btn.address, btn.command, btn.raw_data)
        if not cmd:
            continue

        button_id = _sanitize_id(btn.name)
        lines.append(f"  - platform: template")
        lines.append(f"    name: \"{btn.name}\"")
        lines.append(f"    id: btn_{button_id}")
        lines.append(f"    on_press:")

        if cmd.service == "send_ir_nec":
            lines.append(f"      - remote_transmitter.transmit_nec:")
            lines.append(f"          address: 0x{cmd.data['address']:04X}")
            lines.append(f"          command: 0x{cmd.data['command']:04X}")
        elif cmd.service == "send_ir_samsung":
            lines.append(f"      - remote_transmitter.transmit_samsung:")
            lines.append(f"          data: 0x{cmd.data['data']:08X}")
        elif cmd.service == "send_ir_sony":
            lines.append(f"      - remote_transmitter.transmit_sony:")
            lines.append(f"          data: 0x{cmd.data['data']:04X}")
            lines.append(f"          nbits: {cmd.data['nbits']}")
        elif cmd.service == "send_ir_rc5":
            lines.append(f"      - remote_transmitter.transmit_rc5:")
            lines.append(f"          address: 0x{cmd.data['address']:02X}")
            lines.append(f"          command: 0x{cmd.data['command']:02X}")
        elif cmd.service == "send_ir_rc6":
            lines.append(f"      - remote_transmitter.transmit_rc6:")
            lines.append(f"          address: 0x{cmd.data['address']:02X}")
            lines.append(f"          command: 0x{cmd.data['command']:02X}")
        elif cmd.service == "send_ir_raw":
            code_str = str(cmd.data["code"])
            lines.append(f"      - remote_transmitter.transmit_raw:")
            lines.append(f"          carrier_frequency: 38000")
            lines.append(f"          code: {code_str}")

        lines.append("")

    return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """Convert a button name to a valid ESPHome ID."""
    return name.lower().replace(" ", "_").replace("-", "_")


def save_yaml(yaml_content: str, output_path: str) -> None:
    """Write YAML content to a file."""
    with open(output_path, "w") as f:
        f.write(yaml_content)
