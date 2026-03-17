# Changelog

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
