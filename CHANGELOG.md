# Changelog

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
- Heating circuit temperature (temporary 4h when weekly program active, permanent when constant mode)
- Hot water temperature (always permanent)
- Program switching: Weekly program 1/2, Constant, Eco mode

**Authentication:**
- OAuth2 PKCE via SAP IAS
- Automatic token refresh (proactive every 10 minutes)
- Token persistence across HA restarts
- Reauth flow when tokens expire
- Setup Tool (Windows) for easy token creation
