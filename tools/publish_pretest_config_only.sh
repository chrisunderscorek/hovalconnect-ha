#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  tools/publish_pretest_config_only.sh [options]

Push only hovalconnect/config.yaml to the remote main branch so Home Assistant
can discover a locally built pretest image, while keeping the real code changes
local until they have been tested.

Options:
  --version VERSION       App version to publish (default: read from hovalconnect/config.yaml)
  --remote NAME           Git remote (default: origin)
  --branch NAME           Remote branch (default: main)
  --message MESSAGE       Commit message
                           (default: Pretesting VERSION images only [skip ci])
  --no-rebase             Do not rebase the current branch after pushing
  --allow-dirty           Allow running with local uncommitted changes
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
remote="origin"
branch="main"
message=""
rebase_current="true"
allow_dirty="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            version="${2:-}"
            shift 2
            ;;
        --remote)
            remote="${2:-}"
            shift 2
            ;;
        --branch)
            branch="${2:-}"
            shift 2
            ;;
        --message)
            message="${2:-}"
            shift 2
            ;;
        --no-rebase)
            rebase_current="false"
            shift
            ;;
        --allow-dirty)
            allow_dirty="true"
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

if [[ -z "${version}" ]]; then
    echo "Could not determine app version; pass --version explicitly." >&2
    exit 2
fi

if [[ -z "${message}" ]]; then
    message="Pretesting ${version} images only [skip ci]"
fi

if [[ "${allow_dirty}" != "true" ]]; then
    if [[ -n "$(git -C "${repo_root}" status --porcelain)" ]]; then
        echo "Working tree is not clean. Commit/stash changes or pass --allow-dirty." >&2
        exit 2
    fi
fi

current_branch="$(git -C "${repo_root}" branch --show-current)"
tmp_parent="$(mktemp -d)"
tmp_worktree="${tmp_parent}/pretest-config"

cleanup() {
    git -C "${repo_root}" worktree remove --force "${tmp_worktree}" >/dev/null 2>&1 || true
    rm -rf "${tmp_parent}"
}
trap cleanup EXIT

git -C "${repo_root}" fetch "${remote}" "${branch}"
git -C "${repo_root}" worktree add --detach "${tmp_worktree}" "${remote}/${branch}"

VERSION="${version}" python3 - "${tmp_worktree}/hovalconnect/config.yaml" <<'PY'
import os
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = os.environ["VERSION"]
text = path.read_text(encoding="utf-8")
new_text, count = re.subn(r'(?m)^version:\s*["\']?[^"\'\n]+["\']?\s*$', f'version: "{version}"', text, count=1)
if count != 1:
    raise SystemExit(f"Could not update version line in {path}")
path.write_text(new_text, encoding="utf-8")
PY

if git -C "${tmp_worktree}" diff --quiet -- hovalconnect/config.yaml; then
    echo "Remote ${remote}/${branch} already advertises version ${version}; no config-only commit needed." >&2
else
    git -C "${tmp_worktree}" add hovalconnect/config.yaml
    git -C "${tmp_worktree}" commit -m "${message}"
    git -C "${tmp_worktree}" push "${remote}" "HEAD:${branch}"
fi

git -C "${repo_root}" fetch "${remote}" "${branch}"

if [[ "${rebase_current}" == "true" && -n "${current_branch}" ]]; then
    echo "Rebasing ${current_branch} onto ${remote}/${branch}." >&2
    git -C "${repo_root}" rebase "${remote}/${branch}"
else
    echo "Skipped rebase of current branch." >&2
fi
