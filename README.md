# Hoval Connect – Home Assistant Integration

[![Version](https://img.shields.io/badge/version-0.0.9-blue)](https://github.com/chrisunderscorek/hovalconnect-ha/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange)](https://hacs.xyz)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Unofficial Home Assistant integration for Hoval heat pumps via the HovalConnect Cloud API.

> ⚠️ **Unofficial integration** – not supported by Hoval. Use at your own risk.

---

## Supported Devices

All devices compatible with the **HovalConnect App** (iOS/Android), e.g.:
- Belaria Compact IR
- Other Hoval heat pumps (untested – feedback welcome)

---

## Features

| Entity | Type | Description |
|--------|------|-------------|
| `climate.hoval_heating_circuit` | Climate | Read & set room temperature |
| `climate.hoval_hot_water` | Climate | Read & set hot water temperature |
| `select.hoval_heating_circuit_program` | Select | Weekly prog. 1/2 / Constant / Eco mode |
| `sensor.hoval_flow_temperature` | Sensor | Flow temp. actual |
| `sensor.hoval_return_temperature` | Sensor | Return temp. |
| `sensor.hoval_outside_temperature` | Sensor | Outdoor temp. |
| `sensor.hoval_modulation` | Sensor | Compressor modulation (%) |
| `sensor.hoval_operating_hours` | Sensor | Total operating hours |
| `sensor.hoval_operation_cycles` | Sensor | Total switching cycles |
| `sensor.hoval_heat_output_energy` | Sensor | Heat output energy in kWh |
| `sensor.hoval_inverter_energy_use` | Sensor | Inverter energy consumption in kWh |
| `sensor.hoval_actual_temperature_sf1` | Sensor | Hot water actual temp. SF1 |
| `sensor.hoval_actual_temperature_sf2` | Sensor | Hot water actual temp. SF2 |
| `sensor.hoval_*_status` | Sensor | Circuit and WFA-200 operating status |
| `sensor.hoval_*_active_program` | Sensor | Active week/day prog. names |

### Control Logic

**Heating circuit:**
- Program = `Constant` → temperature set **permanently**
- Program = `Weekly 1/2` → temperature valid for **4 hours** (temporary override)

**Hot water:**
- Temperature is always set **permanently**

---

## Installation

### Step 1 – Install Integration

**Manual:**
1. Copy folder `custom_components/hovalconnect/` to `config/custom_components/hovalconnect/`
2. Restart Home Assistant

**Via Home Assistant App Repository:**
1. Settings → Add-ons → Add-on Store → ⋮ → Repositories
2. URL: `https://github.com/chrisunderscorek/hovalconnect-ha`
3. Install **Hoval Connect**
4. Start the app once → Restart Home Assistant Core

The Home Assistant app copies the bundled integration into
`/config/custom_components/hovalconnect` and then exits. Start it again whenever
you want to refresh the installed integration from the app image.

**Via HACS (Custom Repository):**
1. HACS → Integrations → ⋮ → Custom Repositories
2. URL: `https://github.com/chrisunderscorek/hovalconnect-ha`
3. Category: Integration → Add
4. Install integration → Restart HA

### Step 2 – Configure

1. Settings → Integrations → **+ Add Integration**
2. Search for "Hoval Connect"
3. Enter your HovalConnect email and password
4. Optional: enable **Store email and password permanently** if Home Assistant should be allowed to renew tokens with your credentials after token-based renewal fails
5. Select the integration language: **System**, **Deutsch**, or **English**
6. Select your plant → Done

The language option controls the Hoval Connect entity names and program labels
inside this integration only. It does not change the global Home Assistant
language. Change it later from **Settings → Devices & services → Hoval Connect
→ Configure**.

German and English entity names follow the official HovalConnect app wording
where known, for example `Wärmeerzeuger-Ist`, `Vorlauftemp. Ist`,
`Ist-Temp. SF1`, `Ist-Temp. SF2`, `Heat generator actual`, and
`Flow temp. actual`.

---

## Token Management

During setup Home Assistant exchanges your HovalConnect email and password for OAuth tokens and stores the token data in the config entry. Email and password are not stored unless **Store email and password permanently** is enabled.

| Token | Validity | Renewal |
|-------|----------|---------|
| Access Token | `expires_in` from Hoval/SAP IAS, minus 60 seconds safety margin | First renewal attempt after half of its effective lifetime when a refresh token or stored credentials are available |
| Refresh Token | Optional, if returned by Hoval/SAP IAS | Preferred renewal mechanism |
| Stored Email/Password | Optional | Used only as explicit fallback when token-based renewal is unavailable or rejected |

If token renewal fails while the current access token is still valid, the integration keeps using the current token and retries renewal with a staged backoff: 3 attempts after 10 seconds, 3 attempts after 30 seconds, 3 attempts after 60 seconds, then every 120 seconds. If the token endpoint sends `Retry-After`, the integration waits at least that long. If no refresh token is available and credentials were not stored, Home Assistant will ask you to re-authenticate when the saved token expires.

The SAP IAS `access_token` can be opaque. Hoval's core API currently expects a
JWT-shaped bearer token and otherwise rejects requests as malformed, so the
integration prefers the JWT-shaped `id_token` when one is returned.

---

## Security

- Email and password are only stored when **Store email and password permanently** is enabled
- Transmission exclusively via **HTTPS** to SAP IAS (Hoval Identity Provider)
- Access and refresh tokens are saved in the Home Assistant config entry and must be treated as bearer secrets

---

## Technical Details

This integration uses the unofficial HovalConnect Cloud API, reverse-engineered from the official iOS/Android app.

| Endpoint | Usage |
|----------|-------|
| `GET /api/my-plants` | Fetch plants |
| `GET /v1/plants/{id}/settings` | Get plant access token |
| `GET /v3/plants/{id}/circuits` | Heating circuit data |
| `GET /v3/api/statistics/live-values/{id}` | Live sensor values |
| `GET /v2/business/plants/{id}/circuits/{path}` | WFA operating status fallback |
| `POST /v3/plants/{id}/circuits/{path}/temporary-change` | Temporary temperature |
| `PATCH /v3/plants/{id}/circuits/{path}/programs` | Permanent temperature |
| `POST /v3/plants/{id}/circuits/{path}/programs/{program}` | Switch program |

Energy counters exposed by Hoval as `heatAmount` and `totalEnergy` are converted
from the cloud values that behave like MWh to Home Assistant `kWh` energy
sensors. The WFA-200 documentation names the corresponding counters as kWh
parameters, including `01-048 Energiemenge total` and `01-027 Aufgenommene el.
Energie`.

- **Auth:** OAuth2 via SAP IAS, JWT bearer for the Hoval core API
- **Update interval:** 30 seconds

### Frontend App Version

The Hoval core API also checks the frontend app version sent by the official
mobile app. This integration uses `3.2.0` as the bundled fallback version.

At startup the integration checks Google Play for the current HovalConnect app
version and logs the default, the detected store version, and the effective
version header. If Hoval returns HTTP 426 `Upgrade Required`, the integration
checks the store version again and retries the failed request once if the
effective version changed. These rechecks are limited to one 6-hour slot
calculated from the integration startup time, so installations do not all check
at the same wall-clock time.

### API Reference Snapshot

`docs/api-docs.json` contains a reference OpenAPI snapshot from:

```text
GET https://azure-iot-prod.hoval.com/core/v3/api-docs
```

The snapshot was captured with HovalConnect frontend app version `3.2.0`. It is
OpenAPI `3.1.0`, contains 152 paths, and should be treated as an unofficial
reference, not as a stable contract from Hoval.

### Debug Tool

`tools/debug_hoval_auth.py` can exchange HovalConnect credentials for token data,
inspect existing tokens, print sample API calls, and probe the current mobile app
versions.

```bash
tools/debug_hoval_auth.py --store-versions
tools/debug_hoval_auth.py --sample-curl
tools/debug_hoval_auth.py --username user@example.com --sample-curl --test-api-docs
tools/debug_hoval_auth.py --bump-app-version 3.2.0 --sample-curl
```

Use `--only-tokens` when piping token output into another command. Use
`--bump-app-version VERSION` to skip Google Play / Apple App Store probing and
force a specific frontend app version header.

---

## Known Limitations

- No official API access → API may change without notice
- Two-factor authentication is not supported

---

## Contributing

Pull requests and issues welcome! Especially needed:
- Tests with other Hoval models
- macOS/Linux Setup Script
- HACS validation

---

## License

MIT License – see [LICENSE](LICENSE)

---

## Acknowledgements

Reverse engineering methodology inspired by similar projects such as [homeassistant-myskoda](https://github.com/skodaconnect/homeassistant-myskoda).
