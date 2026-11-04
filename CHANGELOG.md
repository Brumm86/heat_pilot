# Changelog

## 0.12.0

- Neuer globaler Schalter „Heizperiode pausieren“: Solange er an ist, gilt die Heizperiode als inaktiv – unabhängig vom Datum und von „Heizperiode erzwingen“. Alle Thermostate werden ausgeschaltet und von Hand eingeschaltete oder verstellte Thermostate sofort wieder ausgeschaltet. Auch ein Boost heizt dann nicht: Ein laufender Boost endet mit der Heizperiode, und die Karte blendet den Boost-Schalter (und die Boost-Dauer) aus, solange die Heizperiode inaktiv ist.
- Neuer Raumschalter „Heizplan heute pausieren“ (nur Räume mit Zeitplan): Der Raum wird sofort auf die Absenktemperatur gesetzt und bleibt bis 00:00 Uhr dort, Zeitplanwechsel werden ignoriert. Danach gilt der Zeitplan automatisch wieder. Abwesenheitsmodus, offene Tür/Fenster und Heizperiode haben weiter Vorrang, ein Boost steht darüber. Neuer Raumstatus „Heizplan pausiert“ (zählt wie Absenkung, z. B. für „Türwarnung nur in der Absenkung“).
- Der Button „Türsensor anlernen“ ist als Entität entfallen (die Entität wird beim Start entfernt). Stattdessen gibt es den Dienst `heat_pilot.pair_door_sensor`, und die Karte zeigt den Anlern-Knopf nur noch in der Meldung „Tür-/Fenstersensor nicht erreichbar“ im Abschnitt „Aktive Meldungen“, solange der Ausfall besteht. Der Knopf in den „Allgemeinen Einstellungen“ entfällt.
- Karte: Das Feld „Rückkehr“ erscheint nur, solange der Abwesenheitsmodus an ist.
- Karte: Alles zum Tür-/Fenstersensor (Türwarnung in drei Varianten, Abschalten bei offener Tür/Fenster) steht je Raum in einer ausklappbaren Gruppe „Tür-/Fenstersensor“ (standardmäßig eingeklappt) und nur bei Räumen mit Tür- oder Fenstersensor.
- Karte: Der Raumstatus neben dem Raumnamen (Komfort, Absenkung, Raum nicht belegt …) und die Anzeige „offen“ erscheinen nur noch als Symbole; der Text steht als Tooltip daran.
- Karte: „Plan bearbeiten“ öffnet den Dialog des Zeitplan-Helfers direkt auf dem Reiter „Einstellungen“ (dort steht der Zeitplan-Editor), nicht mehr nur die Detailansicht.

## 0.11.0

- Neue Nachtabsenkung für Räume mit Thermostat und ohne Zeitplan: Raumschalter „Nachtabsenkung“ (standardmäßig aus) und Raum-Uhrzeit „Uhrzeit der Nachtabsenkung“ (Standard 22:00). Ist der Schalter an, setzt Heat Pilot den Raum jeden Tag zu dieser Uhrzeit auf die Absenktemperatur, damit ein allein von Hand beheizter Raum nicht die ganze Nacht durchheizt. Es gelten die üblichen Vorrangregeln (Abwesenheitsmodus, offene Tür, Boost, Raumabwesenheit, Heizperiode). Ein ausgeschaltetes Thermostat bleibt aus; „Absenkung überspringen“ endet mit der Nachtabsenkung. Eine verpasste Absenkung (z. B. Neustart) wird nicht nachgeholt. Räume mit Zeitplan haben die Option nicht. Karte: Schalter und Uhrzeit (Tipp öffnet den Einstellungsdialog) im Raumabschnitt.

## 0.10.0

- Tür-/Fenstersensor-Ereignisse lassen den Sollwert jetzt unangetastet: Solange die Wartezeit läuft (auch bei einem flatternden Sensor), tut Heat Pilot nichts; die Abschaltung schaltet die Thermostate nur aus; nach dem Schließen werden sie wieder auf Heizen geschaltet und behalten ihren Sollwert (z. B. eine Handeinstellung). Nur wenn sich das Planziel des Raums zwischen Abschaltung und Wiedereinschalten geändert hat (Komfort/Absenkung, Abwesenheitsmodus, Boost-Ende), wird das neue Planziel gesetzt. Vorher wurde bei jedem Türereignis der Sollwert auf das Planziel zurückgesetzt.
- Ein laufender Boost behält seinen Sollwert (30 °C bzw. Thermostat-Maximum) jetzt auch während einer Abschaltung wegen offener Tür; die Maximaltemperatur-Begrenzung kappt ihn dabei nicht mehr.
- Unverändert: Wird ein Raum wegen offener Tür abgeschaltet, nimmt Heat Pilot ein manuelles Einschalten sofort zurück; alle anderen Ereignisse (Zeitplan, Personen, Abwesenheitsmodus, Mitternacht) setzen den Sollwert wie bisher.

