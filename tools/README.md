# Tools

Dieses Verzeichnis enthaelt Helper-Skripte fuer lokale Hoval Connect App
Entwicklung, Pretest-Images und Checks auf Home Assistant OS.

Alle Beispiele verwenden relative Pfade oder Platzhalter. Private Token-Dateien
sollten ausserhalb des Git-Repositories liegen und explizit mit `--token-file`
uebergeben werden.

## Typischer Pretest Flow

Kompletter lokaler Pretest Flow:

```bash
./tools/pretest_ha_app_release.sh <ha-host> \
  --token-file <path-to-ghcr-token> \
  --restart-core
```

Der Wrapper fuehrt diese Schritte aus:

1. App-Images fuer `amd64` und `aarch64` bauen und nach GHCR pushen.
2. Multi-Arch-Versionstag und `latest` erzeugen/aktualisieren.
3. Nur `hovalconnect/config.yaml` nach `origin/main` pushen, damit der HA Store
   die Pretest-Version sieht.
4. App auf HAOS per SSH aktualisieren/starten.
5. Home Assistant Core neu starten, wenn `--restart-core` gesetzt ist.

App-Version und Image-Name werden standardmaessig aus
`hovalconnect/config.yaml` gelesen.

## Scripts

### `build_push_ghcr_app.sh`

Baut und pusht die GHCR App-Images.

```bash
./tools/build_push_ghcr_app.sh --token-file <path-to-ghcr-token>
```

Nuetzliche Optionen:

- `--version <version>` ueberschreibt die Version aus `hovalconnect/config.yaml`.
- `--image <image>` ueberschreibt das Image aus `hovalconnect/config.yaml`.
- `--skip-login` nutzt vorhandene Docker Credentials.
- `--dry-run` zeigt die Docker-Kommandos, ohne sie auszufuehren.

### `publish_pretest_config_only.sh`

Pusht nur die App-Version in `hovalconnect/config.yaml` auf den remote
`main`-Branch. Damit kann HAOS das Pretest-Image finden, waehrend die echten
Code-Aenderungen lokal bleiben.

```bash
./tools/publish_pretest_config_only.sh
```

Standardmaessig rebased das Skript den aktuellen Branch nach dem config-only
Commit wieder auf `origin/main`.

### `update_ha_app_on_haos.sh`

Laedt den HA Store neu, findet den App-Slug, aktualisiert/startet die App auf
HAOS und gibt danach das finale Check-JSON aus.

```bash
./tools/update_ha_app_on_haos.sh <ha-host> --restart-core
```

Der SSH-User ist standardmaessig `root`. Bei Bedarf `--user <user>` verwenden.

### `check_ha_app_on_haos.sh`

Prueft, ob Repository und App auf HAOS sichtbar sind und ob die Custom
Integration unter `/config/custom_components/hovalconnect` installiert wurde.

```bash
./tools/check_ha_app_on_haos.sh <ha-host> --reload
```

Das Skript gibt ein einzelnes JSON-Objekt aus, das sich fuer weitere Checks
weiterverwenden laesst.

### `debug_hoval_auth.py`

Debug-Helper fuer Hoval OAuth/Token und API-Probing.

```bash
./tools/debug_hoval_auth.py --help
```

Nur fuer lokales Debugging verwenden. Tokens oder private API-Antworten nicht
committen.
