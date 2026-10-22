# PLAN: Rezept-Graph

Grundlage: `SPEC.md`. Werkzeuge: Python 3.9, nur Standardbibliothek, Tests mit `unittest` (siehe `CLAUDE.md`).
Nach jedem Paket laufen alle Tests grün und es wird lokal committet.

## Paket 1: Datenmodell, Brownie-Referenz, Validierung

Inhalt: JSON-Format festlegen und dokumentieren, Brownie-Vorlage als Referenz-JSON, Validierung beim Laden.

Abnahmekriterien:
- [ ] Format beschreibt Titel, Portionen, Quelle (optional), Vorbereitungsschritte, Zutaten in Verarbeitungsreihenfolge (Menge, Einheit, Name), Schritte mit Bezeichnung und Eingängen (Zutaten oder vorherige Schritte), Allergene. Format ist in `rezepte/FORMAT.md` beschrieben.
- [ ] `tests/fixtures/brownies.json` bildet `vorlage/brownies.png` ab (Englisch erlaubt).
- [ ] Brownie-JSON wird als gültig geladen.
- [ ] Nicht-Baum-Rezept (ein Zwischenprodukt geht in zwei Schritte ein) wird mit klarer Meldung abgelehnt.
- [ ] Ebenso abgelehnt mit klarer Meldung: Zutat in zwei Schritten, Eingang verweist auf Unbekanntes, Pflichtfeld fehlt, Allergen nicht aus der EU-Liste der 14 Hauptallergene.

## Paket 2: Layout (Zellraster)

Inhalt: Aus einem gültigen Rezept das Zellraster berechnen (Zeile, Spalte, rowspan, colspan, Inhalt), noch ohne HTML.

Abnahmekriterien:
- [ ] Fixture `tests/fixtures/brownies_cells.json` mit der erwarteten Zellstruktur der Vorlage; berechnetes Raster stimmt exakt überein.
- [ ] Spalten der Schritte: melt | mix | mix | fold in | bake.
- [ ] Leere Zellen: Zucker bis Espresso 1 Spalte × 3 Zeilen, Eier 2 Spalten × 1 Zeile, Mehl bis Salz 3 Spalten × 4 Zeilen.
- [ ] Vorbereitungsschritte als Zeilen über volle Breite oben.
- [ ] Das Raster ist lückenlos und überlappungsfrei: jede Position der Tabelle gehört zu genau einer Zelle.

## Paket 3: Rezeptseite (HTML)

Inhalt: Aus Rezept und Raster eine eigenständige HTML-Seite erzeugen.

Abnahmekriterien:
- [ ] Die HTML-Tabelle, wieder eingelesen, ergibt genau die Zellstruktur aus der Fixture (Zeile, Spalte, rowspan, colspan, Inhalt).
- [ ] Jede Zelle, auch jede leere, hat einen vollen Rahmen (`border-collapse`, Rahmen an allen `td`).
- [ ] Seite enthält Titel, Allergen-Hinweis (aus der JSON), Hinweis auf Unvollständigkeit (Spuren und Herstellerangaben nicht erfasst, keine Gewähr), Tabelle, Quelle als Link (wenn vorhanden; fehlt sie, kein leerer Quellenabschnitt).
- [ ] Mobil: Tabelle in einem horizontal scrollbaren Container, Zeilen brechen nicht um, `viewport`-Meta gesetzt.
- [ ] Seitentexte auf Deutsch.
- [ ] Review: Screenshot der Brownie-Seite sieht strukturell aus wie `vorlage/brownies.png`.

## Paket 4: Startseite und Build

Inhalt: `build.py` erzeugt aus allen Dateien in `rezepte/` die Seiten in `docs/`.

Abnahmekriterien:
- [ ] `python3 build.py` erzeugt `docs/index.html` und je Rezept `docs/<slug>.html`.
- [ ] Startseite listet alle Rezepte mit Titel und funktionierendem relativen Link.
- [ ] Ein ungültiges Rezept bricht den Build mit Meldung (Dateiname und Grund) ab, statt still übersprungen zu werden.
- [ ] Build ist deterministisch (zweimal hintereinander gleiche Ausgabe).

## Paket 5: Einlese-Ablauf in Claude Code

Inhalt: Anleitung für Claude Code (Foto → JSON → Vorschau → Bestätigung → Build) und ein Vorschau-Befehl.

Abnahmekriterien:
- [ ] `python3 preview.py rezepte/<datei>.json` validiert die Datei und erzeugt eine lokale Vorschauseite, deren Pfad ausgegeben wird; Allergene werden in der Konsole aufgelistet.
- [ ] Anleitung in `CLAUDE.md`: Foto lesen, JSON nach Format schreiben, Allergene ableiten, nach Quelle fragen falls nicht im Foto, Vorschau zeigen, erst nach Bestätigung bauen und committen.

## Paket 6: Veröffentlichung und echter Durchlauf

Inhalt: Push, GitHub Pages aus `main` / `docs`, ein echtes Rezept per Foto.

Abnahmekriterien:
- [ ] Startseite und Brownie-Seite sind unter `https://mnkeller.github.io/rezepte/` erreichbar.
- [ ] Ein echtes Rezept per Foto komplett durchgelaufen und online.

Paket 6 braucht Michi (Pages aktivieren, Foto liefern, Freigabe zum Push).

## Annahmen

- Die Brownie-Fixtures (Referenz-JSON und erwartete Zellen) schreibt der tester aus dem Bild und den Vorgaben in `SPEC.md`.
- Die Zutaten eines Teilbaums müssen direkt untereinander stehen, sonst lässt sich ein Schritt nicht über zusammenhängende Zeilen spannen. Ein solches Rezept wird ebenfalls mit Meldung abgelehnt.
- Die Allergene leitet Claude beim Einlesen ab und schreibt sie in die JSON. Das Render-Skript zeigt sie nur an.
