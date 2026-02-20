# IR Remote Wizard 🧙‍♂️

The IR Remote Wizard is an interactive tool for Home Assistant to help you discover, test, and generate configuration for ESPHome IR blasters.

## Getting Started

1.  **Configure ESPHome**: Ensure your ESP32 has an IR Transmitter (`remote_transmitter`) and optionally an IR Receiver (`remote_receiver`).
2.  **Open the Wizard**: Click the "Open Web UI" button in the addon dashboard.
3.  **Connect**: Enter the IP address or hostname of your ESP32.
4.  **Follow the Steps**:
    *   Select your device type (e.g., TV, AC, Soundbar).
    *   Select the brand.
    *   **Discover**: The wizard will cycle through potential IR codes. Use "Bulk Blast" to quickly test many codes at once.
    *   **Map Buttons**: Once the correct profile is found, test individual buttons like Volume and Mute.
5.  **Save & Install**: Copy the generated YAML into your ESPHome configuration and flash your device.

## Learn Mode 🧠

If your device isn't in the database, you can use **Learn Mode**. Point your physical remote at the ESP32's IR receiver and press a button. The wizard will capture the code, let you test it, and save it to your final configuration.

## Features

- **Glassmorphism UI**: A professional, modern interface.
- **Bulk Blast**: Rapidly discover power codes without manual clicking.
- **Smart Chips**: Quick selection for common buttons in Learn Mode.
- **Pulse Visualization**: See a simulated waveform when IR signals are sent or received.
- **Persistence**: Your wizard session is saved in your browser, so you don't lose progress if you refresh.

## Troubleshooting

- **Connection Failed**: Ensure the ESP32 is on the same network and the API port (6053) is accessible.
- **No Response**: Ensure your IR LED is pointed directly at the device's receiver. Check your ESPHome logs for `remote_transmitter` activity.
- **Self-Check Failed**: This usually means the IR LED and receiver on your board can't "see" each other. You can still use the wizard.

## ESPHome Tips

For best results, use the following component IDs in your ESPHome YAML:
```yaml
remote_transmitter:
  pin: GPIO13
  carrier_duty_cycle: 50%

remote_receiver:
  pin: GPIO14
  dump: all
```

---
*Developed for the Home Assistant community.*
