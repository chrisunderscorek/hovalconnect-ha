#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  tools/update_ha_app_on_haos.sh HOST [options]

Reload the Home Assistant store, find the Hoval Connect app slug, update/start
the app on HAOS over SSH, and print the final check JSON.

Required:
  HOST                    Home Assistant host or user@host for SSH

Options:
  --user USER             SSH user when HOST has no user part (default: root)
  --slug SLUG             App slug; auto-detected when omitted
  --repo URL              App repository URL passed to check_ha_app_on_haos.sh
  --app-name NAME         App name passed to check_ha_app_on_haos.sh
  --app-version VERSION   Expected app version passed to check_ha_app_on_haos.sh
  --domain DOMAIN         Custom integration domain/path (default: hovalconnect)
  --no-reload             Do not run "ha store reload" before detection
  --skip-update           Do not run the app update command
  --skip-start            Do not run the app start command
  --restart-core          Restart Home Assistant Core after app update/start
  --core-timeout SECONDS  Wait time for Core to answer after restart (default: 180)
  --help                  Show this help
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

host=""
ssh_user="root"
slug=""
repo=""
app_name=""
app_version=""
domain="hovalconnect"
reload_store="true"
skip_update="false"
skip_start="false"
restart_core="false"
core_timeout="180"

if [[ $# -gt 0 && "$1" != --* ]]; then
    host="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            ssh_user="${2:-}"
            shift 2
            ;;
        --slug)
            slug="${2:-}"
            shift 2
            ;;
        --repo)
            repo="${2:-}"
            shift 2
            ;;
        --app-name)
            app_name="${2:-}"
            shift 2
            ;;
        --app-version)
            app_version="${2:-}"
            shift 2
            ;;
        --domain)
            domain="${2:-}"
            shift 2
            ;;
        --no-reload)
            reload_store="false"
            shift
            ;;
        --skip-update)
            skip_update="true"
            shift
            ;;
        --skip-start)
            skip_start="true"
            shift
            ;;
        --restart-core)
            restart_core="true"
            shift
            ;;
        --core-timeout)
            core_timeout="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "${host}" ]]; then
    echo "Missing required HOST argument" >&2
    usage >&2
    exit 2
fi

if [[ "${host}" == *@* ]]; then
    ssh_target="${host}"
else
    ssh_target="${ssh_user}@${host}"
fi

tmp_dir="$(mktemp -d)"
cleanup() {
    rm -rf "${tmp_dir}"
}
trap cleanup EXIT

check_args=("${host}" --user "${ssh_user}" --domain "${domain}")
if [[ -n "${repo}" ]]; then
    check_args+=(--repo "${repo}")
fi
if [[ -n "${app_name}" ]]; then
    check_args+=(--app-name "${app_name}")
fi
if [[ -n "${app_version}" ]]; then
    check_args+=(--app-version "${app_version}")
fi
if [[ "${reload_store}" == "true" ]]; then
    check_args+=(--reload)
fi

"${script_dir}/check_ha_app_on_haos.sh" "${check_args[@]}" > "${tmp_dir}/before.json"

if [[ -z "${slug}" ]]; then
    slug="$(python3 - "${tmp_dir}/before.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
slug = (
    data.get("store_app", {}).get("slug")
    or data.get("installed_app", {}).get("data", {}).get("slug")
    or ""
)
print(slug)
PY
)"
fi

if [[ -z "${slug}" ]]; then
    echo "Could not detect app slug. Check output follows:" >&2
    cat "${tmp_dir}/before.json" >&2
    exit 1
fi

if [[ ! "${slug}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Refusing unsafe slug: ${slug}" >&2
    exit 2
fi

ssh_cmd=(ssh -o BatchMode=yes -o ConnectTimeout=8 "${ssh_target}")

ha_app_command() {
    local action="$1"
    local fallback_action="$2"
    echo "Running: ha apps ${action} ${slug}" >&2
    if ! "${ssh_cmd[@]}" "ha apps ${action} '${slug}' --raw-json" >&2; then
        echo "Falling back to deprecated ha addons ${fallback_action} ${slug}" >&2
        "${ssh_cmd[@]}" "ha addons ${fallback_action} '${slug}' --raw-json" >&2
    fi
}

if [[ "${skip_update}" != "true" ]]; then
    ha_app_command update update
fi

if [[ "${skip_start}" != "true" ]]; then
    ha_app_command start start
fi

if [[ "${restart_core}" == "true" ]]; then
    echo "Restarting Home Assistant Core." >&2
    "${ssh_cmd[@]}" "ha core restart --raw-json" >&2 || true

    deadline=$((SECONDS + core_timeout))
    while (( SECONDS < deadline )); do
        if "${ssh_cmd[@]}" "ha core info --raw-json" >/dev/null 2>&1; then
            break
        fi
        sleep 5
    done
fi

final_check_args=("${host}" --user "${ssh_user}" --domain "${domain}")
if [[ -n "${repo}" ]]; then
    final_check_args+=(--repo "${repo}")
fi
if [[ -n "${app_name}" ]]; then
    final_check_args+=(--app-name "${app_name}")
fi
if [[ -n "${app_version}" ]]; then
    final_check_args+=(--app-version "${app_version}")
fi
"${script_dir}/check_ha_app_on_haos.sh" "${final_check_args[@]}"
