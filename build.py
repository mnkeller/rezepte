"""Erzeugt die Rezeptseiten: python3 build.py [quelle] [ziel]

Standard: quelle = rezepte/, ziel = docs/ (relativ zum Ordner dieses Skripts).
Rezepte sind die *.json in quelle; slug = Dateiname ohne Endung.
Erst werden alle Rezepte geladen und alle Seiten im Speicher erzeugt. Ist ein
Rezept ungültig, bricht der Build mit Meldung ab und ziel bleibt unberührt.
Sonst werden die Seiten geschrieben, veraltete *.html in ziel entfernt und
andere Dateien in ziel in Ruhe gelassen.
"""

import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import rezeptgraph  # noqa: E402


def seiten_erzeugen(quelle):
    """Gibt {dateiname: html} zurück oder wirft RezeptFehler mit Dateinamen."""
    try:
        dateien = sorted(d for d in os.listdir(quelle) if d.endswith(".json"))
    except OSError as e:
        raise rezeptgraph.RezeptFehler(f"{quelle}: Ordner kann nicht gelesen werden: {e}") from e
    seiten = {}
    paare = []
    for datei in dateien:
        slug = datei[: -len(".json")]
        try:
            if slug == "index":
                raise rezeptgraph.RezeptFehler(
                    "Der Name 'index' ist für die Startseite reserviert, bitte Datei umbenennen.")
            rezept = rezeptgraph.laden(os.path.join(quelle, datei))
            seiten[slug + ".html"] = rezeptgraph.seite(rezept)
        except rezeptgraph.RezeptFehler as e:
            raise rezeptgraph.RezeptFehler(f"{datei}: {e}") from e
        paare.append((slug, rezept))
    seiten["index.html"] = rezeptgraph.startseite(paare)
    return seiten, len(paare)


def schreiben(ziel, seiten):
    os.makedirs(ziel, exist_ok=True)
    for name, html in seiten.items():
        with open(os.path.join(ziel, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    for name in os.listdir(ziel):
        pfad = os.path.join(ziel, name)
        if name.endswith(".html") and name not in seiten and os.path.isfile(pfad):
            os.remove(pfad)


def main(argv):
    if len(argv) > 2:
        print("Aufruf: python3 build.py [quelle] [ziel]", file=sys.stderr)
        return 2
    quelle = argv[0] if len(argv) > 0 else os.path.join(HIER, "rezepte")
    ziel = argv[1] if len(argv) > 1 else os.path.join(HIER, "docs")
    try:
        seiten, anzahl = seiten_erzeugen(quelle)
    except rezeptgraph.RezeptFehler as e:
        print(e, file=sys.stderr)
        return 1
    schreiben(ziel, seiten)
    print(f"{anzahl} Rezept(e) gebaut nach {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
