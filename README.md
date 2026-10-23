# Heat Pilot

Zentrale, raumweise Heizungssteuerung für Home Assistant. Heat Pilot entscheidet pro Raum, ob und wie warm geheizt wird, und greift dabei **nur bei Ereignissen** ein (Zeitplanwechsel, Sensoränderung, Schalter, Timer, Start von Home Assistant). Manuelle Änderungen am Thermostat bleiben bis zum nächsten Ereignis bestehen.

## Funktionen

- Zeitplangesteuerte Temperatur mit Absenkung (vorhandener `schedule`-Helfer: an = Komfort, aus = Absenkung)
- „Absenkung überspringen“ pro Raum (einmalig, endet automatisch zum nächsten Komfortbeginn)
- Abschalten bei offener Tür oder offenem Fenster (Wartezeit einstellbar)
- Abschalten, wenn alle zugeordneten Personen länger abwesend sind
- Abwesenheitsmodus für das ganze Haus (Frostschutz) mit optionaler Rückkehrzeit
- Heizperiode (feste Daten, außerhalb bleibt alles aus)
- Maximaltemperatur-Begrenzung pro Raum
- Nicht verfügbare Sensoren gelten als geschlossen
- Benachrichtigungen aufs Handy (Android Companion App): Türwarnung, Lüftungserinnerung, Störungsmeldungen

## Prioritäten (höchste zuerst)

1. Außerhalb der Heizperiode: Thermostate aus
2. Abwesenheitsmodus: Frostschutztemperatur
3. Tür/Fenster länger offen als die Wartezeit: aus
4. Alle Raum-Personen länger abwesend: aus
5. Zeitplan: Komfort- oder Absenktemperatur

## Installation (HACS)

1. HACS → Benutzerdefinierte Repositories → dieses Repository als *Integration* hinzufügen
2. Heat Pilot installieren und Home Assistant neu starten
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Heat Pilot**
4. Auf der Integrationsseite über „Raum hinzufügen“ Räume anlegen

## Raum-Einstellungen

Thermostate, Zeitplan (nur mit Thermostaten nötig), Tür- und Fenstersensoren, Personen, Wartezeit bei offener Tür/Fenster (Standard 3 min), Wartezeit bei Abwesenheit (Standard 15 min).

**Raum wird anders beheizt** (z. B. Fußbodenheizung, die in Home Assistant nicht abgebildet ist): Mit dieser Option wird die Türwarnung auch ausgelöst, wenn der Raum heute nicht über ein Thermostat geheizt hat. Ein Raum ganz ohne Thermostat gilt automatisch als anders beheizt; dann reichen Name und Türsensor(en).

## Lovelace-Karte

Die Karte wird von der Integration automatisch geladen. Dashboard bearbeiten → Karte hinzufügen → „Heat Pilot“, oder per YAML:

```yaml
type: custom:heat-pilot-card
```

Die Abschnitte „Allgemeine Einstellungen“ und die einzelnen Räume sind einklappbar und standardmäßig eingeklappt (Tipp auf die Kopfzeile). Die Karte findet alle Räume selbst. „Plan bearbeiten“ öffnet den Zeitplan-Helfer des Raums (dort über das Zahnrad bearbeiten).

## Benachrichtigungen

Einstellungen → Heat Pilot → Konfigurieren: Admin-Handy, Handy je Person (feste Zuordnung), Wartezeiten und Dashboard-Pfad.

- **Türwarnung** (je Raum schaltbar): nach 5 Minuten offener Tür, dann alle 3 Minuten, maximal 3-mal, an alle zugeordneten Personen, die zu Hause sind. Nur in der Heizperiode und nicht, wenn der Raum aus ist und heute nicht beheizt wurde (außer bei Räumen, die als „anders beheizt“ gelten). Verschwindet, sobald die Tür zu ist.
- **Lüftungserinnerung**: einmalig, wenn ein Fenster die Heizung abgeschaltet hat und weiterhin offen ist (Standard 15 Minuten).
- **Störungsmeldungen** (nur Admin-Handy): Tür-/Fenstersensor nicht erreichbar (Standard 30 Minuten) und Thermostat, das mindestens 25 °C misst (Standard: 15 Minuten lang, nur in der Heizperiode; Hinweis auf defektes Ventil). Wiederholung alle 6 Stunden, nur zwischen 08:00 und 22:00.

Jede aufs Handy gesendete Meldung erscheint zusätzlich als dauerhafte Benachrichtigung in der Mitteilungszentrale von Home Assistant und verschwindet dort, sobald die Ursache behoben ist. Ein Tipp auf die Handy-Meldung öffnet die Mitteilungszentrale: Home Assistant hat dafür keine eigene URL, daher hängt Heat Pilot `?heat_pilot_notifications=1` an den Dashboard-Pfad; die automatisch geladene Kartendatei erkennt den Parameter und öffnet die Mitteilungen.

## Türsensor neu anlernen (ZHA)

Der Button „Türsensor anlernen“ (Heat-Pilot-Gerät und Karte) öffnet das ZHA-Netzwerk für 2 Minuten. Anschließend die Reset-Taste am ausgefallenen Sensor etwa 3 Sekunden halten, bis die LED blinkt. ZHA erkennt den Sensor an seiner IEEE-Adresse wieder; Entitäten und Heat-Pilot-Zuordnung bleiben bestehen. Voraussetzung: ZHA ist geladen.

## Dienst

`heat_pilot.set_heating_period` – setzt Start und Ende der Heizperiode (Monat und Tag, Standard 1.10.–30.4.).

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Geplant: Lovelace-Karte.
