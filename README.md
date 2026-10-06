# Shelly Elevate for Home Assistant

A HACS integration for **Shelly Wall Displays running [ShellyElevate](https://github.com/RapierXbox/ShellyElevate)**.
Each display is one Home Assistant device: relays, sensors, the screen, a media player, an Assist
voice satellite, a Bluetooth proxy, settings, backups, profiles, app updates and an optional
thermostat. A sidebar panel manages the fleet, installs the app over ADB and can revert a display
to the stock Shelly app.

The display keeps working without Home Assistant; every Home Assistant feature is optional.

## Requirements

- Home Assistant **2026.8** or newer
- [HACS](https://hacs.xyz/docs/use/) installed in Home Assistant
- A Shelly Wall Display on the same network (with ShellyElevate, or install it from the panel below)

## Installation (HACS)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RapierXbox&repository=shellyelevateintegration&category=integration)

Or by hand:

1. In Home Assistant open **HACS**, then the **⋮** menu (top right) → **Custom repositories**.
2. Repository: `https://github.com/RapierXbox/shellyelevateintegration`, type: **Integration** → **Add**.
3. Search HACS for **Shelly Elevate**, open it and select **Download**.
4. Restart Home Assistant (**Settings → System → ⋮ → Restart Home Assistant**).
5. Displays running ShellyElevate are discovered automatically (**Settings → Devices & services**).
   Otherwise add one with **Add integration → Shelly Elevate** and enter its IP address.
   The **Shelly Elevate** panel appears in the sidebar for administrators.

Updates show up in HACS like any other integration.

## Installing ShellyElevate on a display

1. Connect the display to Wi-Fi in the Shelly settings under **Network**.
2. Update the display to the newest Shelly firmware.
3. Unlock the Android settings: in the Shelly settings open **General → About device** and tap
   Firmware (F) and Hardware (H) in the order **F H F F H F H H**.
4. In the Android *Developer options*, enable only **ADB debugging** and **ADB over Wi-Fi**
   (port 5555). On newer Shelly firmware, also turn on **ADB - WiFi** in the Shelly developer
   settings (it shows the display's address with port 5555). Note the display's IP address.
5. Open **Shelly Elevate** in the Home Assistant sidebar, go to **Install** and enter the IP.

Home Assistant installs the app, applies your default profile and adds the display. To undo
everything, use **Revert to stock…** in the panel.

## Building the panel

```bash
cd frontend && npm ci && npm run build
```

## License

Apache-2.0
