# Changelog

## 0.3.0

- Lovelace-Karte `heat-pilot-card` (wird automatisch geladen, keine Ressource nötig): Heizperiode (mit Bearbeiten), Abwesenheitsmodus mit Rückkehrzeit, Frostschutz und Maximaltemperatur, je Raum Status, Ist/Soll, Komfort/Absenkung, alle Raumschalter und „Plan bearbeiten“.
- Karte wird mit Cache-Buster und zusätzlich als ES5-Skript registriert und definiert sich nach dem Start von Home Assistant erneut (Workaround für die Android Companion App).
- Status-Sensor liefert zusätzlich `schedule` und `thermostats`.

## 0.2.0

- Benachrichtigungen: Türwarnung (nach der Wartezeit des Raums, dann alle 3 Minuten, maximal 3, nur an Personen zu Hause, nur in der Heizperiode, unterdrückt bei ausgeschaltetem und heute nicht beheiztem Raum), Lüftungserinnerung nach offenem Fenster, Störungsmeldungen an das Admin-Handy (Sensor/Thermostat nicht erreichbar, Überhitzung; alle 6 Stunden, nur 08:00–22:00).
- Einstellungen (Optionen): Admin-Handy, Handy je Person, Schwellwerte, Dashboard-Pfad.
- Warnungen verschwinden von allen Handys, sobald die Tür geschlossen ist.

## 0.1.0

- Erste Version: zentrale, raumweise Heizungssteuerung (Config-Flow mit Räumen als Subentries, DataUpdateCoordinator, persistenter Zustand).
- Entscheidungslogik mit fester Priorität: Heizperiode, Abwesenheitsmodus, offene Tür/Fenster, Raumabwesenheit, Zeitplan (Komfort/Absenkung, „Absenkung überspringen“).
- Entitäten pro Raum und global, Dienst `heat_pilot.set_heating_period`.
