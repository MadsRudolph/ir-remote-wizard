# Changelog

## 0.3.9
- **Bulk Blast Confirmation Flow**: After blasting all power codes, Yes/No buttons now appear asking if the device responded. "Yes" collects all matching device IDs and proceeds to button mapping. "No" skips to results.

## 0.3.8
- **Fix: Sony SIRC repeat in HA scripts**: Generated HA scripts now emit 3 service calls with 45ms delays for Sony SIRC, matching the repeat behavior needed for Sony devices to register the command.

## 0.3.7
- **Fix: Sony SIRC Repeat**: Sony devices require the command to be sent 3+ times to register. Added repeat support to IR commands — SIRC now sends 3 transmissions with ~45ms gaps, matching real remote behavior.

## 0.3.6
- **Fix: Sony SIRC Protocol**: ESPHome represents Sony data with first-transmitted bit as MSB, but SIRC sends LSB-first. Data word is now bit-reversed to match ESPHome's encoding (e.g. TV Power: logical `0x95` → `0xA90`).

## 0.3.5
- **Fix: Bulk Blast (Try All)**: Button now works correctly behind HA Ingress — the fetch URL was missing the ingress path prefix.
- **Fix: Flipper NEC Protocol**: Standard NEC now adds complement bytes as ESPHome expects (e.g. address `0x04` → `0xFB04`). NECext separated to handle 16-bit addresses correctly.
- **Fix: Flipper Samsung32 Protocol**: Bit-reverse bytes before building the data frame (Flipper stores LSB-first, ESPHome sends MSB-first).

## 0.3.4
- **Mushroom Dashboard Cards**: Generated dashboard YAML now uses `custom:mushroom-template-card` in `custom:stack-in-card` with `horizontal-stack` pairs, matching common HA dashboard styles. Includes per-category icon colors.

## 0.3.2
- **Fix: Multi-line Pronto Parsing**: Rewrote Pronto log parser with a two-pass approach. ESPHome splits Pronto data across 2-3 log lines with component prefixes — the new parser correctly collects hex data across line boundaries.

## 0.3.1
- **Fix: Coolix Protocol**: ESPHome's `transmit_coolix` requires `first` parameter, not `data`.

## 0.3.0
- **No More Reflashing**: Results now generate Home Assistant scripts instead of ESPHome button YAML. Flash the ESP32 once with the universal firmware, then just "Reload Scripts" in HA for instant updates.
- **HA Script Output**: New primary output format writes to `scripts.yaml` — each confirmed button becomes a callable HA script with proper icons.
- **Dashboard Card**: Auto-generated Lovelace dashboard card snippet that calls the new scripts.
- **6 New Protocols**: Added native support for LG, Panasonic, Pioneer, JVC, Dish, and Coolix (no more raw-only fallback for these).
- **Universal Firmware**: ESPHome config template now includes all protocol services out of the box.
- **ESPHome YAML Preserved**: Still available in a collapsible section on the results page for advanced users who prefer firmware-baked buttons.

## 0.2.3
- **Connectivity Fix**: Restored `web_server` to the Full Config template so you can continue to access your device directly via its IP address in the browser.
- **Dynamic Template**: The Full Config template now uses your device's actual name and friendly name, preventing hostname conflicts when flashing.

## 0.2.2
- **Fix**: Dynamic YAML Export — now saves to your specific device config file (e.g., `remote.yaml`) instead of a hardcoded generic name.
- **UI**: Display the filename and merge status after saving YAML.

## 0.2.1
- **Critical Fix**: Resolved `TemplateSyntaxError` (unknown tag 'endblock') that caused "Internal Server Error" on certain pages.
- **Bug Fix**: Robust log decoding in `esphome_client.py` to prevent `TypeError` on various Python environments.
- **UI Enhancement**: One-Click Save for Smart Learn chips — immediately assign and save captured buttons.
- **UI visibility**: Fixed device/brand names being unreadable (black text) on dark backgrounds.
- **Cache Management**: Added asset versioning to force reload of new UI enhancements in Home Assistant Ingress.

## 0.2.0
- **UI Redesign**: Complete Glassmorphism overhaul with a modern slate-blue theme.
- **Bulk Blast**: Added capability to rapidly cycle through all candidate power codes.
- **Learn Mode Enhancements**: 
    - Interactive "Smart Chips" for common buttons.
    - Real-time IR Pulse Wave visualization.
    - Improved decoding logic for physical remote captures.
- **Persistence**: Wizard progress is now saved locally in the browser.
- **Documentation**: Added professional README and detailed DOCS for better user onboarding.
- **Dashboard snippets**: Exported results now include Home Assistant Manual Card YAML.

## 0.1.1
- Initial public release.
- Support for Flipper-IRDB integration.
- Basic IR capture and test functionality.
