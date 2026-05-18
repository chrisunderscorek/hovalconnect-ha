# HA-0003 Plant Events, Online State and Weather

Status: implemented locally

## User Story

Als Nutzer möchte ich am Anlagen-Device nicht nur Heizkreis-, Warmwasser- und
Wärmepumpenwerte sehen, sondern auch Anlagenzustand, aktive Ereignisse und die
Hoval-Wetterprognose. So ist direkt in Home Assistant sichtbar, ob die Anlage
online ist, ob Hoval aktive Meldungen liefert und welche Außentemperatur die
Hoval-Cloud für die Regelung prognostiziert.

## Umgesetzte Werte

| Home Assistant Name | English name | API-Feld | API-Endpunkt |
| --- | --- | --- | --- |
| `Online` | `Online` | Boolean response | `GET /business/plants/{plantExternalId}/is-online` |
| `Aktive Ereignisse` | `Active events` | `plantEvent.eventType`, Details als Attribute | `GET /business/plants/{plantExternalId}/plant-events/latest` |
| `Prognose Außentemp.` | `Forecast outdoor temp.` | `outsideTemperature` | `GET /v2/api/weather/forecast/{plantExternalId}` |
| `Prognose Außentemp. min.` | `Forecast outdoor temp. min.` | `outsideTemperatureMin` | `GET /v2/api/weather/forecast/{plantExternalId}` |
| `Wetterprognose` | `Weather forecast` | `weatherType` | `GET /v2/api/weather/forecast/{plantExternalId}` |

Alle Werte hängen am Parent-Device `Anlage`, nicht an den Circuit-Devices.

## Namensentscheidung

- `Aktive Ereignisse` orientiert sich an der App-Funktion "Active events".
  Der Sensor zeigt `Keine` / `None`, wenn `plantEvent` leer ist.
- Ereignistypen werden lokalisiert: `locking`, `blocking`, `warning`, `info`,
  `offline`, `ok`.
- Die Wetterfelder heißen in der API `outsideTemperature` und
  `outsideTemperatureMin`. Da die Integration bereits die echte HK-Außentemp.
  als `Außentemp.` anzeigt, heißen die Wetterwerte bewusst
  `Prognose Außentemp.` und `Prognose Außentemp. min.`.
- `weatherType` wird als `Wetterprognose` / `Weather forecast` angezeigt und
  lokalisiert Werte wie `sun`, `partialCloud`, `lightRain` usw.

## Weitere Auslesbare Bereiche

Im OpenAPI-Snapshot und in lokalen Probes sind weitere Endpunkte sichtbar, die
wir bewusst noch nicht als Standard-Sensoren einbauen:

- `GET /support/plants/{plantExternalId}/gateway-status`: Gateway-Status,
  Softwarestände und `lastSeenOnline`. In der lokalen Probe kam kein verwertbarer
  Body zurück, deshalb noch nicht aktiv genutzt.
- `GET /api/gateway-software/{plantExternalId}/versions/current`: Gateway-
  Softwareversion; die lokale Probe lieferte `null`.
- `GET /v2/api/energy-manager-pv-smart/available/{plantExternalId}` und
  `/live`: PV-Smart-/Smart-Grid-Werte. Bei der getesteten Anlage war
  `energyManagerPvSmartAvailable=false`.
- `GET /business/notifications`: offene Ereignisse über alle zugänglichen
  Anlagen. Für die Integration ist der plant-spezifische Latest-Event-Endpunkt
  stabiler und besser auf ein Home-Assistant-Device abbildbar.
- `GET /api/my-plants`: enthält zusätzlich `isOnline`, `isOnboarded` und
  `isContractValid`. Für `Online` wird der plant-spezifische Business-Endpunkt
  verwendet.

## Akzeptanzkriterien

- Die neuen Entitäten erscheinen unter dem Anlagen-Device.
- Ein fehlendes oder leeres `plantEvent` erzeugt keine `unavailable`-Phase,
  sondern den lokalisierten Wert `Keine` / `None`.
- Kurzzeitige Fehler der neuen Plant-Level-Endpunkte verwenden den vorherigen
  Wert weiter und werden in `fetch_stats.plant_errors` sichtbar.
- Wetterwerte bleiben auch dann als Entitäten vorhanden, wenn der Forecast-
  Endpunkt vorübergehend nichts liefert.
