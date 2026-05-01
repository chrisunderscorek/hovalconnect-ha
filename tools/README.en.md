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

Reloads the HA Store, detects the app slug, updates/starts the app on HAOS,
waits until the copied custom component reports the expected version, and prints
the final check JSON. With `--restart-core`, it then restarts Home Assistant
Core so the new Python code is loaded.

```bash
./tools/update_ha_app_on_haos.sh <ha-host> --restart-core
```

The script exits with an error if the app version was updated but
`/config/custom_components/hovalconnect/manifest.json` still contains an older
version.

The SSH user defaults to `root`. Use `--user <user>` when needed.

### `check_ha_app_on_haos.sh`

Checks whether the repository and app are visible on HAOS and whether the custom
integration was installed into `/config/custom_components/hovalconnect` with the
expected version.

```bash
./tools/check_ha_app_on_haos.sh <ha-host> --reload
```

The script prints a single JSON object that can be reused as input for follow-up
checks. `ok` is only `true` when the store version, installed app version, and
copied custom-component version all match.

### Manual HAOS Update Flow

Without SSH commands, the one-shot installer has to be started again after every
update:

1. Update **Hoval Connect** in Home Assistant.
2. Start **Hoval Connect** once.
3. Wait for `Installed Hoval Connect integration <version>` in the app logs.
4. Restart Home Assistant Core.

Clicking Update only updates the app image. It does not automatically copy the
new integration to `/config/custom_components/hovalconnect`.

### `debug_hoval_auth.py`

Debug helper for Hoval OAuth/token and API probing.

```bash
./tools/debug_hoval_auth.py --help
```

Use this only for local debugging. Do not commit tokens or private generated API
responses.

### `analyze_ha_history_availability.py`

Analyzes a local copy of the Home Assistant recorder database and counts
`unavailable`/`unknown` periods for Hoval entities. The script does not install
anything on HAOS; copy the database to `localdata/` first.

```bash
./tools/analyze_ha_history_availability.py \
  ../localdata/home-assistant_v2.db \
  --entity-like '%hoval%' \
  --days 3 \
  --short-threshold 10 \
  --pretty
```
