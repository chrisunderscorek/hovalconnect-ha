#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  tools/pretest_ha_app_release.sh HOST [options]

Run the normal local pretest flow:
  1. build and push GHCR app images
  2. push only hovalconnect/config.yaml to origin/main for HA Store discovery
  3. update/start the app on HAOS

Options:
  --version VERSION       App/image version (default: read from hovalconnect/config.yaml)
  --image IMAGE           Image name (default: read from hovalconnect/config.yaml)
  --token-file FILE       GHCR token file for docker login
  --registry-user USER    GHCR user for docker login
  --user USER             SSH user for HAOS when HOST has no user part (default: root)
  --restart-core          Restart Home Assistant Core after app update/start
  --no-latest             Do not update the latest image tag
  --skip-build            Skip GHCR build/push
  --skip-config-push      Skip config-only remote push
  --skip-ha-update        Skip HAOS update/start
  --help                  Show this help
USAGE
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

host=""
version=""
image=""
token_file=""
registry_user=""
ssh_user="root"
restart_core="false"
tag_latest="true"
skip_build="false"
skip_config_push="false"
skip_ha_update="false"

if [[ $# -gt 0 && "$1" != --* ]]; then
    host="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            version="${2:-}"
            shift 2
            ;;
        --image)
            image="${2:-}"
            shift 2
            ;;
        --token-file)
            token_file="${2:-}"
            shift 2
            ;;
        --registry-user)
            registry_user="${2:-}"
            shift 2
            ;;
        --user)
            ssh_user="${2:-}"
            shift 2
            ;;
        --restart-core)
            restart_core="true"
            shift
            ;;
        --no-latest)
            tag_latest="false"
            shift
            ;;
        --skip-build)
            skip_build="true"
            shift
            ;;
        --skip-config-push)
            skip_config_push="true"
            shift
            ;;
        --skip-ha-update)
            skip_ha_update="true"
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

if [[ "${skip_ha_update}" != "true" && -z "${host}" ]]; then
    echo "Missing required HOST argument unless --skip-ha-update is used." >&2
    usage >&2
    exit 2
fi

build_args=()
publish_args=()
ha_args=()

if [[ -n "${version}" ]]; then
    build_args+=(--version "${version}")
    publish_args+=(--version "${version}")
    ha_args+=(--app-version "${version}")
fi

if [[ -n "${image}" ]]; then
    build_args+=(--image "${image}")
fi

if [[ -n "${token_file}" ]]; then
    build_args+=(--token-file "${token_file}")
fi

if [[ -n "${registry_user}" ]]; then
    build_args+=(--registry-user "${registry_user}")
fi

if [[ "${tag_latest}" != "true" ]]; then
    build_args+=(--no-latest)
fi

if [[ "${restart_core}" == "true" ]]; then
    ha_args+=(--restart-core)
fi

run_with_optional_args() {
    local command="$1"
    shift
    if [[ "$#" -gt 0 ]]; then
        "${command}" "$@"
    else
        "${command}"
    fi
}

if [[ "${skip_build}" != "true" ]]; then
    if [[ "${#build_args[@]}" -gt 0 ]]; then
        run_with_optional_args "${script_dir}/build_push_ghcr_app.sh" "${build_args[@]}"
    else
        run_with_optional_args "${script_dir}/build_push_ghcr_app.sh"
    fi
fi

if [[ "${skip_config_push}" != "true" ]]; then
    if [[ "${#publish_args[@]}" -gt 0 ]]; then
        run_with_optional_args "${script_dir}/publish_pretest_config_only.sh" "${publish_args[@]}"
    else
        run_with_optional_args "${script_dir}/publish_pretest_config_only.sh"
    fi
fi

if [[ "${skip_ha_update}" != "true" ]]; then
    if [[ "${#ha_args[@]}" -gt 0 ]]; then
        run_with_optional_args "${script_dir}/update_ha_app_on_haos.sh" "${host}" --user "${ssh_user}" "${ha_args[@]}"
    else
        run_with_optional_args "${script_dir}/update_ha_app_on_haos.sh" "${host}" --user "${ssh_user}"
    fi
fi
