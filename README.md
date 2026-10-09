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

## Setup fields

When you add a display by hand:

| Field | Description |
| --- | --- |
| Host | IP address or hostname of the display. |
| Port | Port of the ShellyElevate API, 8443 by default. Older app versions are found on port 8080 automatically. |
| Pairing code | The 6-digit code the display shows during setup. Not asked for older app versions, which have no pairing. |
| Profile | Only shown if you saved settings profiles: a profile to write to the new display. |

The address can be changed later with Reconfigure on the integration page. When the display
gets a new address and announces itself, Home Assistant moves it on its own once it presents
the certificate it was paired with.

## Supported displays

Every Shelly Wall Display that runs ShellyElevate: Wall Display, Wall Display 2, X2, XL, U1,
X2i, X1i and D1. Which entities a display gets depends on its hardware: the D1 has no relays,
the XL, X2i and X1i have no temperature sensor of their own, and the second relay of the X2, XL,
X2i and X1i needs the power base.

Displays with an older ShellyElevate version (without the native Home Assistant API) can be
added as well, with fewer features (see Known limitations).

## What you get

Each display is one device with these entities, as far as the display supports them and the
feature is turned on:

- Relays as switches (or lights, see Options), the dimmer, wired inputs as binary sensors and
  as events, the hardware buttons and the power button as events, swipes on the screen as events
- Sensors: temperature, humidity, illuminance, proximity, screen brightness, power of the dimmer,
  and diagnostic sensors for Wi-Fi signal, CPU temperature, free memory and app start time
- The screen as a light (on/off and brightness), wake and sleep buttons, night mode, screensaver,
  automatic brightness, wake on proximity and touch to wake
- A media player (speaker), a notify entity that shows messages on the screen, and the dashboard
  URL as a text entity
- Voice assistant: an Assist satellite with wake word, microphone mute, pipeline and finished
  speaking detection
- Bluetooth proxy: the display forwards Bluetooth advertisements to Home Assistant
- Screenshots as an image entity (taken by the app, or over ADB where it cannot), a restart app
  button, and an update entity for the ShellyElevate app
- A thermostat that switches a relay (see Options)

Turning media, the voice assistant, the Bluetooth proxy or MQTT off on the display removes their
entities, turning them on adds them again. Entities of other settings, such as the screensaver,
proximity wake or swipe events, stay and are unavailable while their setting is off.

### Actions

| Action | What it does |
| --- | --- |
| `shellyelevateintegration.backup_settings` | Takes a snapshot of the settings of one or more displays. |
| `shellyelevateintegration.restore_settings` | Restores a settings backup (only changed settings are written). |
| `shellyelevateintegration.apply_profile` | Applies a settings profile to displays. |
| `shellyelevateintegration.save_profile` | Saves the settings of a display as a profile (per-display settings are left out). |
| `shellyelevateintegration.copy_settings` | Copies settings from one display to others. |
| `shellyelevateintegration.export_settings` | Returns the settings of a display as JSON. |
| `shellyelevateintegration.import_settings` | Imports exported settings as a backup and optionally applies them. |
| `shellyelevateintegration.get_settings` | Returns all settings of a display (secrets redacted). |
| `shellyelevateintegration.set_settings` | Writes raw settings to displays. |
| `shellyelevateintegration.navigate` | Shows a dashboard path or URL on the display (not persisted). |
| `shellyelevateintegration.show_message` | Shows a message on the screen. |
| `shellyelevateintegration.adb_shell` | Runs a shell command on the display over ADB (admin only). |
| `shellyelevateintegration.install_app` | Installs (or reinstalls) the ShellyElevate app over ADB. |
| `shellyelevateintegration.revert_display` | Removes ShellyElevate over ADB and gives the display back to the stock Shelly app. |

Every event the display reports is also fired on the event bus as `shellyelevateintegration_event`.

## Options

Settings → Devices & services → Shelly Elevate → Configure on a display:

