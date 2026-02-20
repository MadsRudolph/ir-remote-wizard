# IR Remote Wizard

A Home Assistant add-on that auto-discovers working IR codes for any device using the [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB) database. No original remote needed — just an ESP32 IR blaster and this wizard.

## How It Works

1. **Flash once** — Load your ESP32 with the universal IR blaster firmware (`esphome/ir-blaster-discovery.yaml`)
2. **Connect** to your ESP32 IR blaster over WiFi
3. **Pick your device type** (TV, AC, Soundbar, etc.) and brand
4. **Test power codes** — the wizard sends candidates one by one until your device responds
5. **Map buttons** — test volume, channel, navigation, input, playback, etc.
6. **Save** — generates HA scripts in `scripts.yaml`, reload scripts in HA, done

No ESP32 reflashing needed after the initial setup. New remotes are added by reloading scripts in HA (instant).

## Installation

### 1. Flash the ESP32 (one-time)

Flash your ESP32 with the universal config from `esphome/ir-blaster-discovery.yaml`. This exposes API services for every supported IR protocol. After this single flash, the ESP32 never needs updating again.

Copy the file to your ESPHome config directory, add your WiFi credentials and API key to `secrets.yaml`, then flash via USB or OTA.

### 2. Add the Repository to Home Assistant

1. Go to **Settings** > **Add-ons** > **Add-on Store**
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

### 4. Open the Wizard

Click **IR Wizard** in the Home Assistant sidebar and follow the guided flow.

## Output

### HA Scripts

The wizard generates Home Assistant scripts that call the ESP32's API services at runtime:

```yaml
ir_samsung_tv_power:
  alias: "Samsung TV - Power"
  icon: mdi:power
  sequence:
    - action: esphome.ir_blaster_send_ir_samsung
      data:
        data: 0xE0E040BF
```

Save writes to `scripts.yaml`. Reload in HA: **Settings > Automations & Scenes > Scripts > Reload**.

### Dashboard Cards

Auto-generated Mushroom-themed Lovelace cards in `horizontal-stack` pairs:

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
        layout: vertical
        icon_color: red
        tap_action:
          action: call-service
          service: script.turn_on
          target:
            entity_id: script.ir_samsung_tv_power
```

## Supported Protocols

| Protocol | ESPHome Service | Notes |
|----------|----------------|-------|
| NEC / NECext / NEC42 | `send_ir_nec` | Most common TV protocol |
| Samsung32 | `send_ir_samsung` | Samsung TVs, soundbars |
| Samsung36 | `send_ir_samsung36` | Extended Samsung |
| SIRC / SIRC15 / SIRC20 | `send_ir_sony` | Sony devices |
| RC5 / RC5X | `send_ir_rc5` | Philips and European devices |
| RC6 | `send_ir_rc6` | Microsoft MCE remotes |
| LG / LG32 | `send_ir_lg` | LG TVs |
| Panasonic / Kaseikyo | `send_ir_panasonic` | Panasonic family |
| Pioneer | `send_ir_pioneer` | Pioneer AV receivers |
| JVC | `send_ir_jvc` | JVC devices |
| Dish | `send_ir_dish` | Dish Network receivers |
| Coolix | `send_ir_coolix` | AC units (Coolix protocol) |
| Pronto | `send_ir_pronto` | Universal fallback |
| Raw | `send_ir_raw` | Raw timing data |

## Architecture

```
┌──────────────────────────┐      ┌─────────────────────┐
│  HA Add-on               │      │  ESP32 IR Blaster    │
│                          │      │  (flash once)        │
│  FastAPI web app         │ ───> │                      │
│  SQLite (Flipper-IRDB)   │ API  │  ESPHome API         │
│  HA script generator     │      │  send_ir_nec         │
│  Dashboard card gen      │      │  send_ir_samsung     │
│                          │      │  send_ir_lg          │
│  Output:                 │      │  send_ir_panasonic   │
│  - scripts.yaml          │      │  send_ir_*           │
│  - Mushroom card YAML    │      │                      │
└──────────────────────────┘      └─────────────────────┘
```

- **Web UI** — FastAPI + Jinja2, served via HA ingress
- **Database** — SQLite built from Flipper-IRDB
- **ESP32 client** — aioesphomeapi for native API communication
- **Script output** — saves to `/homeassistant/scripts.yaml` for instant reload
- **Dashboard output** — Mushroom template cards in stack-in-card

## Repository Structure

```
ir-remote-wizard/
├── repository.yaml
├── ir-remote-wizard/
│   ├── config.yaml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                # FastAPI routes
│   │   ├── config.py              # Add-on configuration
│   │   ├── database.py            # SQLite access layer
│   │   ├── discovery.py           # Wizard state machine
│   │   ├── esphome_client.py      # aioesphomeapi wrapper
│   │   ├── protocol_map.py        # Flipper → ESPHome conversion
│   │   ├── yaml_generator.py      # ESPHome YAML output (legacy)
│   │   ├── ha_script_generator.py # HA script + dashboard output
│   │   ├── templates/             # Jinja2 HTML
│   │   └── static/                # CSS + JS
│   └── scripts/
│       └── build_database.py      # Flipper-IRDB parser
└── esphome/
    └── ir-blaster-discovery.yaml  # Universal ESP32 firmware config
```

## Development

The add-on runs as a Docker container. To develop locally:

```bash
# Build the database from a local Flipper-IRDB clone
python scripts/build_database.py /path/to/Flipper-IRDB irdb.sqlite3

# Run the web app
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Credits

- [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB) — IR code database
- [ESPHome](https://esphome.io/) — ESP32 firmware framework
- [aioesphomeapi](https://github.com/esphome/aioesphomeapi) — ESPHome native API client
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) — Lovelace UI components