## 0.9.0

- Neue Boost-Funktion für jeden Raum mit Thermostat: Der Raumschalter „Boost“ dreht die Heizung für eine einstellbare Zeit voll auf (Zahl „Boost-Dauer“ je Raum, Standard 30 Minuten, 5–240 in 5er-Schritten) und kehrt danach von selbst zum normalen Zeitplan zurück; vorzeitiges Ausschalten des Schalters beendet den Boost sofort. Die Solltemperatur ist 30 °C, begrenzt auf das Maximum des jeweiligen Thermostats. Der Schalter zeigt die Endzeit im Attribut `ends_at`, der Raumstatus lautet „Boost“. Der Boost überlebt einen Neustart von Home Assistant.
- Rangfolge: Der Boost steht unter Heizperiode, Abwesenheitsmodus und offener Tür/offenem Fenster (diese schalten weiter ab oder gehen vor; nach dem Schließen läuft der Boost bis zum Ende weiter), aber über Raumabwesenheit, Zeitplan und der Maximaltemperatur-Begrenzung.
- Karte: Pro Raum Boost-Schalter (mit „bis hh:mm“) und Einstellung der Boost-Dauer.

## 0.8.1

- Türwarnungen verschwinden zuverlässiger vom Handy: Der Befehl zum Entfernen der Meldung wird jetzt wie die Warnung selbst mit `ttl: 0` und `priority: high` gesendet (sonst kann Android ihn im Standby verzögern oder verwerfen).
- Nach einem Neustart von Home Assistant oder der Integration werden einmalig alle Tür- und Fenstermeldungen entfernt, deren Ursache nicht mehr besteht (vorher blieb eine Meldung stehen, wenn die Tür während des Neustarts geschlossen wurde). Noch zutreffende Warnungen werden wie gewohnt erneut gesendet.
- Schaltet jemand einen Heizkörper von Hand ein, während der Raum wegen einer offenen Tür oder eines offenen Fensters abgeschaltet ist, wird er sofort wieder ausgeschaltet (vorher blieb die manuelle Änderung bis zum nächsten Ereignis bestehen). Innerhalb der Wartezeit vor der Abschaltung bleibt eine manuelle Änderung unangetastet.

## 0.8.0

- Neuer Raumschalter „Türwarnung nur beim Heizen“ (standardmäßig aus): Die Türwarnung kommt dann nur, solange der Raum auf Komforttemperatur beheizt wird, d. h. der Zeitplan ist in der Komfortphase (oder „Absenkung überspringen“ ist aktiv) und weder Abwesenheitsmodus noch Raumabwesenheit greifen. Die Abschaltung wegen der offenen Tür selbst zählt nicht dagegen. Eine bereits offene Tür zählt weiter: Beginnt die Komfortphase nach mehr als 5 Minuten offener Tür, kommt die Warnung sofort. Räume ohne Thermostat werden nicht gefiltert. Lässt sich mit „Türwarnung nur in der Absenkung“ kombinieren (beide zusammen unterdrücken die Warnung immer); bestehende Räume bleiben unverändert.

## 0.7.0

- Meldungen erscheinen nicht mehr in der Mitteilungszentrale von Home Assistant; der Parameter `?heat_pilot_notifications=1` und der zugehörige Code in der Karte entfallen. Ein Tipp auf die Handy-Meldung öffnet jetzt den in den Einstellungen hinterlegten Dashboard-Pfad.
- Neuer Sensor „Aktive Meldungen“ (Anzahl; Attribut `alerts` mit Art, Raum, Titel, Text und Beginn) und neuer Abschnitt „Aktive Meldungen“ oben in der Karte. Er erscheint nur, solange mindestens eine gesendete Meldung noch zutrifft, und verschwindet von selbst, sobald die Ursache behoben ist.
- Neuer Raumschalter „Türwarnung nur in der Absenkung“ (standardmäßig aus): Die Türwarnung kommt dann nur, solange der Zeitplan des Raums in der Absenkung ist (Komfort und „Absenkung überspringen“ unterdrücken sie). Gedacht für die Küche neben dem durchgehend beheizten Kaminzimmer.

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
