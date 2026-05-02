# Changelog

## [1.0.0] – 2026-05-02

### Release

- Mark the integration as the first stable release for the actively tested Hoval Belaria setup.
- Rework the README to describe the real HAOS app flow, tested scope, current entity set, and known limits.
- Change the project license from MIT to GPL-3.0-only. Versions up to and including `v0.2.2` remain available under MIT.

## [0.2.2] – 2026-05-02

### Devices

- Group Home Assistant entities into native Hoval plant, heat pump, heating circuit, and hot water devices.
- Keep existing entity unique IDs stable while migrating old single-device entities to the new circuit devices.
- Store the selected Hoval plant name during setup and use localized circuit fallback names.

### Tooling

- Make HAOS app checks fail when the copied custom-component version still lags behind the installed app version.
- Document the required manual HAOS update flow: update app image, start the one-shot app once, then restart Home Assistant Core.

## [0.2.0] – 2026-05-01

### Reliability

- Improve resilience against short Hoval cloud outages and avoid token-refresh reloads that briefly made entities unavailable.
- Normalize missing modulation to `0%` when the heat pump is off or waiting; see `feature_docs/HA-0001-reliable-cloud-fetches.md`.
- Add a local recorder-history availability analysis tool.

## [0.0.9] – 2026-05-01

### Energy

- Add heat output and inverter energy sensors in `kWh` from the BL live-values `heatAmount` and `totalEnergy`.
- Convert the cloud energy values from inferred `MWh` to Home Assistant `kWh` and expose the raw value/unit as attributes.

### Status

- Map WFA-200 numeric operating status codes, including `0` to `WP aus` / `Heat pump off`.
- Use the read-only business circuit detail datapoint `*.2053` as fallback when `faStatus` is missing from live values.

## [0.0.8] – 2026-04-30

### Localization

- Use context-specific names for heating circuit, hot water, and heat generator status sensors.
- Localize circuit status values such as `heating` and `off` for German/English integration languages.
- Show the active week/day prog. names instead of raw API keys such as `week1` and `week2`.
- Rename the former error-code live sensor to operating status while leaving value mapping for a later release.
- Avoid duplicate target/actual temperature sensors when the same HK/WW values are already exposed from live values.

### Tooling

- Add helper scripts for local GHCR pretest image builds, config-only pretest pushes, and HAOS app update checks.
- Add German and English tools documentation with path-neutral examples.

## [0.0.7] – 2026-04-30

### Localization

- Add an integration language option with `System`, `Deutsch`, and `English`.
- Keep the language scoped to Hoval Connect entity names and program labels instead of changing the global Home Assistant language.
- Align German and English sensor names with the official HovalConnect app screenshots.
- Add live sensors for heat generator status, return temperature, and hot water `SF2`.
- Use the API heat generator name for Home Assistant device metadata instead of a hard-coded model.

## [0.0.6] – 2026-04-27

### Presentation

- Add local Home Assistant brand images under `custom_components/hovalconnect/brand/` so the integration can show its icon and logo in Home Assistant 2026.3+.

## [0.0.5] – 2026-04-27

### Authentication

- Retry failed token renewals with staged backoff: 3x 10 seconds, 3x 30 seconds, 3x 60 seconds, then 120 seconds.
- Honor token endpoint `Retry-After` responses when they request a longer wait.
- Clarify token renewal timing in the README and Home Assistant app documentation.

## [0.0.4] – 2026-04-27

### Authentication

- Prefer the JWT-shaped `id_token` as Hoval API bearer token when SAP IAS returns an opaque OAuth `access_token`.
- Update the simulated Hoval frontend app version header to `3.2.0`.
- Check the current Google Play HovalConnect app version during integration startup and after HTTP 426 responses, throttled to 6-hour slots from integration start.
- Print an explicit `api_bearer_token` in the debug auth tool and use it for `--sample-curl` / `--test-api-docs`.
- Fetch Google Play and Apple App Store versions in the debug auth tool and use the newest store version for sample API calls.
- Add `--bump-app-version` to skip store probing with a fixed version and `--only-tokens` to suppress store/diagnostic output.
- Add `docs/api-docs.json`, an OpenAPI snapshot captured with HovalConnect frontend app version `3.2.0`.
- Update the README with token handling, frontend app version handling, the debug tool, and the API snapshot.

## [0.0.3] – 2026-04-27

### Authentication

- Add HovalConnect email/password setup flow.
- Store OAuth token data and renewal timing after setup.
- Do not store email or password unless permanent credential storage is enabled.
- Prefer refresh-token renewal and use stored credentials only as an explicit fallback.
- Renew after half of the effective token lifetime and retry failed renewal every 60 seconds while the current token is still valid.
- Trigger re-authentication when the token expires and cannot be renewed.

## [0.0.1] – 2026-03-17

### Initial Release

**Sensors:**
- Heating circuit: Flow temp actual/target, room temp actual/target, outside temperature, status, program
- Heat generator: Flow temp actual/target, modulation, operating hours, switching cycles, error code
- Hot water: Storage temperature, target temperature, status, program

**Controls:**
- Initial control entities for heating circuit temperature, hot water temperature, and program switching. Write behavior still needs practical validation.

**Authentication:**
- OAuth2 PKCE via SAP IAS
- Automatic token refresh (proactive every 10 minutes)
- Token persistence across HA restarts
- Reauth flow when tokens expire
- Setup Tool (Windows) for easy token creation
