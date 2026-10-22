"""Lokale Vorschau eines Rezepts: python3 preview.py <datei.json> [zielordner]

Lädt und prüft die Datei über rezeptgraph.laden und schreibt die Seite als
<slug>.html (slug = Dateiname ohne Endung, geprüft mit
rezeptgraph.slug_pruefen) in den Zielordner. Standard ist
ein Ordner "rezept-vorschau" unter tempfile.gettempdir(), also nie im Repo.
Gibt den absoluten Pfad der Seite aus und listet die Allergene.
Bei ungültiger Datei: "Dateiname: Grund" auf stderr, Exit 1, nichts geschrieben.
"""

import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import rezeptgraph  # noqa: E402


def main(argv):
    if len(argv) not in (1, 2):
        print("Aufruf: python3 preview.py <datei.json> [zielordner]", file=sys.stderr)
        return 2
    datei = argv[0]
    ziel = argv[1] if len(argv) > 1 else os.path.join(tempfile.gettempdir(), "rezept-vorschau")
    name = os.path.basename(datei)
    try:
        slug = rezeptgraph.slug_pruefen(name)
        rezept = rezeptgraph.laden(datei)
        html = rezeptgraph.seite(rezept)
    except rezeptgraph.RezeptFehler as e:
        print(f"{name}: {e}", file=sys.stderr)
        return 1
    pfad = os.path.abspath(os.path.join(ziel, slug + ".html"))
    try:
        os.makedirs(ziel, exist_ok=True)
        with open(pfad, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    except OSError as e:
        print(f"{name}: Vorschau kann nicht geschrieben werden: {e}", file=sys.stderr)
        return 1
    print(f"Vorschau: {pfad}")
    if rezept["allergene"]:
        print("Allergene: " + ", ".join(rezept["allergene"]))
    else:
        print("Allergene: keines der 14 EU-Hauptallergene erfasst")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
