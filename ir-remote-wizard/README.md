# IR Remote Wizard

Discover, learn, and control any IR device from Home Assistant — no reflashing required.

![Design Preview](https://raw.githubusercontent.com/MadsRudolph/ir-remote-wizard/main/logo.png)

## Features

- **No Reflashing** — Flash your ESP32 once with the universal firmware. New remotes are added instantly by reloading scripts in HA.
- **HA Script Output** — Generates Home Assistant scripts (not ESPHome button YAML), so adding a new remote takes seconds instead of minutes.
- **Mushroom Dashboard Cards** — Auto-generated Lovelace card snippets that match the Mushroom theme out of the box.
- **Bulk Blast** — Test dozens of power codes in seconds to find your device instantly.
- **Learn Mode** — Capture codes from any physical remote using your ESP32's IR receiver.
- **13 Protocols** — NEC, Samsung, Samsung36, Sony, RC5, RC6, LG, Panasonic, Pioneer, JVC, Dish, Coolix, and Pronto/Raw fallback.
- **Flipper-IRDB** — Built-in database of thousands of IR codes from the Flipper-IRDB project.

## How It Works

1. Flash your ESP32 with `esphome/ir-blaster-discovery.yaml` (one-time setup).
2. Open the wizard, connect to your ESP32, pick device type and brand.
3. Test power codes until your device responds, then map other buttons.
4. Click **Save to Home Assistant** — writes to `scripts.yaml`.
5. Reload scripts in HA: **Settings > Automations & Scenes > Scripts > Reload**.
6. Done! Your new IR scripts appear instantly.

## Installation

1. Add this repository to your Home Assistant Add-ons.
2. Install the **IR Remote Wizard**.
3. Point it at your ESPHome-enabled IR Blaster.
4. Follow the guided wizard flow.

## Documentation

- **[BUILD_GUIDE.md](BUILD_GUIDE.md)** — How to build the ESP32 IR blaster hardware (schematic, BOM, wiring)
- **[DOCS.md](DOCS.md)** — Setup instructions, ESPHome configuration, and troubleshooting

---
*Created by Mads Rudolph*