| Option | Description |
| --- | --- |
| Show relays as lights | Creates the relays as light entities instead of switches. |
| Create a thermostat | Creates a thermostat that switches a relay of the display based on the temperature. |
| Back up settings automatically | Takes a snapshot of the display settings after every change. |
| Number of backups to keep | Older automatic backups are removed first, named backups are kept longest. |
| Update channel | Stable, or beta to also get pre-releases of the app. |
| Use ADB (port 5555) | Lets Home Assistant install and update the app, take screenshots and rescue the display over ADB. ADB over Wi-Fi must stay on. |
| Restart the app automatically | Restarts the app over ADB when it stops responding (needs ADB). |

With the thermostat turned on, a second page asks for the relay, the temperature sensor (the
display's own sensor if left empty), heat or cool, the tolerance around the target temperature,
the minimum time between two switching operations, and the lowest and highest target
temperature. The control loop runs in Home Assistant.

## How data is updated

Displays with the current app push every change over a WebSocket (TLS, with the token from
pairing), so entities update right away. If the connection drops, the integration reconnects on
its own, waiting 1 second at first and up to 60 seconds between attempts. Displays with an older
app version are polled every 5 seconds (relays, inputs, night mode, screen) and every 30 seconds
(sensors, settings). The app update entity checks the GitHub releases every 6 hours.

## Examples

Turn off the kitchen lights with a swipe to the left on the display:

```yaml
triggers:
  - trigger: state
    entity_id: event.kitchen_display_swipe
    not_from: unavailable
conditions:
  - condition: state
    entity_id: event.kitchen_display_swipe
    attribute: event_type
    state: left
actions:
  - action: light.turn_off
    target:
      area_id: kitchen
```

Show a message when someone rings the doorbell:

```yaml
action: shellyelevateintegration.show_message
data:
  device_id: YOUR_DISPLAY_DEVICE_ID
  title: Doorbell
  message: Someone is at the door
  duration: 10
```

Other ideas: open the camera dashboard with `navigate` when motion is detected, use the display
as a voice satellite in every room, or let a relay of the display run floor heating through the
thermostat.

## Known limitations

- Displays with an older ShellyElevate version have no authentication on their HTTP API, are
  polled instead of pushing changes, and have no voice assistant, no Bluetooth proxy and no
  event entities. Update the app and Home Assistant asks you to pair the display.
- The voice assistant needs the Assist pipeline and the Bluetooth proxy needs the Bluetooth
  integration in Home Assistant.
- Installing the app, granting permissions and reverting to stock need ADB over Wi-Fi on the
  display, and so do screenshots on displays where the app cannot take them itself.
- Displays without their own temperature sensor (XL, X2i, X1i) need another temperature sensor
  for the thermostat. The D1 has no relays and cannot be a thermostat.

## Troubleshooting

- **The display is unavailable:** check that it is on and in the network. The integration
  reconnects on its own and logs once when the display goes away and once when it is back.
- **Home Assistant asks to pair again:** the display no longer accepts the token or shows a
  different certificate, for example after the app was reinstalled. Follow the repair and enter
  the code from the display.
- **Repairs:** Home Assistant shows a repair when the app does not respond, permissions are
  missing, the display also shows up as a second device, or the unauthenticated legacy HTTP API
  is turned on. Most of them can be fixed from the repair itself.
- **Report a problem:** download the diagnostics of the display (tokens, addresses and secrets are
  redacted, also in the app log and logcat) and turn on debug logging on the integration page,
  then open an
  [issue](https://github.com/RapierXbox/shellyelevateintegration/issues).

## Removing the integration

1. Settings → Devices & services → Shelly Elevate → ⋮ next to each display → Delete. Home
   Assistant revokes its token on the display. Delete the Shelly Elevate panel entry the same way.
2. Remove Shelly Elevate in HACS and restart Home Assistant.

ShellyElevate keeps running on the display. To give the display back to the stock Shelly app,
use Revert to stock in the panel before you remove the integration.

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
