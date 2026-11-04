# Heat Pilot

Zentrale, raumweise Heizungssteuerung für Home Assistant. Heat Pilot entscheidet pro Raum, ob und wie warm geheizt wird, und greift dabei **nur bei Ereignissen** ein (Zeitplanwechsel, Sensoränderung, Schalter, Timer, Start von Home Assistant). Manuelle Änderungen am Thermostat bleiben bis zum nächsten Ereignis bestehen. Tür-/Fenstersensor-Ereignisse lassen den Sollwert unangetastet: Heat Pilot schaltet die Thermostate nur aus und nach dem Schließen wieder ein; der Sollwert wird nur gesetzt, wenn sich das Planziel des Raums in der Zwischenzeit geändert hat.

## Funktionen

- Zeitplangesteuerte Temperatur mit Absenkung (vorhandener `schedule`-Helfer: an = Komfort, aus = Absenkung)
- „Absenkung überspringen“ pro Raum (einmalig, endet automatisch zum nächsten Komfortbeginn)
- „Nachtabsenkung“ für Räume ohne Zeitplan: Zu einer einstellbaren Uhrzeit (Standard 22:00) wird der Raum täglich auf die Absenktemperatur gesetzt, damit ein von Hand beheizter Raum nicht die ganze Nacht durchheizt (Raumschalter, standardmäßig aus). Ein ausgeschaltetes Thermostat bleibt aus; verpasste Absenkungen werden nicht nachgeholt
- „Boost“ pro Raum: volle Heizleistung für eine einstellbare Zeit (Standard 30 Minuten), danach zurück zum Zeitplan
- Abschalten bei offener Tür oder offenem Fenster (Wartezeit einstellbar)
- Abschalten, wenn alle zugeordneten Personen länger abwesend sind
- Abwesenheitsmodus für das ganze Haus (Frostschutz) mit optionaler Rückkehrzeit
- Heizperiode (feste Daten, außerhalb bleibt alles aus; Schalter „Heizperiode pausieren“ setzt sie aus, „erzwingen“ hält sie an – die Pause hat Vorrang)
- „Heizplan heute pausieren“ pro Raum mit Zeitplan: Absenktemperatur bis Mitternacht, danach gilt der Zeitplan wieder
- Maximaltemperatur-Begrenzung pro Raum
- Nicht verfügbare Sensoren gelten als geschlossen
- Benachrichtigungen aufs Handy (Android Companion App): Türwarnung, Lüftungserinnerung, Störungsmeldungen

## Prioritäten (höchste zuerst)

1. Außerhalb der Heizperiode (auch bei Pause): Thermostate aus, auch ein Boost heizt dann nicht; von Hand eingeschaltete Thermostate werden sofort wieder ausgeschaltet
2. Abwesenheitsmodus: Frostschutztemperatur
3. Tür/Fenster länger offen als die Wartezeit: aus
4. Boost (zeitlich begrenzt, manuell gestartet): 30 °C bzw. Maximum des Thermostats, ignoriert die Maximaltemperatur-Begrenzung
5. Alle Raum-Personen länger abwesend: aus
6. Heizplan für heute pausiert: Absenktemperatur
7. Zeitplan: Komfort- oder Absenktemperatur

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

- **Türwarnung** (je Raum schaltbar): nach 5 Minuten offener Tür, dann alle 3 Minuten, maximal 3-mal, an alle zugeordneten Personen, die zu Hause sind. Nur in der Heizperiode und nicht, wenn der Raum aus ist und heute nicht beheizt wurde (außer bei Räumen, die als „anders beheizt“ gelten). Verschwindet, sobald die Tür zu ist. Mit dem Raumschalter **Türwarnung nur in der Absenkung** (standardmäßig aus) kommt die Warnung nur, solange der Zeitplan des Raums in der Absenkung ist, z. B. für eine Küche neben einem durchgehend beheizten Raum. Mit dem Raumschalter **Türwarnung nur beim Heizen** (standardmäßig aus) kommt die Warnung nur, solange der Raum auf Komforttemperatur beheizt wird, also der Zeitplan in der Komfortphase ist (oder die Absenkung übersprungen wurde) und weder Abwesenheitsmodus noch Raumabwesenheit die Heizung ändern. Das Abschalten wegen der offenen Tür selbst zählt nicht dagegen. Räume ohne Thermostat haben keine Komfortphase und werden nicht gefiltert. Beide Schalter lassen sich kombinieren.
- **Lüftungserinnerung**: einmalig, wenn ein Fenster die Heizung abgeschaltet hat und weiterhin offen ist (Standard 15 Minuten).
- **Störungsmeldungen** (nur Admin-Handy): Tür-/Fenstersensor nicht erreichbar (Standard 30 Minuten) und Thermostat, das mindestens 25 °C misst (Standard: 15 Minuten lang, nur in der Heizperiode; Hinweis auf defektes Ventil). Wiederholung alle 6 Stunden, nur zwischen 08:00 und 22:00.

Alle gesendeten Meldungen, deren Ursache noch besteht, listet die Karte oben im Abschnitt „Aktive Meldungen“ (Sensor „Aktive Meldungen“, Attribut `alerts`); der Abschnitt ist nur sichtbar, solange etwas aktiv ist, und leert sich von selbst. Ein Tipp auf die Handy-Meldung öffnet den eingestellten Dashboard-Pfad (am besten das Dashboard mit der Heat-Pilot-Karte).

## Türsensor neu anlernen (ZHA)

Fällt ein Tür-/Fenstersensor aus, zeigt die Karte in der Meldung im Abschnitt „Aktive Meldungen“ den Knopf „Anlernmodus starten“ (Dienst `heat_pilot.pair_door_sensor`). Er öffnet das ZHA-Netzwerk für 2 Minuten. Anschließend die Reset-Taste am ausgefallenen Sensor etwa 3 Sekunden halten, bis die LED blinkt. ZHA erkennt den Sensor an seiner IEEE-Adresse wieder; Entitäten und Heat-Pilot-Zuordnung bleiben bestehen. Voraussetzung: ZHA ist geladen.

## Dienst

`heat_pilot.set_heating_period` – setzt Start und Ende der Heizperiode (Monat und Tag, Standard 1.10.–30.4.).

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Geplant: Lovelace-Karte.
