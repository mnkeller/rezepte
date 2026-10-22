# Rezept-Graph

Rezeptseiten im Stil von "Cooking for Engineers" aus einer JSON-Beschreibung pro Rezept, veröffentlicht über GitHub Pages. Maßgeblich ist `SPEC.md`, der Arbeitsstand steht in `PLAN.md`.

## Aufbau

- `rezepte/` – eine JSON-Datei pro Rezept (Quelle der Wahrheit)
- `rezeptgraph/` – Python-Paket: Validierung, Layout (Zellraster), HTML-Rendering
- `build.py` – erzeugt die Seiten aus `rezepte/` nach `docs/`
- `docs/` – erzeugte Seiten, von GitHub Pages ausgeliefert (nicht von Hand bearbeiten)
- `tests/` – Tests und Fixtures
- `vorlage/` – Referenzbilder (Brownie-Vorlage)

## Werkzeuge

- Python 3.9, nur Standardbibliothek. Keine weiteren Abhängigkeiten.
- Tests: `python3 -m unittest discover -s tests -v`
- Seiten bauen: `python3 build.py` (aus `rezepte/` nach `docs/`)

## Regeln

- Das Render-Skript enthält keine KI. Der einzige KI-Schritt ist das Einlesen des Fotos in eine JSON-Datei.
- Seiten auf Deutsch und metrisch.

## Rezept einlesen

Ablauf, wenn Michi ein Foto oder einen Screenshot eines Rezepts liefert:

1. Foto/Screenshot lesen (ggf. die Webseite dazu), Rezept nach `rezepte/FORMAT.md` als `rezepte/<slug>.json` schreiben (Slug-Regeln aus FORMAT.md: nur Kleinbuchstaben, Ziffern, Bindestrich; nicht `index`). Seiten auf Deutsch und metrisch: Zutaten und Schritte übersetzen, US-Maße (cups, oz, °F usw.) in g/ml bzw. °C umrechnen.
   - Titel und Portionen auf Deutsch.
   - Mengen mit Dezimalkomma ("2,5 ml", nicht "2.5 ml").
   - Stückzutaten bleiben Stück ("2 Eier", nicht in g umrechnen): menge "2", einheit "", name "Eier".
   - Zutaten in der Reihenfolge, in der sie verarbeitet werden.
   - Vorheizen und Form vorbereiten gehören nach `vorbereitung`, nicht in die Schritte.
2. Schritte als Baum: kurze Verben in den Schrittzellen (z.B. "schmelzen", "verrühren", "backen 170 °C, 30 min"). Aufgeteilte Zutaten ("Hälfte jetzt, Hälfte später") als zwei Zutatenzeilen. Zwischenprodukte dürfen nicht aufgeteilt werden – verlangt das Rezept das, Michi fragen. Warte- und Kühlzeiten sind eigene Schritte (z.B. "vollständig auskühlen lassen" vor dem Bestreichen, "kühl stellen, bis die Creme fest ist" danach) – auf die zeitliche Logik achten, nicht nur auf die Zutaten.
3. Allergene aus den Zutaten ableiten (14 EU-Hauptallergene, Schreibweise aus FORMAT.md). Im Zweifel aufnehmen und Michi darauf hinweisen.
4. Quelle: Link eintragen. Steht keiner im Foto, Michi danach fragen. Gibt es keine Quelle (z.B. Kochbuch ohne Link), das Feld `quelle` weglassen.
5. `python3 preview.py rezepte/<slug>.json` ausführen. Schlägt das fehl, JSON nach der Meldung korrigieren und erneut ausführen.
   Screenshot der Vorschau erstellen (`<tmp>` = Scratchpad/Temp-Ordner, `<pfad>` = von preview.py ausgegebener Pfad; `timeout` gibt es auf dem Mac nicht, daher `perl -e 'alarm 60; ...'`):

   ```
   perl -e 'alarm 60; exec @ARGV' "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --use-mock-keychain --user-data-dir=<tmp>/chrome --window-size=1200,900 --screenshot=<tmp>/vorschau.png file://<pfad>
   ```

   Das PNG selbst ansehen und gegen das Foto prüfen (Zutaten, Mengen, Baumstruktur), Fehler vorher beheben. Dann Michi den Screenshot (oder Pfad) und die Allergene zeigen und auf Bestätigung warten.
6. Erst nach Bestätigung: `python3 build.py`, Tests laufen lassen, committen. Push nur nach Michis Freigabe. Danach die URL nennen: `https://mnkeller.github.io/rezepte/<slug>.html`.
