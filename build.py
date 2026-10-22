"""Erzeugt die Rezeptseiten: python3 build.py [quelle] [ziel]

Standard: quelle = rezepte/, ziel = docs/ (relativ zum Ordner dieses Skripts).
Rezepte sind die *.json in quelle (ohne Dateien, die mit '.' beginnen);
slug = Dateiname ohne Endung, erlaubt ist nur [a-z0-9][a-z0-9-]*, nicht 'index'.
ziel darf weder quelle noch ein Elternordner von quelle sein.
Erst werden alle Rezepte geladen und alle Seiten im Speicher erzeugt. Ist ein
Rezept ungültig, bricht der Build mit Meldung ab und ziel bleibt unberührt.
Sonst werden die Seiten geschrieben, veraltete *.html in ziel entfernt und
andere Dateien in ziel in Ruhe gelassen.
"""

import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import rezeptgraph  # noqa: E402

SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


def seiten_erzeugen(quelle):
    """Gibt {dateiname: html} zurück oder wirft RezeptFehler mit Dateinamen."""
    try:
        dateien = sorted(d for d in os.listdir(quelle)
                         if d.endswith(".json") and not d.startswith("."))
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
            if not SLUG.fullmatch(slug):
                raise rezeptgraph.RezeptFehler(
                    "Ungültiger Dateiname, erlaubt sind nur Kleinbuchstaben, Ziffern und "
                    "Bindestrich (z.B. karottenkuchen.json), keine Umlaute oder Leerzeichen.")
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
    q_echt, z_echt = os.path.realpath(quelle), os.path.realpath(ziel)
    if os.path.commonpath([q_echt, z_echt]) == z_echt:
        print(f"{ziel}: Ziel darf nicht die Quelle oder ein Elternordner der Quelle sein.",
              file=sys.stderr)
        return 1
    if os.path.exists(ziel) and not os.path.isdir(ziel):
        print(f"{ziel}: Ziel ist kein Ordner.", file=sys.stderr)
        return 1
    try:
        seiten, anzahl = seiten_erzeugen(quelle)
    except rezeptgraph.RezeptFehler as e:
        print(e, file=sys.stderr)
        return 1
    try:
        schreiben(ziel, seiten)
    except OSError as e:
        print(f"{ziel}: Schreiben fehlgeschlagen: {e}", file=sys.stderr)
        return 1
    print(f"{anzahl} Rezept(e) gebaut nach {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
