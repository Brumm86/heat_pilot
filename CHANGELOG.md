# Changelog

## 0.6.0

- Die Meldungen „Thermostat nicht erreichbar“ und die Überhitzungswarnung relativ zum Sollwert entfallen (zu viele Fehlalarme bei funktionierenden Thermostaten). Ersatz: Der Admin wird benachrichtigt, wenn ein Thermostat mindestens **25 °C** misst, und zwar **15 Minuten** lang (beides in den Einstellungen änderbar, nur in der Heizperiode; Wiederholung alle 6 Stunden, 08–22 Uhr). Die Meldung „Tür-/Fenstersensor nicht erreichbar“ bleibt.
- Die Türwarnung kommt jetzt nach **5 Minuten** offener Tür (unabhängig von der Wartezeit zum Abschalten der Heizung), dann wie bisher alle 3 Minuten, maximal 3-mal.
- Neuer Button „Türsensor anlernen“ (auch in der Karte unter „Allgemeine Einstellungen“): öffnet das ZHA-Netzwerk für 2 Minuten (`zha.permit`). Danach die Reset-Taste am Sensor ca. 3 Sekunden halten, bis die LED blinkt; ZHA erkennt den Sensor an seiner IEEE-Adresse wieder, die Entitäten bleiben erhalten.

## 0.5.0

- Lovelace-Karte: „Allgemeine Einstellungen“ und jeder Raum sind einklappbar und standardmäßig eingeklappt. Status-Chips (Heizperiode, offen, Raumstatus) bleiben in der Kopfzeile sichtbar.
- Jede an ein Handy gesendete Meldung (Türwarnung, Lüftungserinnerung, Störungen) erscheint zusätzlich als dauerhafte Benachrichtigung in der Mitteilungszentrale von Home Assistant. Wiederholungen ersetzen sich, die Benachrichtigung verschwindet, sobald die Ursache behoben ist.
- Ein Tipp auf die Handy-Meldung öffnet die Mitteilungszentrale (Dashboard-Pfad mit `?heat_pilot_notifications=1`; die Karten-Skriptdatei, die Home Assistant ohnehin lädt, öffnet daraufhin die Mitteilungen).

## 0.4.0

- Neue Raumoption „Raum wird anders beheizt (z. B. Fußbodenheizung)“: Die Türwarnung wird dann auch ausgelöst, wenn der Raum heute nicht über ein Thermostat geheizt hat (bisher unterdrückt, solange der Raum aus war und heute nicht beheizt wurde). Die Beschränkung auf die Heizperiode bleibt.
- Räume ohne Thermostat sind jetzt möglich (nur Tür-/Fenstersensoren und Personen); sie gelten automatisch als anders beheizt. Der Zeitplan ist nur noch mit Thermostaten nötig. Die Karte blendet Komfort/Absenkung für solche Räume aus.
- Bestehende Räume bleiben unverändert (Option standardmäßig aus).

## 0.3.1

- Raumgeräte werden mit `via_device_id` an das Heat-Pilot-Gerät gehängt (statt des veralteten `via_device`; Warnung in Home Assistant, entfällt ab 2027.8).

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
