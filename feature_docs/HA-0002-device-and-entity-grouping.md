# HA-0002 Device and Entity Grouping

Status: implemented locally

## User Story

Als Nutzer moechte ich die Hoval-Entitaeten in Home Assistant nicht als eine
lange gemischte Liste sehen, sondern fachlich nach Anlagenteilen gruppiert,
damit ich Werte schneller finde und die UI der HovalConnect-App besser
wiedererkenne.

Fuer meine Anlage sollen mindestens diese Gruppen sichtbar sein:

- Anlage
- WP / Waermepumpe
- Heizkoerper
- Warmwasser

Die Gruppierung soll nicht nur ueber Namenspraefixe funktionieren, sondern ueber
Home-Assistant-Devices, damit Home Assistant die Entitaeten nativ in diesen
Gruppen zeigt.

## Problem

Aktuell haengen die Entities weitgehend an einem gemeinsamen Device. Dadurch ist
in Home Assistant zwar jede Entity vorhanden, die fachliche Struktur der Anlage
geht aber verloren. Besonders bei gleichen oder aehnlichen Namen wie `Status`,
`Akt. Prog.` oder `Ist-Temp.` ist ohne Device-Kontext nicht schnell erkennbar,
ob der Wert zur Anlage, zur Waermepumpe, zum Heizkreis oder zum Warmwasser
gehoert.

## Zielbild

Die Integration bildet die Hoval-Anlage als native Home-Assistant-Device-
Hierarchie ab:

- ein Parent-Device fuer die gesamte Anlage
- ein Child-Device pro relevantem Circuit
- Child-Devices verweisen per `via_device` auf die Anlage
- Entity-`unique_id`s bleiben unveraendert

Damit entsteht die Gruppierung aus der Device Registry und nicht aus kuenstlich
verlaengerten Entity-Namen.

### Anlage

Parent-Device fuer die gesamte Hoval-Anlage.

Identifier:

```text
(DOMAIN, plant_id)
```

Name:

```text
Hoval <Anlagenname>
```

Falls kein Anlagenname bekannt ist:

```text
Hoval <plant_id>
```

Plant-Level-Entities sollen hier landen, zum Beispiel:

- Online-/Cloud-Status
- Anlagenstatus / Plant Events
- Gateway-Status, falls wir ihn spaeter expose'n
- Wetter/Forecast, falls diese Entities uebernommen werden

### WP / Waermepumpe

Child-Device fuer den `BL`-Circuit.

Identifier:

```text
(DOMAIN, f"{plant_id}:circuit:{circuit_path}")
```

Name bevorzugt aus der API:

```text
Hoval <circuit.name>
```

Bei meiner Anlage waere das z. B. `Hoval BelariaPro`. Falls der API-Name fehlt,
wird lokalisiert auf `Waermepumpe` / `Heat pump` oder `Waermeerzeuger` /
`Heat generator` zurueckgefallen.

Entities:

- Status Waermeerzeuger
- Waermeerzeuger-Ist
- Waermeerzeuger Soll
- Ruecklauftemp.
- Modulation
- Betriebsstunden
- Betriebsstunden > 50%
- Schaltzyklen
- Waermeabgabe
- Stromverbrauch Inverter
- Betriebsstatus

### Heizkoerper / Heizkreis

Child-Device fuer `HK`-Circuits.

Name bevorzugt aus `circuit.name`, bei meiner Anlage also `Heizkoerper`.
Fallback lokalisiert:

- `Heizkreis`
- `Heating circuit`

Falls mehrere Heizkreise existieren, wird pro `circuit_path` ein eigenes Device
angelegt und der API-Name bzw. Pfad macht die Gruppe eindeutig.

Entities:

- Climate Entity fuer HK
- Programm-Select fuer HK
- Vorlauftemp. Ist
- Vorlauftemp. Soll
- Raumtemp. Ist
- Raumtemp. Soll
- Aussentemp.
- Status Heizkreis
- Akt. Heizkreisprog.

### Warmwasser

Child-Device fuer `WW`-Circuits.

Name bevorzugt aus `circuit.name`, bei meiner Anlage also `Warmwasser`.
Fallback lokalisiert:

- `Warmwasser`
- `Hot water`

Entities:

- Climate Entity fuer WW
- Programm-Select fuer WW
- Soll-Temp.
- Ist-Temp. SF1 / Ist-Temp. WW
- Ist-Temp. SF2
- Status Warmwasser
- Akt. Warmwasserprog.

## Dynamische Gruppierung

Die Implementierung soll aus den API-Circuits abgeleitet werden:

