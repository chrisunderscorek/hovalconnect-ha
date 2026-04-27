# Hoval Connect App

This app installs the bundled Hoval Connect custom integration into the Home Assistant configuration directory. It is an alternative to HACS or manual copying; the integration code remains available under `custom_components/hovalconnect` for HACS users.

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `backup_existing` | `true` | Copies any existing `/config/custom_components/hovalconnect` directory to a timestamped backup before installing this version. |

## Usage

1. Add this app repository to Home Assistant:

   ```text
   https://github.com/chrisunderscorek/hovalconnect-ha
   ```

2. Install **Hoval Connect**.
3. Start the app once.
4. Restart Home Assistant Core.
5. Add **Hoval Connect** from **Settings > Devices & services**.

The app exits after copying the integration files. Start it again whenever you want to update the installed integration from the app image.

## Network and Security

The app ships with a custom AppArmor profile. It grants write access only to the Home Assistant custom integration path and allows outbound TCP/DNS networking. The installed integration itself runs inside Home Assistant Core and uses HTTPS to reach the Hoval cloud API.
