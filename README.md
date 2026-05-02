# Hoval Connect for Home Assistant

[![Version](https://img.shields.io/github/v/release/chrisunderscorek/hovalconnect-ha?label=version)](https://github.com/chrisunderscorek/hovalconnect-ha/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange)](https://hacs.xyz)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](LICENSE)

Unofficial Home Assistant integration for Hoval heat pumps through the
HovalConnect cloud API.

This project is not supported by Hoval. It uses the same cloud backend as the
official HovalConnect mobile app and can break if Hoval changes the API.

## Status

The integration is built and tested for my own Hoval Belaria installation
through the HovalConnect app, with WFA-200 operating status data and the usual
heat pump, heating circuit, and hot water circuits.

Other HovalConnect-compatible heat pumps may work, but they are best-effort
until somebody tests them and reports the available circuits and values.

## What It Does

The integration creates native Home Assistant devices for the plant and its
circuits instead of putting every entity into one long flat list:

- Hoval plant
- Heat pump / heat generator
- Heating circuit
- Hot water

Entity labels can be shown in German, English, or Home Assistant's system
language. The language setting only affects this integration.

## Main Features

- Login with HovalConnect email and password.
- Optional permanent credential storage; tokens are stored either way.
- OAuth token renewal after half of the effective token lifetime.
- Retry handling for short Hoval cloud outages and HTTP `429`/`5xx` responses.
- 30 second cloud polling interval.
- Home Assistant device grouping by plant, heat pump, heating circuit, and hot
  water.
- German and English names for entities, program values, circuit status values,
  and WFA-200 operating status values.
- Active week/day program names from the API instead of raw keys like `week1`.
- Energy sensors in `kWh` for heat output and inverter energy use.
- Modulation normalized to `0%` when the heat pump is off or waiting and the
  cloud omits the value.
- Home Assistant app image for HAOS installation through an add-on repository.
- HACS/manual installation remains possible via `custom_components/hovalconnect`.

## Screenshots

Example Home Assistant device view with German labels:

| Climate controls | Heating circuit |
| --- | --- |
| ![Hoval climate controls in Home Assistant](docs/images/hoval-ha-climate.png) | ![Hoval heating circuit entities in Home Assistant](docs/images/hoval-ha-heating-circuit.png) |

| Heat pump / heat generator | Hot water |
| --- | --- |
| ![Hoval heat pump entities in Home Assistant](docs/images/hoval-ha-heat-pump.png) | ![Hoval hot water entities in Home Assistant](docs/images/hoval-ha-hot-water.png) |

## Exposed Values

Exact entities depend on what the Hoval cloud returns for your plant.

### Heat Pump / Heat Generator

- Heat generator status / `Status Wärmeerzeuger`
- WFA-200 operating status / `Betriebsstatus`
- Heat generator actual temperature / `Wärmeerzeuger-Ist`
- Heat generator target temperature / `Wärmeerzeuger Soll`
- Return temperature / `Rücklauftemp.`
- Compressor modulation / `Modulation`
- Operating hours / `Betriebsstunden`
- Operating hours over 50% / `Betriebsstunden > 50%`
- Switching cycles / `Schaltzyklen`
- Heat output energy / `Wärmeabgabe`
- Inverter energy use / `Stromverbrauch Inverter`

### Heating Circuit

- Heating circuit temperature control / `Hoval Heizkörper`
- Heating circuit program select / `Heizkreis Prog.`
- Heating circuit status / `Status Heizkreis`
- Active heating circuit program / `Akt. Heizkreisprog.`
- Flow temperature actual / `Vorlauftemp. Ist`
- Flow temperature target / `Vorlauftemp. Soll`
- Room temperature actual / `Raumtemp. Ist`
- Room temperature target / `Raumtemp. Soll`
- Outdoor temperature / `Außentemp.`

### Hot Water

- Hot water temperature control / `Hoval Warmwasser`
- Hot water program select / `Warmwasser Prog.`
- Hot water status / `Status Warmwasser`
- Active hot water program / `Akt. Warmwasserprog.`
- Hot water target temperature / `Soll-Temp.`
- Actual temperature SF1 / `Ist-Temp. SF1`
- Actual temperature SF2 / `Ist-Temp. SF2`

## Controls

The integration can write the values that are available in the HovalConnect
cloud API:

- Heating circuit target temperature
- Hot water target temperature
- Heating circuit program
- Hot water program

Heating circuit temperature changes follow the active Hoval program:

- `Constant`: set the temperature permanently.
- Weekly programs: create a temporary 4 hour override.

Hot water target temperature is set permanently.

## Installation

### HAOS App Repository

This is the preferred installation path for this repository.

1. In Home Assistant, open **Settings > Add-ons > Add-on Store**.
2. Open the three-dot menu and select **Repositories**.
3. Add this repository:

   ```text
   https://github.com/chrisunderscorek/hovalconnect-ha
   ```

4. Install **Hoval Connect**.
5. Start the app once.
6. Wait for the app log line:

   ```text
   Installed Hoval Connect integration <version>
   ```

7. Restart Home Assistant Core.
8. Add the integration from **Settings > Devices & services**.

The HAOS app is a one-shot installer. It copies the bundled custom integration
into:

```text
/config/custom_components/hovalconnect
```

Then it exits. It is not a long-running service.

### Updating Through HAOS

The Home Assistant **Update** button updates only the app image. It does not
copy the new Python integration files into `/config` and it does not restart
Home Assistant Core.

After every app update:

1. Click **Update** for the Hoval Connect app.
2. Start **Hoval Connect** once.
3. Wait for the install log line.
4. Restart Home Assistant Core.

### HACS Or Manual Installation

The integration code remains available under `custom_components/hovalconnect`.
This is useful if you previously installed the Hoval Connect integration via
HACS or if you prefer a manual custom-component installation.

For HACS:

1. HACS > Integrations > three-dot menu > Custom repositories.
2. Add this repository as category **Integration**.
3. Install **Hoval Connect**.
4. Restart Home Assistant Core.

For manual installation, copy:

```text
custom_components/hovalconnect
```

to:

```text
/config/custom_components/hovalconnect
```

Then restart Home Assistant Core.

## Configuration

1. Open **Settings > Devices & services**.
2. Add **Hoval Connect**.
3. Enter your HovalConnect email and password.
4. Choose whether Home Assistant may store email and password permanently.
5. Choose the integration language: **System**, **Deutsch**, or **English**.
6. Select your Hoval plant.

Email and password are not stored unless permanent credential storage is
enabled. OAuth token data is stored in the Home Assistant config entry.

The language can be changed later from the integration options.

## Authentication And Token Renewal

During setup, the integration exchanges your HovalConnect credentials for OAuth
tokens through SAP IAS. Hoval's core API currently expects a JWT-shaped bearer
token, so the integration prefers the JWT-shaped `id_token` when SAP IAS also
returns an opaque OAuth `access_token`.

Token handling:

- Renew after half of the effective token lifetime.
- Prefer refresh-token renewal.
- Use stored email/password only as an explicit fallback if enabled.
- If renewal fails while the current token is still valid, retry with staged
  backoff: 3x 10 seconds, 3x 30 seconds, 3x 60 seconds, then 120 seconds.
- Honor longer `Retry-After` responses from the token endpoint.
- Ask for re-authentication if the token expires and cannot be renewed.

## Hoval App Version Header

The Hoval cloud checks the frontend app version sent by the official mobile app.
This integration ships with `3.2.0` as the fallback version header.

At startup and after HTTP `426 Upgrade Required`, the integration tries to read
the current Google Play HovalConnect version and uses it if found. The check is
limited to one 6 hour slot from integration startup, so installations do not all
probe Hoval/Google at the same wall-clock time.

## API Notes

The integration uses these Hoval cloud areas:

- `GET /api/my-plants`
- `GET /v1/plants/{id}/settings`
- `GET /v3/plants/{id}/circuits`
- `GET /v3/api/statistics/live-values/{id}`
- `GET /v2/business/plants/{id}/circuits/{path}`
- `POST /v3/plants/{id}/circuits/{path}/temporary-change`
- `PATCH /v3/plants/{id}/circuits/{path}/programs`
- `POST /v3/plants/{id}/circuits/{path}/programs/{program}`

`docs/api-docs.json` contains an unofficial OpenAPI snapshot captured from:

```text
GET https://azure-iot-prod.hoval.com/core/v3/api-docs
```

The snapshot is useful for development, but it is not an official contract from
Hoval.

## Debug Tools

The `tools/` directory contains local helper scripts for development and HAOS
checks. The most useful ones are:

- `tools/debug_hoval_auth.py`: token and API probing.
- `tools/check_ha_app_on_haos.sh`: check app and installed integration versions
  on HAOS.
- `tools/update_ha_app_on_haos.sh`: update/start the one-shot app on HAOS.
- `tools/analyze_ha_history_availability.py`: inspect a locally copied Home
  Assistant recorder database for `unavailable` phases.

Do not commit tokens, Home Assistant recorder databases, or private API output.

## Known Limits

- Only my Belaria setup is actively supported and tested.
- Other HovalConnect plants may expose different circuit names or values.
- The HovalConnect cloud API is unofficial and may change without notice.
- Two-factor authentication is not supported.
- This project does not provide a local OPC UA server.
- No Lovelace dashboard is included.

## License

GPL-3.0-only. See [LICENSE](LICENSE).

Versions up to and including `v0.2.2` were published under the MIT License.
Starting with `v1.0.0`, this project is distributed under GPL-3.0-only.