| Circuit type | Device group |
| --- | --- |
| `BL` | WP / Waermepumpe / Heat generator |
| `HK` | Heizkoerper bzw. Heizkreis |
| `WW` | Warmwasser |
| `HV` | HomeVent / Lueftung, wenn spaeter implementiert |
| `GW` | Anlage oder Gateway, nur wenn wir Gateway-Entities expose'n |
| unbekannt | eigenes Circuit-Device mit API-Name und Typ als Modell |

Wichtig: Keine hart codierten Produktnamen. API-Namen und Circuit-Pfade muessen
die Quelle der Wahrheit sein.

## Best-Practice-Regeln

- `unique_id`s bleiben stabil, damit Entity-IDs, Historie, Dashboards und
  Automationen nicht unnoetig brechen.
- Device-Identifiers sind stabil und enthalten Plant-ID plus Circuit-Pfad.
- Das Parent-Device beschreibt die Anlage, nicht zufaellig den ersten
  Waermepumpen-Circuit.
- Circuit-Device-Namen kommen bevorzugt aus `circuit.name`.
- Circuit-Device-Modelle kommen aus dem lokalisierten Circuit-Typ.
- Manuell in Home Assistant geaenderte Device-Namen duerfen nicht aggressiv
  ueberschrieben werden.
- Entity-Namen bleiben kurz; der fachliche Kontext kommt vom Device.
- HA-Areas werden nicht automatisch gesetzt.

## Nicht-Ziele

- Keine vorkonfigurierten Home-Assistant-Dashboards bauen.
- Keine Home-Assistant-Areas automatisch setzen; das bleibt Nutzerentscheidung.
- Keine Entity-IDs absichtlich umbenennen.
- Keine neuen API-Endpoints nur fuer diese Gruppierung einfuehren.
- Keine Sortierreihenfolge erzwingen, die Home Assistant selbst nicht stabil
  garantiert. Ziel ist saubere Device-Gruppierung, nicht manuelles UI-Sorting.

## Akzeptanzkriterien

- Es gibt ein Parent-Device fuer die Anlage.
- Jeder relevante Circuit bekommt ein eigenes Child-Device mit `via_device` zur
  Anlage.
- Entities werden dem fachlich richtigen Device zugeordnet:
  - BL-Werte zur WP / Waermepumpe
  - HK-Werte und HK-Control-Entities zum Heizkreis
  - WW-Werte und WW-Control-Entities zum Warmwasser
  - Plant-Level-Werte zur Anlage
- Bestehende `unique_id`s bleiben stabil, damit bestehende Entity-IDs,
  Dashboards und Historien nicht unnoetig kaputtgehen.
- Device-Namen werden bevorzugt aus `circuit.name` bzw. Plant-Daten gebildet.
- Fallback-Namen sind lokalisiert fuer Deutsch und Englisch.
- Mehrere Circuits desselben Typs erzeugen mehrere eindeutige Devices.
- Die aktuelle Anlage ergibt sichtbar mindestens die Gruppen Anlage,
  WP/Waermepumpe, Heizkoerper und Warmwasser.
- HAOS-Update- und Installationsweg bleiben unveraendert.

## Implementierung

Das Modul `devices.py` kapselt die Device-Registry-Logik, damit
Lokalisierung, Entity-Namen und Device-Struktur nicht weiter vermischt werden:

- `plant_device_info(...)`
- `circuit_device_info(...)`
- `circuit_device_identifier(...)`

Die Anlage wird beim Setup explizit als Parent-Device registriert. Die Entity-
Plattformen verwenden danach fuer Circuit-Entities das passende Child-Device:

- `sensor.py`
- `climate.py`
- `select.py`

Neue Config-Flows speichern den Anlagenname zusaetzlich als `plant_name`; fuer
bestehende Installationen wird der Name aus dem Config-Entry-Titel abgeleitet
oder auf `plant_id` zurueckgefallen.

## Risiken / Migrationsfragen

- Home Assistant kann durch geaendertes `device_info` neue Devices anlegen und
  Entities in diese Devices verschieben. Das ist gewollt, aber muss getestet
  werden.
- Bestehende Entity-IDs duerfen sich nicht aendern. Entscheidend sind stabile
  `unique_id`s.
- Alte leere Devices koennen in HA sichtbar bleiben, wenn Home Assistant sie
  nicht automatisch bereinigt. Das muss beim Test auf HAOS beobachtet werden.
- Falls ein Nutzer manuell Device-Namen geaendert hat, darf die Integration
  nicht aggressiv dagegen arbeiten.

## Testplan

- Lokaler Syntaxcheck.
- HAOS installieren/starten und Core neu starten.
- In Home Assistant pruefen:
  - Anlage-Device existiert.
  - Child-Devices existieren fuer BL, HK, WW.
  - Child-Devices zeigen `via_device` zur Anlage.
  - Entity-IDs bleiben stabil.
  - Entitaeten liegen in den erwarteten Gruppen.
