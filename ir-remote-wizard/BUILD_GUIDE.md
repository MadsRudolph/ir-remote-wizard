# ESP32 IR Blaster — Build Guide

How to build the ESP32 IR blaster/receiver that powers the IR Remote Wizard.

## What You're Building

A WiFi-connected IR blaster and receiver using an ESP32, an IR LED (with transistor driver), and an IR receiver module. Once built and flashed with the included ESPHome firmware, it connects to Home Assistant and can send/receive any IR signal.

## Bill of Materials

| Qty | Component | Value / Part | Notes |
|-----|-----------|-------------|-------|
| 1 | ESP32 dev board | Any ESP32 with USB | ESP32-DevKitC, NodeMCU-32S, etc. |
| 1 | IR emitter LED | SFH4546 | 940 nm, high radiant intensity |
| 1 | IR receiver module | VS1838 | 38 kHz demodulator built-in |
| 1 | NPN transistor | 2N2222 | IR LED driver |
| 1 | Resistor | 1 kΩ | Base resistor for 2N2222 |
| 1 | Resistor | 22 Ω (from 3.3V) or 33 Ω (from 5V) | Current-limiting for IR LED |
| 1 | Capacitor | 100 nF ceramic | Decoupling on VS1838 VCC |
| - | Breadboard or protoboard | - | For assembly |
| - | Hookup wire | 22–24 AWG | Connections |

### Optional

| Qty | Component | Value | Notes |
|-----|-----------|-------|-------|
| 1–3 | IR emitter LED | SFH4546 | Additional LEDs for wider coverage |
| 1 | Capacitor | 10 µF electrolytic | Power rail bulk decoupling |

## GPIO Pinout

| Function | GPIO | Description |
|----------|------|-------------|
| IR Transmit | GPIO4 | Output to IR LED (via 2N2222) |
| IR Receive | GPIO14 | VS1838 demodulated signal input |
| Status LED | GPIO2 | Onboard LED — blinks during WiFi connect |

> These pins match the included ESPHome firmware (`esphome/ir-blaster-discovery.yaml`). If you use different GPIOs, update the YAML to match.

## Circuit

### IR Transmitter

The ESP32 drives the IR LED through a 2N2222 NPN transistor (low-side switch) to source enough current. The ESP32 GPIO alone can't drive an IR LED adequately.

```
                     3.3V (or 5V)
                       |
                    [22Ω]  (or 33Ω from 5V)
                       |
                   SFH4546
                   (anode)
                       |
                   SFH4546
                  (cathode)
                       |
                  Collector
                       |
 ESP32 GPIO4 ---[1kΩ]--- Base
                            2N2222
                       |
                   Emitter
                       |
                      GND
```

**Current-limiting resistor calculation:**
The SFH4546 has a forward voltage of ~1.35V at 100 mA.
- **From 3.3V:** R = (3.3 − 1.35) / 0.1 = 19.5 Ω → **use 22 Ω** (~89 mA)
- **From 5V:** R = (5.0 − 1.35) / 0.1 = 36.5 Ω → **use 33 Ω** (~110 mA)

These are pulsed values — IR LEDs tolerate higher currents during short 38 kHz carrier bursts.

### IR Receiver

The VS1838 is a complete IR receiver with built-in bandpass filter, demodulator, and AGC. Output is active-low.

```
                3.3V
                  |
            +-----+-----+
            |            |
         [100nF]      VS1838
          (cap)         |
            |       +---+---+
           GND      |   |   |
                    OUT GND VCC
                     |   |   |
                     |  GND 3.3V
                     |
                ESP32 GPIO14
               (input, pullup)
```

**VS1838 pin order** (looking at the front / dome side): **OUT | GND | VCC** (left to right). Some breakout boards may differ — always check your module's pinout.

## Flashing the Firmware

1. Copy `esphome/ir-blaster-discovery.yaml` to your ESPHome config directory.
2. Add your WiFi credentials and API key to `secrets.yaml`:
   ```yaml
   wifi_ssid: "YourNetwork"
   wifi_password: "YourPassword"
   api_key: "your-api-encryption-key"
   ota_password: "your-ota-password"
   fallback_password: "your-fallback-password"
   ```
3. Flash via USB: `esphome run ir-blaster-discovery.yaml`
4. After the first flash, all future updates can be done OTA (over WiFi).

> **Tip:** If auto-reset fails during flash, use manual boot mode: unplug USB → hold BOOT → plug in USB → release BOOT. Then flash with `--before no-reset`.

## Hardware Pitfalls

**SFH4546 LED polarity** — Some SFH4546 units have reversed polarity markings compared to typical LEDs (short leg = anode). Always verify with a multimeter in diode mode before soldering.

**2N2222 pinout** — The 2N2222 pinout varies between manufacturers and packages (TO-92 vs TO-18). Verify with a multimeter in diode mode:
- Base → Emitter: ~0.6V forward drop
- Base → Collector: ~0.6V forward drop
- Emitter → Collector: no conduction (OL)

**Testing the IR LED** — IR is invisible to the naked eye, but phone cameras can see it as a faint purple/white glow. Use this to quickly check the LED is firing.

**GPIO test** — To verify the ESP32 GPIO output, temporarily connect a visible LED (with a 330Ω resistor) to the pin. A faint glow confirms the 38 kHz modulated signal is present.

## Verifying the Build

Once flashed and powered on:

1. The status LED (GPIO2) should blink during WiFi connection, then go solid.
2. Open the IR Wizard add-on in Home Assistant and connect to the ESP32.
3. Use the **Self-Check** button — it sends an IR signal and checks if the receiver picks it up. This confirms both TX and RX are working. (Note: self-check may fail on some boards where the LED and receiver don't face each other — this doesn't affect normal operation.)
4. Try Learn Mode: point any IR remote at the VS1838 and press a button. The wizard should capture and display the protocol and code.
