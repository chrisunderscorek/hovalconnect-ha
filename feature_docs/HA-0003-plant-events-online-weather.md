# HA-0003 Plant Events, Online State and Weather

Status: released in 1.1.1

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
| `Gateway-Daten` | `Gateway data` | Metadaten als Attribute | `GET /v1/plants/{plantExternalId}/settings`, `GET /api/my-plants`, `GET /support/plants/{plantExternalId}/gateway-status`, `GET /api/gateway-software/{plantExternalId}/versions/current` |

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
- `Gateway-Daten` ist bewusst eine Diagnose-Entität. Der Zustand ist nur ein
  kompakter Hinweis, die eigentlichen Gateway-/Anlagenmetadaten werden als
  Attribute abgelegt. Adresse, Ort, Postleitzahl und Koordinaten werden nicht
  als Attribute veröffentlicht.

## Entity-Kategorien

Die lokal geprüfte Altinstallation nutzt `diagnostic` für technische
Latest-Event-Detailwerte. `active_events`, Wetter und Forecast-Temperatur waren
normale Entitäten.

Für diese Integration gilt deshalb:

- `Online` und `Gateway-Daten` sind `EntityCategory.DIAGNOSTIC`, weil sie
  Verbindung und Gateway-Kontext beschreiben.
- `Aktive Ereignisse` bleibt eine normale Anlagen-Entität, damit aktive
  Meldungen nicht in Diagnose-Details verschwinden.
- Wetterprognose und Forecast-Temperaturen bleiben normale Entitäten, weil sie
  nutzbare Zustands-/Vorhersagewerte für Automationen und Dashboards sind.

## Weitere Auslesbare Bereiche

Im OpenAPI-Snapshot und in lokalen Probes sind weitere Endpunkte sichtbar, die
wir bewusst noch nicht als Standard-Sensoren einbauen:

- `GET /support/plants/{plantExternalId}/gateway-status`: Gateway-Status,
  Softwarestände und `lastSeenOnline`. Der Endpunkt wird als optionale
  Diagnosequelle genutzt, kann aber je nach Benutzerrolle leer oder nicht
  freigegeben sein.
- `GET /api/gateway-software/{plantExternalId}/versions/current`: Gateway-
  Softwareversion. Der Wert ist langsam veränderlich und wird als Diagnose-
  Attribut genutzt.
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
