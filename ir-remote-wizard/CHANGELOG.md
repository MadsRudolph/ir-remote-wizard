# Changelog

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
