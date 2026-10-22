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
