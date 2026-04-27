#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  tools/check_ha_app_on_haos.sh HOST [options]

Required:
  HOST                    Home Assistant host or user@host for SSH

Options:
  --user USER             SSH user when HOST has no user part (default: root)
  --repo URL              App repository URL
                           (default: https://github.com/chrisunderscorek/hovalconnect-ha)
  --app-name NAME         App name to find in the store
                          (default: read from hovalconnect/config.yaml)
  --app-version VERSION   Expected latest app version
                          (default: read from hovalconnect/config.yaml)
  --domain DOMAIN         Custom integration domain/path to inspect (default: hovalconnect)
  --reload                Run "ha store reload" before collecting data
  --help                  Show this help

The script prints a single JSON object to stdout.
USAGE
}

host=""
ssh_user="root"
repo="https://github.com/chrisunderscorek/hovalconnect-ha"
app_name=""
app_version=""
domain="hovalconnect"
reload_store="false"

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
        --reload)
            reload_store="true"
            shift
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

if [[ ! "${domain}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Invalid --domain value: ${domain}" >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
app_config="${repo_root}/hovalconnect/config.yaml"

read_config_value() {
    local key="$1"
    local value=""
    if [[ -f "${app_config}" ]]; then
        value="$(awk -v key="${key}" '$1 == key ":" { sub("^[^:]+:[[:space:]]*", ""); print; exit }' "${app_config}")"
    fi
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s\n' "${value}"
}

if [[ -z "${app_name}" ]]; then
    app_name="$(read_config_value name)"
fi

if [[ -z "${app_version}" ]]; then
    app_version="$(read_config_value version)"
fi

if [[ -z "${app_name}" || -z "${app_version}" ]]; then
    echo "Could not determine app name/version; pass --app-name and --app-version explicitly." >&2
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

ssh_cmd=(ssh -o BatchMode=yes -o ConnectTimeout=8 "${ssh_target}")

if [[ "${reload_store}" == "true" ]]; then
    "${ssh_cmd[@]}" "ha store reload >/dev/null" >&2
fi

"${ssh_cmd[@]}" "ha info --raw-json" > "${tmp_dir}/ha_info.json"
"${ssh_cmd[@]}" "ha store --raw-json" > "${tmp_dir}/store.json"
"${ssh_cmd[@]}" "ha apps --raw-json" > "${tmp_dir}/apps.json"
"${ssh_cmd[@]}" "if [ -f '/config/custom_components/${domain}/manifest.json' ]; then cat '/config/custom_components/${domain}/manifest.json'; else printf '{}'; fi" > "${tmp_dir}/component_manifest.json"

CHECK_HOST="${host}" \
CHECK_TARGET="${ssh_target}" \
CHECK_REPO="${repo}" \
CHECK_APP_NAME="${app_name}" \
CHECK_APP_VERSION="${app_version}" \
CHECK_DOMAIN="${domain}" \
CHECK_RELOAD="${reload_store}" \
python3 - "${tmp_dir}" <<'PY'
import json
import os
import sys
from pathlib import Path


def load_json(path: Path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        return {
            "_parse_error": str(err),
            "_raw_tail": raw[-1000:],
        }


def data(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def normalize_url(value):
    value = (value or "").strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("addons", "apps"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


tmp = Path(sys.argv[1])
expected_repo = os.environ["CHECK_REPO"]
expected_repo_norm = normalize_url(expected_repo)
expected_app_name = os.environ["CHECK_APP_NAME"]
expected_version = os.environ["CHECK_APP_VERSION"]
domain = os.environ["CHECK_DOMAIN"]

ha_info_payload = load_json(tmp / "ha_info.json")
store_payload = load_json(tmp / "store.json")
apps_payload = load_json(tmp / "apps.json")
component_manifest = load_json(tmp / "component_manifest.json")

ha_info = data(ha_info_payload)
store = data(store_payload)
apps = data(apps_payload)

repositories = store.get("repositories", []) if isinstance(store, dict) else []
store_apps = store.get("addons", []) if isinstance(store, dict) else []
installed_apps = as_list(apps)

repo_match = None
for repo in repositories:
    if normalize_url(repo.get("source")) == expected_repo_norm:
        repo_match = repo
        break

repo_slug = repo_match.get("slug") if repo_match else None


def app_score(app):
    score = 0
    if app.get("name") == expected_app_name:
        score += 4
    if repo_slug and app.get("repository") == repo_slug:
        score += 3
    if expected_repo_norm and normalize_url(app.get("url", "")).startswith(expected_repo_norm):
        score += 2
    if domain and domain in str(app.get("slug", "")):
        score += 1
    return score


app_candidates = [app for app in store_apps if app_score(app) > 0]
store_app = max(app_candidates, key=app_score) if app_candidates else None

installed_candidates = [app for app in installed_apps if app_score(app) > 0]
installed_app = max(installed_candidates, key=app_score) if installed_candidates else None

ha_arch = ha_info.get("arch") if isinstance(ha_info, dict) else None
supported_arch = store_app.get("arch", []) if isinstance(store_app, dict) else []
version_latest = store_app.get("version_latest") if isinstance(store_app, dict) else None

checks = {
    "ssh_ok": not any("_parse_error" in p for p in (ha_info_payload, store_payload, apps_payload)),
    "repository_present": repo_match is not None,
    "store_app_visible": store_app is not None,
    "version_matches": store_app is not None and version_latest == expected_version,
    "host_arch_supported": store_app is not None and ha_arch in supported_arch,
}

component = {
    "path": f"/config/custom_components/{domain}",
    "installed": isinstance(component_manifest, dict) and bool(component_manifest),
    "manifest": component_manifest if isinstance(component_manifest, dict) and component_manifest else None,
}

if component["manifest"]:
    component["domain_matches"] = component["manifest"].get("domain") == domain
    component["version"] = component["manifest"].get("version")
else:
    component["domain_matches"] = False
    component["version"] = None

result = {
    "ok": all(checks.values()),
    "host": os.environ["CHECK_HOST"],
    "ssh_target": os.environ["CHECK_TARGET"],
    "store_reloaded": os.environ["CHECK_RELOAD"] == "true",
    "expected": {
        "repository": expected_repo,
        "app_name": expected_app_name,
        "app_version": expected_version,
        "domain": domain,
    },
    "home_assistant": {
        "hostname": ha_info.get("hostname") if isinstance(ha_info, dict) else None,
        "arch": ha_arch,
        "homeassistant": ha_info.get("homeassistant") if isinstance(ha_info, dict) else None,
        "supervisor": ha_info.get("supervisor") if isinstance(ha_info, dict) else None,
        "operating_system": ha_info.get("operating_system") if isinstance(ha_info, dict) else None,
    },
    "repository": {
        "present": repo_match is not None,
        "slug": repo_slug,
        "data": repo_match,
    },
    "store_app": {
        "visible": store_app is not None,
        "slug": store_app.get("slug") if isinstance(store_app, dict) else None,
        "name": store_app.get("name") if isinstance(store_app, dict) else None,
        "repository": store_app.get("repository") if isinstance(store_app, dict) else None,
        "version_latest": version_latest,
        "installed": store_app.get("installed") if isinstance(store_app, dict) else None,
        "arch": supported_arch,
        "url": store_app.get("url") if isinstance(store_app, dict) else None,
    },
    "installed_app": {
        "present": installed_app is not None,
        "data": installed_app,
    },
    "custom_component": component,
    "checks": checks,
}

print(json.dumps(result, indent=2, sort_keys=True))
PY
