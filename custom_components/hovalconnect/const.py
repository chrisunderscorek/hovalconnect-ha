"""Constants for Hoval Connect."""
DOMAIN = "hovalconnect"
MANUFACTURER = "Hoval"

API_BASE  = "https://azure-iot-prod.hoval.com/core"
AUTH_BASE = "https://akwc5scsc.accounts.ondemand.com"
AUTH_TOKEN_URL = f"{AUTH_BASE}/oauth2/token"
CLIENT_ID = "991b54b2-7e67-47ef-81fe-572e21c59899"

API_MY_PLANTS      = f"{API_BASE}/api/my-plants?page=0&size=12"
API_PLANT_SETTINGS = f"{API_BASE}/v1/plants/{{plant_id}}/settings"
API_CIRCUITS       = f"{API_BASE}/v3/plants/{{plant_id}}/circuits?ignoreConnectionState=false"
API_TEMP_CHANGE    = f"{API_BASE}/v3/plants/{{plant_id}}/circuits/{{path}}/temporary-change"
API_SET_PROGRAM    = f"{API_BASE}/v3/plants/{{plant_id}}/circuits/{{path}}/programs/{{program}}"

CONF_PLANT_ID = "plant_id"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_STORE_PASSWORD = "store_password"
CONF_TOKEN_ISSUED_AT = "token_issued_at"
CONF_TOKEN_EXPIRES_AT = "token_expires_at"
CONF_TOKEN_RENEW_AFTER = "token_renew_after"
UPDATE_INTERVAL_SECONDS = 30
TEMP_DURATION_DEFAULT = "fourHours"

API_LIVE_VALUES = f"{API_BASE}/v3/api/statistics/live-values/{{plant_id}}"
