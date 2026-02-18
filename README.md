# IR Remote Wizard

A Home Assistant add-on that auto-discovers working IR codes for any device using the [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB) database. No original remote needed — just an ESP32 IR blaster and this wizard.

## How It Works

1. **Connect** to your ESP32 IR blaster over WiFi
2. **Pick your device type** (TV, AC, Soundbar, etc.) and brand
3. **Test power codes** — the wizard sends candidates one by one until your device responds
4. **Map buttons** — test volume, channel, navigation, input, playback, etc.
5. **Export** — generates an ESPHome YAML config with all confirmed working buttons

The add-on contains a pre-built SQLite database of thousands of IR codes parsed from the Flipper-IRDB. It connects to your ESP32 via the ESPHome native API to send test codes in real time.

## Installation

### 1. Flash the ESP32

Flash your ESP32 with the discovery config from `esphome/ir-blaster-discovery.yaml`. This config exposes API services that allow the add-on to send any IR code dynamically.

Copy the file to your ESPHome config directory, add your WiFi credentials and API key to `secrets.yaml`, then flash via USB or OTA.

### 2. Add the Repository to Home Assistant

1. Go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the three dots (top right) → **Repositories**
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

## Supported Protocols

| Protocol | ESPHome Action |
|----------|---------------|
| NEC / NECext / NEC42 | `transmit_nec` |
| Samsung32 | `transmit_samsung` |
| RC5 / RC5X | `transmit_rc5` |
| RC6 | `transmit_rc6` |
| SIRC / SIRC15 / SIRC20 | `transmit_sony` |
| Kaseikyo, RCMM, Pioneer | `transmit_raw` (converted to timing data) |
| Raw | `transmit_raw` (direct timing data) |

## Architecture

```
┌──────────────────────────┐      ┌─────────────────┐
│  HA Add-on               │      │  ESP32 IR Blaster│
│                          │      │                  │
│  FastAPI web app         │ ───> │  ESPHome API     │
│  SQLite (Flipper-IRDB)   │ API  │  services:       │
│  YAML generator          │      │  send_ir_nec     │
│                          │      │  send_ir_raw     │
└──────────────────────────┘      │  send_ir_*       │
                                  └─────────────────┘
```

- **Web UI** — FastAPI + Jinja2, served via HA ingress
- **Database** — SQLite built from Flipper-IRDB at first startup
- **ESP32 client** — aioesphomeapi for native API communication
- **YAML output** — saves to `/homeassistant/esphome/` for flashing from the ESPHome dashboard

## Repository Structure

```
ir-remote-wizard/
├── repository.yaml
├── ir-remote-wizard/
│   ├── config.yaml
│   ├── Dockerfile
│   ├── run.sh
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI routes
│   │   ├── config.py            # Add-on configuration
│   │   ├── database.py          # SQLite access layer
│   │   ├── discovery.py         # Wizard state machine
│   │   ├── esphome_client.py    # aioesphomeapi wrapper
│   │   ├── protocol_map.py      # Flipper → ESPHome conversion
│   │   ├── yaml_generator.py    # ESPHome YAML output
│   │   ├── templates/           # Jinja2 HTML
│   │   └── static/              # CSS + JS
│   └── scripts/
│       └── build_database.py    # Flipper-IRDB parser
└── esphome/
    └── ir-blaster-discovery.yaml  # ESP32 config with dynamic IR services
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
