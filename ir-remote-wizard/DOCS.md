# IR Remote Wizard — Documentation

The IR Remote Wizard is a Home Assistant add-on that discovers, tests, and generates IR remote configurations using an ESP32 IR blaster and the Flipper-IRDB database.

## Quick Start

### 1. Build & Flash the ESP32 (one-time)

First, build the IR blaster hardware. See **[BUILD_GUIDE.md](BUILD_GUIDE.md)** for the full schematic, bill of materials, and wiring instructions.

Then flash your ESP32 with `esphome/ir-blaster-discovery.yaml`. This universal firmware exposes API services for every supported IR protocol — you never need to reflash it again.

Copy the file to your ESPHome config directory, add your WiFi credentials and API key to `secrets.yaml`, then flash via USB or OTA from the ESPHome dashboard.

### 2. Install the Add-on

1. Go to **Settings > Add-ons > Add-on Store**
2. Click the three dots (top right) > **Repositories**
3. Add: `https://github.com/MadsRudolph/ir-remote-wizard`
4. Find **IR Remote Wizard** in the store and install it

### 3. Configure

In the add-on configuration, set:

| Option | Description |
|--------|-------------|
| `esp32_host` | IP address or hostname of your ESP32 IR blaster |
| `esp32_port` | ESPHome API port (default: 6053) |
| `api_encryption_key` | API encryption key from your ESPHome config |

### 4. Run the Wizard

Click **IR Wizard** in the Home Assistant sidebar and follow the guided flow:

1. **Connect** — Enter your ESP32's IP and API key.
2. **Device Type** — Select TV, AC, Soundbar, etc.
3. **Brand** — Pick the manufacturer (or "Unknown" to try all).
4. **Discover** — The wizard sends power code candidates. Use **Bulk Blast** to test many codes quickly, or step through one at a time.
5. **Map Buttons** — Once the right remote profile is found, confirm individual buttons (volume, channel, navigation, etc.).
6. **Results** — View and save the generated HA scripts.

### 5. Save and Activate

Click **Save to Home Assistant** on the results page. This writes to `scripts.yaml` in your HA config directory.

Then reload scripts: **Settings > Automations & Scenes > Scripts > (three dots) > Reload**.

Your new IR scripts appear instantly — no ESP32 reflashing needed.

## Learn Mode

If your device isn't in the Flipper-IRDB database, use **Learn Mode**:

1. On the device type page, click **Learn Mode**.
2. Point your physical remote at the ESP32's IR receiver and press a button.
3. The wizard captures the code and shows the decoded protocol.
4. Click **Test** to send it back through the ESP32 and verify it works.
5. Name the button and save it.
6. Repeat for each button, then click **Done** to generate scripts.

Learn Mode supports all protocols including Pronto fallback for remotes that ESPHome can't natively decode.

## Output Formats

### HA Scripts (primary)

The wizard generates Home Assistant script YAML that calls the ESP32's existing API services at runtime:

```yaml
ir_samsung_tv_power:
  alias: "Samsung TV - Power"
  icon: mdi:power
  sequence:
    - action: esphome.ir_blaster_send_ir_samsung
      data:
        data: 0xE0E040BF
```

These go in `scripts.yaml` and become available after a script reload.

### Dashboard Cards

The wizard also generates a Mushroom-themed Lovelace card snippet:

```yaml
type: custom:stack-in-card
mode: vertical
cards:
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        entity: script.ir_samsung_tv_power
        icon: mdi:power
        primary: "Power"
        secondary: ""
        layout: vertical
        icon_color: red
        tap_action:
          action: call-service
          service: script.turn_on
          target:
            entity_id: script.ir_samsung_tv_power
```

Paste this into a Manual Card on your dashboard. Requires the [Mushroom](https://github.com/piitaya/lovelace-mushroom) and [stack-in-card](https://github.com/custom-cards/stack-in-card) custom cards.

### ESPHome YAML (advanced)

The original ESPHome `button:` YAML is still available in a collapsible section on the results page, for users who prefer baking buttons directly into firmware.

## Supported Protocols

| Protocol | ESPHome Service | Notes |
|----------|----------------|-------|
| NEC / NECext / NEC42 | `send_ir_nec` | Most common TV protocol |
| Samsung32 | `send_ir_samsung` | Samsung TVs, soundbars |
| Samsung36 | `send_ir_samsung36` | Extended Samsung protocol |
| SIRC / SIRC15 / SIRC20 | `send_ir_sony` | Sony devices |
| RC5 / RC5X | `send_ir_rc5` | Philips and European devices |
| RC6 | `send_ir_rc6` | Microsoft MCE remotes |
| LG / LG32 | `send_ir_lg` | LG TVs |
| Panasonic / Kaseikyo | `send_ir_panasonic` | Panasonic and Kaseikyo-family |
| Pioneer | `send_ir_pioneer` | Pioneer AV receivers |
| JVC | `send_ir_jvc` | JVC devices |
| Dish | `send_ir_dish` | Dish Network receivers |
| Coolix | `send_ir_coolix` | AC units (Coolix protocol) |
| Pronto | `send_ir_pronto` | Universal fallback |
| Raw | `send_ir_raw` | Raw timing data |

## ESPHome Configuration

The universal firmware in `esphome/ir-blaster-discovery.yaml` includes API services for all protocols above. Key sections:

```yaml
remote_transmitter:
  pin: GPIO4
  carrier_duty_percent: 33%

remote_receiver:
  pin:
    number: GPIO14
    inverted: true
  dump: all
```

Adjust the GPIO pins to match your board. The `dump: all` on the receiver enables Learn Mode to capture any protocol.

## Troubleshooting

- **Connection Failed** — Ensure the ESP32 is on the same network and the API port (6053) is accessible. Check the API encryption key matches.
- **No Response** — Ensure the IR LED is pointed at the device's receiver. Check ESPHome logs for `remote_transmitter` activity.
- **Self-Check Failed** — The IR LED and receiver on your board can't see each other. This is normal on some boards and doesn't affect normal operation.
- **"IR signal detected but could not parse protocol"** — The ESP32 received a signal but couldn't decode it as a known protocol. This is common with some remotes; the Pronto fallback should handle most cases.
- **Scripts not appearing after save** — Go to **Settings > Automations & Scenes > Scripts > (three dots) > Reload**. No HA restart needed.

---
*Developed for the Home Assistant community.*
