# HA-0001 Reliable Hoval Cloud Fetches

Status: released in 0.2.0

## User Story

Als Nutzer moechte ich, dass kurze Aussetzer der Hoval Cloud nicht sofort zu
`unavailable` in Home Assistant fuehren, damit Diagramme und Langzeitstatistiken
nicht durch Sekunden-Aussetzer verfaelscht werden.

Als Nutzer moechte ich ausserdem die Modulation als 30-Sekunden-Livewert
auswerten koennen. Wenn die Waermepumpe aus ist oder wartet und die Cloud keinen
Modulationswert liefert, soll die Modulation fachlich `0%` sein statt
`unknown`.

## Problem

Die Hoval Cloud liefert gelegentlich transiente Fehler:

- HTTP `429`
- HTTP `5xx`
- HTTP `599`
- Netzwerk-/Timeout-Fehler

Vor HA-0001 konnten diese Fehler zwei schlechte Effekte haben:

- Ein kompletter `/circuits`-Fehler machte den Coordinator-Update-Lauf
  fehlerhaft; Home Assistant konnte Entities kurz als `unavailable` sehen.
- Fehlende einzelne `live-values` konnten einzelne Sensoren auf `unknown` oder
  `unavailable` kippen lassen.

Zusaetzlich wurde beim Speichern erneuerter Tokens die Config Entry aktualisiert.
Der bestehende Update-Listener hat darauf wie auf eine Optionsaenderung reagiert
und die Integration neu geladen. Das erzeugte ebenfalls kurze
`unavailable`-Phasen.

## Faktenbasis

Quelle:

- HA-Core-Logs per `ha core logs --lines 5000`
- lokale Recorder-DB-Kopie unter `localdata/home-assistant_v2.db`
- Auswertung mit `tools/analyze_ha_history_availability.py`

Beobachtungen:

- 12 `live-values` Fehler in der Log-Stichprobe.
- 3 komplette `/circuits` Coordinator-Fehler in der Log-Stichprobe.
- Im 1-Tages-Fenster: 30 Hoval-Entities, 782 `unavailable`, 92 `unknown`.
- Davon 727 kurze `unavailable`-Ereignisse mit Dauer <= 10 Sekunden.
- Typischer kurzer Aussetzer: ca. 1,2 Sekunden pro Entity.
- Fuer `sensor.hoval_belaria_8_pro_modulation` gab es in der DB keinen `0`
  State; beobachtet wurden nur Werte wie `3`, `30`, `42` sowie `unknown` und
  `unavailable`.

Die Rohreports liegen ausserhalb des Git-Repositories in `localdata/`.

## Akzeptanzkriterien

- Transiente Cloud-Fehler werden innerhalb eines begrenzten Retry-Fensters
  erneut versucht.
- Das Retry-Fenster orientiert sich am Polling-Intervall und versucht mindestens
  einen Retry.
- Erfolgreiche Requests mit Retry loggen Dauer und Retry-Anzahl.
- Ein kurzer `/circuits`-Ausfall verwendet vorhandene Coordinator-Daten weiter,
  statt alle Entities sofort `unavailable` werden zu lassen.
- Ein einzelner `live-values`-Ausfall verwendet vorhandene Werte fuer den
  betroffenen Circuit weiter.
- Token-Persistenz darf keinen Integrations-Reload ausloesen.
- Nicht genutzte `GW` Live-Value-Fetches werden nicht mehr ausgefuehrt.
- Modulation wird als BL-Livewert behandelt.
- Fehlende Modulation wird als `0%` normalisiert, wenn der
  Waermeerzeuger-/WFA-Status aus oder wartend ist.
- Modulation kann auf 30-Sekunden-Recorder-Cadence beobachtet werden.

## Umsetzung

### Retry

Retryable:

- `429`
- `500`
- `502`
- `503`
- `504`
- `599`
- `aiohttp` Client-/Timeout-Fehler

Backoff:

- `2s`
- `5s`
- `8s`

Das Fenster ist aktuell:

- `max(5s, UPDATE_INTERVAL_SECONDS / 2)`
- bei 30 Sekunden Polling also 15 Sekunden

Beispiel-Log:

```text
GET <URL> fetched: 6321 msec, 2 retries
```

### Stale Data

Wenn `/circuits` fehlschlaegt und es bereits Coordinator-Daten gibt, werden die
alten Daten weitergegeben. Dadurch bleiben Entities verfuegbar.

Wenn ein einzelner Live-Value-Fetch fehlschlaegt, werden fuer diesen Circuit die
letzten bekannten Live-Werte weitergegeben.

### Token Updates

Erneuerte Tokens werden weiterhin in der Config Entry gespeichert. Der
Options-Listener unterscheidet jetzt aber zwischen reinen Datenupdates und
echten Optionsaenderungen. Nur Optionsaenderungen fuehren zu einem Reload.

### Modulation

Modulation ist ein Live-Wert aus dem BL-Circuit:

```text
GET /v3/api/statistics/live-values/{plant_id}
key = modulation
```

Wenn der Key fehlt und der Status aus oder wartend ist, wird der Sensorwert auf
`0` gesetzt. Die Rohlage bleibt als Attribute sichtbar.

Inaktive/Warte-Indikatoren:

- Live-Status: `off`, `standby`, `idle`, `waiting`, `wait`, `ready`
- WFA-Codes: `0`, `3`, `16`, `17`, `18`, `19`

## Nicht-Ziele

- Keine Veraenderung der globalen Home-Assistant-History- oder
  Recorder-Konfiguration.
- Keine UI-spezifische 30-Sekunden-Darstellung erzwingen; die verwendete Karte
  entscheidet, ob sie Rohdaten oder aggregierte Daten zeigt.
- Keine generelle `force_update`-Aktivierung fuer alle Sensoren.

## Referenzen

- Changelog: `HA-0001`
- Code:
  - `custom_components/hovalconnect/api.py`
  - `custom_components/hovalconnect/__init__.py`
  - `custom_components/hovalconnect/sensor.py`
  - `custom_components/hovalconnect/const.py`
- Tool:
  - `tools/analyze_ha_history_availability.py`
