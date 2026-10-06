# Shelly Elevate for Home Assistant

Home Assistant integration for Shelly Wall Displays running [ShellyElevate](https://github.com/RapierXbox/ShellyElevate).

Every display shows up as one device with its relays, sensors, screen, media player, voice
assistant and Bluetooth proxy. You can also back up and copy display settings, update the app,
and use a display relay as a thermostat. The sidebar panel lets you install ShellyElevate on a
new display over ADB, or put a display back to the stock Shelly app.

The display still works fine without Home Assistant.

## What you need

- Home Assistant 2026.8 or newer
- [HACS](https://hacs.xyz/docs/use/)
- A Shelly Wall Display in the same network

## Install

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RapierXbox&repository=shellyelevateintegration&category=integration)

Or add it by hand:

1. HACS → ⋮ (top right) → Custom repositories
2. Add `https://github.com/RapierXbox/shellyelevateintegration` as type Integration
3. Search for Shelly Elevate in HACS and download it
4. Restart Home Assistant
5. Go to Settings → Devices & services → Add integration → Shelly Elevate. Pick
   "Add a display" if ShellyElevate already runs on it, or "Only add the panel" if you still
   need to put ShellyElevate on a display. Displays with ShellyElevate are also found
   automatically. The Shelly Elevate panel then shows up in the sidebar (admins only).

## Putting ShellyElevate on a display

1. Connect the display to Wi-Fi in the Shelly settings under Network.
2. Update the display to the newest Shelly firmware.
3. In the Shelly settings open General → About device and tap Firmware (F) and Hardware (H)
   in this order: F H F F H F H H. This unlocks the Android settings.
4. In the Android Developer options, turn on only ADB debugging and ADB over Wi-Fi (port 5555).
   On newer Shelly firmware, also turn on ADB - WiFi in the Shelly developer settings
   (it shows the display's address with port 5555). Note the IP address.
5. Open Shelly Elevate in the Home Assistant sidebar (see step 5 above if it isn't there),
   go to Install and enter the IP.

Home Assistant installs the app and adds the display. To undo all of it, use
Revert to stock in the panel.

## Versions

Every change to the integration that lands on main is released automatically as the next patch
version (0.1.0, 0.1.1, ...), and HACS shows it as an update. Minor and major versions are released
by hand: Actions → Release → Run workflow.

## Building the panel

```bash
cd frontend
npm ci
npm run build
```

## License

Apache-2.0
