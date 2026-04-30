# Tools

This directory contains helper scripts for local Hoval Connect app development,
pretest image publishing, and Home Assistant OS checks.

All examples use relative paths or placeholders. Keep private token files outside
the Git repository and pass them explicitly with `--token-file`.

## Typical Pretest Flow

Run the full local pretest flow:

```bash
./tools/pretest_ha_app_release.sh <ha-host> \
  --token-file <path-to-ghcr-token> \
  --restart-core
```

The wrapper performs these steps:

1. Build and push the app images for `amd64` and `aarch64` to GHCR.
2. Create/update the multi-arch version tag and the `latest` tag.
3. Push only `hovalconnect/config.yaml` to `origin/main` so the HA Store can see
   the pretest version.
4. Update/start the app on HAOS over SSH.
5. Restart Home Assistant Core when `--restart-core` is set.

The app version and image name are read from `hovalconnect/config.yaml` by
default.

## Scripts

### `build_push_ghcr_app.sh`

Builds and pushes the GHCR app images.

```bash
./tools/build_push_ghcr_app.sh --token-file <path-to-ghcr-token>
```

Useful options:

- `--version <version>` overrides the version from `hovalconnect/config.yaml`.
- `--image <image>` overrides the image from `hovalconnect/config.yaml`.
- `--skip-login` uses existing Docker credentials.
- `--dry-run` prints the Docker commands without running them.

### `publish_pretest_config_only.sh`

Pushes only the app version in `hovalconnect/config.yaml` to the remote `main`
branch. This allows HAOS to discover the pretest image while the actual code
changes remain local.

```bash
./tools/publish_pretest_config_only.sh
```

By default, the script rebases the current branch onto `origin/main` after the
config-only commit has been pushed.

### `update_ha_app_on_haos.sh`

Reloads the HA Store, detects the app slug, updates/starts the app on HAOS, and
prints the final check JSON.

```bash
./tools/update_ha_app_on_haos.sh <ha-host> --restart-core
```

The SSH user defaults to `root`. Use `--user <user>` when needed.

### `check_ha_app_on_haos.sh`

Checks whether the repository and app are visible on HAOS and whether the custom
integration was installed into `/config/custom_components/hovalconnect`.

```bash
./tools/check_ha_app_on_haos.sh <ha-host> --reload
```

The script prints a single JSON object that can be reused as input for follow-up
checks.

### `debug_hoval_auth.py`

Debug helper for Hoval OAuth/token and API probing.

```bash
./tools/debug_hoval_auth.py --help
```

Use this only for local debugging. Do not commit tokens or private generated API
responses.
