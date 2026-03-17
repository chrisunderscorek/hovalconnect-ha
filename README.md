# Hoval Connect – Home Assistant Integration

[![Version](https://img.shields.io/badge/version-0.0.1-blue)](https://github.com/yourusername/hovalconnect-ha/releases)
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
| `select.hoval_heating_circuit_program` | Select | Weekly program 1/2 / Constant / Eco mode |
| `sensor.hoval_flow_temperature` | Sensor | Flow temperature actual |
| `sensor.hoval_outside_temperature` | Sensor | Outside temperature |
| `sensor.hoval_modulation` | Sensor | Compressor modulation (%) |
| `sensor.hoval_operating_hours` | Sensor | Total operating hours |
| `sensor.hoval_operation_cycles` | Sensor | Total switching cycles |
| `sensor.hoval_storage_temperature` | Sensor | Hot water storage temperature |
| `sensor.hoval_*_status` | Sensor | Operating status (heating/charging/off) |
| `sensor.hoval_*_active_program` | Sensor | Active program |

### Control Logic

**Heating circuit:**
- Program = `Constant` → temperature set **permanently**
- Program = `Weekly 1/2` → temperature valid for **4 hours** (temporary override)

**Hot water:**
- Temperature is always set **permanently**

---

## Installation

### Step 1 – Get Tokens (once)

1. [Download Setup Tool](setup_tool/) → extract ZIP
2. Double-click `install.bat` (downloads Chromium ~150MB, one-time only)
3. Double-click `start.bat`
4. Enter your Hoval email and password → click **Get Tokens**
5. Access Token and Refresh Token are displayed with copy buttons

### Step 2 – Install Integration

**Manual:**
1. Copy folder `custom_components/hovalconnect/` to `config/custom_components/hovalconnect/`
2. Restart Home Assistant

**Via HACS (Custom Repository):**
1. HACS → Integrations → ⋮ → Custom Repositories
2. URL: `https://github.com/yourusername/hovalconnect-ha`
3. Category: Integration → Add
4. Install integration → Restart HA

### Step 3 – Configure

1. Settings → Integrations → **+ Add Integration**
2. Search for "Hoval Connect"
3. Paste Access Token and Refresh Token from Setup Tool
4. Select your plant → Done ✅

---

## Token Management

Tokens are **renewed automatically** – one-time setup is sufficient for permanent operation.

| Token | Validity | Renewal |
|-------|----------|---------|
| Access Token | 30 minutes | Automatic by HA |
| Refresh Token | Weeks/months | Automatic, saved in HA config |

If the integration goes offline after a long HA downtime: run the Setup Tool again and enter new tokens.

---

## Security

- Credentials are **never stored** (neither locally nor in the cloud)
- Transmission exclusively via **HTTPS** to SAP IAS (Hoval Identity Provider)
- Browser (Chromium) runs **headless** (invisible) and is closed immediately after login
- Tokens are deleted from RAM after handover

---

## Technical Details

This integration uses the unofficial HovalConnect Cloud API, reverse-engineered from the official iOS/Android app.

| Endpoint | Usage |
|----------|-------|
| `GET /api/my-plants` | Fetch plants |
| `GET /v1/plants/{id}/settings` | Get plant access token |
| `GET /v3/plants/{id}/circuits` | Heating circuit data |
| `GET /v3/api/statistics/live-values/{id}` | Live sensor values |
| `POST /v3/plants/{id}/circuits/{path}/temporary-change` | Temporary temperature |
| `PATCH /v3/plants/{id}/circuits/{path}/programs` | Permanent temperature |
| `POST /v3/plants/{id}/circuits/{path}/programs/{program}` | Switch program |

**Auth:** OAuth2 PKCE via SAP IAS  
**Update interval:** 30 seconds

---

## Known Limitations

- No official API access → API may change without notice
- Setup Tool requires Windows (Linux/Mac planned)
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
