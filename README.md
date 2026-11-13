# WiiM Local for Home Assistant

A custom Home Assistant integration for WiiM streamers, built around the [official WiiM HTTP API v1.2](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf). Primary target: **WiiM Mini**. Domain: `wiim_local`.

## Features

- UI setup with local IP address or hostname; stable device identity prevents duplicates.
- Play, pause, stop, next/previous, volume, mute, seek, and HTTP(S) audio URL playback.
- Home Assistant media-source URL resolution, including compatible TTS URLs.
- Playback state, artist, album, artwork, duration and position, when supplied by firmware.
- Wi-Fi, Aux In and Bluetooth input selection. Optical input is offered for reported Pro, Ultra and Amp projects, never the Mini.
- Twelve preset shortcut buttons matching presets configured in WiiM Home. Buttons are disabled by default: enable only the preset slots you use in the entity registry.
- Five-second local polling, unavailable state on connection loss, and automatic recovery.

## Install

Requires Home Assistant **2025.3 or later**. Minimum-version validation uses 2025.3.4. Later Home Assistant releases still need validation.

1. Clone or download this private repository using your GitHub account.
2. Copy `custom_components/wiim_local` into `/config/custom_components/wiim_local` on your Home Assistant host. The resulting manifest path must be `/config/custom_components/wiim_local/manifest.json`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → WiiM Local**.
5. Enter the Mini's local IP address, shown in WiiM Home device settings. A DHCP reservation is recommended.
6. HTTPS verification defaults to enabled. If setup fails because your WiiM has a self-signed certificate, disable **Verify HTTPS certificate** for this device only, on a trusted LAN. This encrypts traffic but does not authenticate the device certificate.

Home Assistant must reach the device on TCP 443. No cloud account, API key, or inbound Internet access is required. To update, replace the integration directory and restart. To change the address or certificate setting, add the integration again with the same device: setup updates the existing entry rather than duplicating it.

The repository contains HACS metadata for future distribution, but **manual installation is the supported path while this repository is private**. Do not put a GitHub access token in Home Assistant configuration or in the repository.

## Use

The device appears as a media player. Preset buttons can be enabled under the device's entities. Configure preset contents in WiiM Home first; unassigned slots may do nothing or return a device error.

Example Home Assistant action:

```yaml
action: media_player.play_media
target:
  entity_id: media_player.your_wiim
data:
  media_content_type: music
  media_content_id: https://example.com/audio.mp3
```

Use your actual entity ID and a directly playable audio URL. Streaming-service page URLs (Spotify, Apple Music, etc.) are not audio streams. Use WiiM Home presets for those services.

## Compatibility and limits

WiiM documents these as product-family commands and uses a Mini in its examples. Shared playback commands should work across compatible WiiM firmware, with read-only device information, idle playback status, and preset retrieval verified on a physical Mini running firmware `Linkplay.4.6.833047`. Active playback controls and other models remain unverified. Model/firmware-specific functionality is not guaranteed. Only the documented common input names are exposed; HDMI, phono and other newer inputs need explicit API support before addition.

Playback commands, track skipping, seeking and metadata availability depend on the current source. External sources such as AirPlay, Bluetooth and line input may ignore some controls or omit metadata. Metadata failure alone does not make the player unavailable. Missing metadata is cleared rather than retained from a previous track.

This initial version does not implement automatic discovery, multiroom grouping, EQ, alarms, firmware updates, audio output switching, queueing, shuffle/repeat, or power control. There is no generic arbitrary-command action. Do not add the same device to another media integration unless duplicate controls are desired. This project uses its own domain and does not overwrite built-in integrations.

## Development

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/ruff check .
```

Tests simulate WiiM HTTPS responses; they do not connect to or change a real speaker. See `tests/` for error handling, query encoding, input validation, config flow and entity checks. The GitHub Actions workflow runs the same checks.

Remove through Settings → Devices & services, then delete the custom integration directory and restart if no longer needed.
