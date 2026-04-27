#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

SOURCE_DIR="/app/custom_components/hovalconnect"
TARGET_ROOT="/config/custom_components"
TARGET_DIR="${TARGET_ROOT}/hovalconnect"
TEMP_DIR=""
BACKUP_EXISTING="true"

cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}
trap cleanup EXIT

if [[ ! -d "${SOURCE_DIR}" ]]; then
    bashio::log.fatal "Bundled Hoval Connect integration is missing from the image."
fi

if [[ ! -d "/config" ]]; then
    bashio::log.fatal "Home Assistant config directory is not mounted at /config."
fi

if [[ -f "/data/options.json" ]] \
    && grep -Eq '"backup_existing"[[:space:]]*:[[:space:]]*false' "/data/options.json"; then
    BACKUP_EXISTING="false"
fi

mkdir -p "${TARGET_ROOT}"

if [[ -d "${TARGET_DIR}" && "${BACKUP_EXISTING}" == "true" ]]; then
    backup_dir="${TARGET_DIR}.backup-$(date -u +%Y%m%d%H%M%S)"
    bashio::log.info "Backing up existing integration to ${backup_dir}"
    cp -a "${TARGET_DIR}" "${backup_dir}"
fi

TEMP_DIR="$(mktemp -d "${TARGET_ROOT}/.hovalconnect.XXXXXX")"
cp -a "${SOURCE_DIR}/." "${TEMP_DIR}/"

find "${TEMP_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

rm -rf "${TARGET_DIR}"
mv "${TEMP_DIR}" "${TARGET_DIR}"
TEMP_DIR=""

version="$(sed -n 's/.*"version":[[:space:]]*"\([^"]*\)".*/\1/p' "${TARGET_DIR}/manifest.json" | head -n 1)"

bashio::log.info "Installed Hoval Connect integration ${version:-unknown} to ${TARGET_DIR}"
bashio::log.warning "Restart Home Assistant Core to load or update the integration."
