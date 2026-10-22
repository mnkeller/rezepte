# PLAN: Rezept-Graph

Grundlage: `SPEC.md`. Werkzeuge: Python 3.9, nur Standardbibliothek, Tests mit `unittest` (siehe `CLAUDE.md`).
Nach jedem Paket laufen alle Tests grün und es wird lokal committet.

## Schnittstellen (damit Tests und Umsetzung zusammenpassen)

Paket `rezeptgraph/`, importierbar als `import rezeptgraph`:

- `rezeptgraph.RezeptFehler(Exception)` – alle Ablehnungen; die Meldung nennt den Grund auf Deutsch (z.B. betroffene ID).
- `rezeptgraph.laden(pfad) -> dict` – liest JSON, validiert, gibt das Rezept zurück.
- `rezeptgraph.validieren(rezept: dict) -> None` – wirft `RezeptFehler` bei Verstoß gegen `rezepte/FORMAT.md`.
- `rezeptgraph.layout(rezept: dict) -> list[dict]` – Zellen `{"zeile", "spalte", "rowspan", "colspan", "inhalt"}`, 0-basiert, Zeile 0 ist die erste Vorbereitungszeile, Spalte 0 die Zutaten. Leere Zellen haben `"inhalt": ""`. Sortiert nach (zeile, spalte).
- `rezeptgraph.seite(rezept: dict) -> str` – vollständige HTML-Rezeptseite.
- `rezeptgraph.startseite(rezepte: list[tuple[str, dict]]) -> str` – HTML-Startseite aus (slug, rezept).

## Paket 1: Datenmodell, Brownie-Referenz, Validierung

Inhalt: Brownie-Vorlage als Referenz-JSON, Validierung beim Laden. Das Format ist in `rezepte/FORMAT.md` festgelegt (von der Koordination geschrieben).

Abnahmekriterien:
- [ ] `validieren` und `laden` setzen `rezepte/FORMAT.md` um.
- [ ] `tests/fixtures/brownies.json` bildet `vorlage/brownies.png` ab (Englisch erlaubt).
- [ ] Brownie-JSON wird als gültig geladen.
- [ ] Nicht-Baum-Rezept (ein Zwischenprodukt geht in zwei Schritte ein) wird mit klarer Meldung abgelehnt.
- [ ] Ebenso abgelehnt mit klarer Meldung: Zutat in zwei Schritten, Eingang verweist auf Unbekanntes, Pflichtfeld fehlt, Allergen nicht aus der EU-Liste der 14 Hauptallergene.
- [ ] Ein Testrezept mit aufgeteilter Zutat (zwei Zutatenzeilen, siehe `FORMAT.md`) ist gültig.

## Paket 2: Layout (Zellraster)

Inhalt: Aus einem gültigen Rezept das Zellraster berechnen (Zeile, Spalte, rowspan, colspan, Inhalt), noch ohne HTML.

Abnahmekriterien:
- [ ] Fixture `tests/fixtures/brownies_cells.json` mit der erwarteten Zellstruktur der Vorlage; berechnetes Raster stimmt exakt überein.
- [ ] Spalten der Schritte: melt | mix | mix | fold in | bake.
- [ ] Leere Zellen: Zucker bis Espresso 1 Spalte × 3 Zeilen, Eier 2 Spalten × 1 Zeile, Mehl bis Salz 3 Spalten × 4 Zeilen.
- [ ] Vorbereitungsschritte als Zeilen über volle Breite oben.
- [ ] Das Raster ist lückenlos und überlappungsfrei: jede Position der Tabelle gehört zu genau einer Zelle.
- [ ] Stehen die Zutaten eines Schritts in der JSON nicht direkt untereinander, wird das Rezept trotzdem dargestellt: Die Zutatenzeilen werden so umsortiert, dass jeder Teilbaum zusammenhängt, wobei die angegebene Reihenfolge so weit wie möglich erhalten bleibt. Bereits zusammenhängende Rezepte (Brownies) bleiben unverändert.
- [ ] Ein Rezept mit aufgeteilter Zutat (zwei Teilmengen in verschiedenen Schritten) wird lückenlos dargestellt.

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

Paket 6 braucht Michi (`gh auth login`, Foto liefern, Freigabe zum Push). Pages wird danach per `gh` auf `main` / `docs` eingeschaltet.

## Entscheidungen (Stopp 1, 22.10.)

- `gh` wird installiert, Pages per `gh` aktivieren.
- Nicht zusammenhängende Zutaten werden nicht abgelehnt, sondern umsortiert (Paket 2).
- Aufgeteilte Zutaten ("Hälfte jetzt, Hälfte später") werden als zwei Zutatenzeilen erfasst. Abgelehnt wird nur, wenn ein Zwischenprodukt (Ergebnis eines Schritts) aufgeteilt wird.
- Repo bleibt im Nextcloud-Ordner.
- Rezept für den echten Durchlauf: https://biancazapatka.com/en/moist-and-simple-carrot-cake-vegan/ (Screenshot der Seite als "Foto"; Quelle = dieser Link).

## Annahmen

- Die Brownie-Fixtures (Referenz-JSON und erwartete Zellen) schreibt der tester aus dem Bild und den Vorgaben in `SPEC.md`.
- Die Allergene leitet Claude beim Einlesen ab und schreibt sie in die JSON. Das Render-Skript zeigt sie nur an.
