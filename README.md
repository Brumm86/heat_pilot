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

Thermostate (mindestens eines), Zeitplan, Tür- und Fenstersensoren, Personen, Wartezeit bei offener Tür/Fenster (Standard 3 min), Wartezeit bei Abwesenheit (Standard 15 min).

## Dienst

`heat_pilot.set_heating_period` – setzt Start und Ende der Heizperiode (Monat und Tag, Standard 1.10.–30.4.).

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Geplant: Benachrichtigungen (Türwarnung, Lüftungserinnerung, Störungsmeldungen) und eine Lovelace-Karte.
