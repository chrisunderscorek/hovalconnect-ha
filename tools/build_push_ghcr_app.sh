#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  tools/build_push_ghcr_app.sh [options]

Build and push the Home Assistant app image to GHCR for amd64 and aarch64,
then publish the multi-arch version tag.

Options:
  --version VERSION       Image/app version (default: read from hovalconnect/config.yaml)
  --image IMAGE           Image name (default: read from hovalconnect/config.yaml)
  --registry-user USER    Registry user for docker login (default: image owner)
  --token-file FILE       Read registry token from FILE and run docker login
  --skip-login            Do not run docker login
  --no-latest             Do not update the latest tag
  --dry-run               Print docker commands without running them
  --help                  Show this help
USAGE
}

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

version=""
image=""
registry_user=""
token_file=""
skip_login="false"
tag_latest="true"
dry_run="false"

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
        --registry-user)
            registry_user="${2:-}"
            shift 2
            ;;
        --token-file)
            token_file="${2:-}"
            shift 2
            ;;
        --skip-login)
            skip_login="true"
            shift
            ;;
        --no-latest)
            tag_latest="false"
            shift
            ;;
        --dry-run)
            dry_run="true"
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

if [[ -z "${version}" ]]; then
    version="$(read_config_value version)"
fi

if [[ -z "${image}" ]]; then
    image="$(read_config_value image)"
fi

if [[ -z "${version}" || -z "${image}" ]]; then
    echo "Could not determine image/version; pass --image and --version explicitly." >&2
    exit 2
fi

registry="${image%%/*}"
if [[ "${registry}" == "${image}" ]]; then
    registry="docker.io"
fi

if [[ -z "${registry_user}" && "${image}" == ghcr.io/*/* ]]; then
    owner="${image#ghcr.io/}"
    registry_user="${owner%%/*}"
fi

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if [[ "${dry_run}" != "true" ]]; then
        "$@"
    fi
}

if [[ "${skip_login}" != "true" && -n "${token_file}" ]]; then
    if [[ -z "${registry_user}" ]]; then
        echo "Missing --registry-user for docker login." >&2
        exit 2
    fi
    if [[ ! -r "${token_file}" ]]; then
        echo "Cannot read token file: ${token_file}" >&2
        exit 2
    fi
    printf '+ docker login %q --username %q --password-stdin < %q\n' "${registry}" "${registry_user}" "${token_file}"
    if [[ "${dry_run}" != "true" ]]; then
        docker login "${registry}" --username "${registry_user}" --password-stdin < "${token_file}"
    fi
elif [[ "${skip_login}" != "true" ]]; then
    echo "Skipping docker login because --token-file was not provided; using existing credentials." >&2
fi

build_arch() {
    local platform="$1"
    local hass_arch="$2"
    run docker buildx build \
        --platform "${platform}" \
        --provenance=false \
        --sbom=false \
        --build-arg "BUILD_VERSION=${version}" \
        --build-arg "BUILD_ARCH=${hass_arch}" \
        -t "${image}:${version}-${hass_arch}" \
        --push \
        -f "${repo_root}/hovalconnect/Dockerfile" \
        "${repo_root}"
}

build_arch linux/amd64 amd64
build_arch linux/arm64 aarch64

manifest_cmd=(docker buildx imagetools create -t "${image}:${version}")
if [[ "${tag_latest}" == "true" ]]; then
    manifest_cmd+=(-t "${image}:latest")
fi
manifest_cmd+=("${image}:${version}-amd64" "${image}:${version}-aarch64")
run "${manifest_cmd[@]}"

run docker buildx imagetools inspect "${image}:${version}"
if [[ "${tag_latest}" == "true" ]]; then
    run docker buildx imagetools inspect "${image}:latest"
fi
