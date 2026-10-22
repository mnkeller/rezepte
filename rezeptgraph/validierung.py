"""Laden und Prüfen von Rezepten nach rezepte/FORMAT.md."""

import json
from urllib.parse import urlparse

EU_ALLERGENE = (
    "Glutenhaltiges Getreide", "Krebstiere", "Eier", "Fische", "Erdnüsse",
    "Soja", "Milch", "Schalenfrüchte", "Sellerie", "Senf", "Sesam",
    "Schwefeldioxid und Sulfite", "Lupinen", "Weichtiere",
)


class RezeptFehler(Exception):
    """Ein Rezept verstößt gegen das Format; die Meldung nennt den Grund."""


def laden(pfad):
    """Liest eine Rezept-JSON, prüft sie und gibt das Rezept zurück."""
    try:
        with open(pfad, encoding="utf-8") as f:
            rezept = json.load(f)
    except OSError as e:
        raise RezeptFehler(f"Datei {pfad} kann nicht gelesen werden: {e}") from e
    except ValueError as e:
        raise RezeptFehler(f"Datei {pfad} ist kein gültiges JSON: {e}") from e
    validieren(rezept)
    return rezept


def _feld(objekt, feld, typ, ort):
    if feld not in objekt:
        raise RezeptFehler(f"Pflichtfeld '{feld}' fehlt{ort}.")
    wert = objekt[feld]
    if not isinstance(wert, typ):
        art = "Text" if typ is str else "Liste"
        raise RezeptFehler(f"Feld '{feld}'{ort} muss {art} sein, ist aber {wert!r}.")
    return wert


def _nicht_leer(wert, feld, ort):
    if not wert.strip():
        raise RezeptFehler(f"Feld '{feld}'{ort} darf nicht leer sein.")


def _liste_aus_dicts(liste, feld):
    for i, eintrag in enumerate(liste):
        if not isinstance(eintrag, dict):
            raise RezeptFehler(f"{feld}[{i}] muss ein Objekt sein, ist aber {eintrag!r}.")


def validieren(rezept):
    """Wirft RezeptFehler, wenn das Rezept gegen rezepte/FORMAT.md verstößt."""
    if not isinstance(rezept, dict):
        raise RezeptFehler("Rezept muss ein JSON-Objekt sein.")

    # Felder oben
    _nicht_leer(_feld(rezept, "titel", str, ""), "titel", "")
    _feld(rezept, "portionen", str, "")
    quelle = rezept.get("quelle")
    if quelle is not None:
        if not isinstance(quelle, str):
            raise RezeptFehler(f"Feld 'quelle' muss ein Link sein, ist aber {quelle!r}.")
        teile = urlparse(quelle.strip())
        if teile.scheme not in ("http", "https") or not teile.netloc:
            raise RezeptFehler(f"Feld 'quelle' ist kein http(s)-Link: {quelle!r}.")
    for i, text in enumerate(_feld(rezept, "vorbereitung", list, "")):
        if not isinstance(text, str):
            raise RezeptFehler(f"vorbereitung[{i}] muss Text sein, ist aber {text!r}.")
    zutaten = _feld(rezept, "zutaten", list, "")
    schritte = _feld(rezept, "schritte", list, "")
    allergene = _feld(rezept, "allergene", list, "")
    if not zutaten:
        raise RezeptFehler("Feld 'zutaten' braucht mindestens eine Zutat.")
    if not schritte:
        raise RezeptFehler("Feld 'schritte' braucht mindestens einen Schritt.")
    _liste_aus_dicts(zutaten, "zutaten")
    _liste_aus_dicts(schritte, "schritte")

    # Allergene
    for a in allergene:
        if a not in EU_ALLERGENE:
            raise RezeptFehler(
                f"Allergen {a!r} gehört nicht zu den 14 EU-Hauptallergenen "
                f"(erlaubt: {', '.join(EU_ALLERGENE)}).")

    # Zutaten und Schritte, IDs eindeutig
    ids = set()

    def neue_id(objekt, ort):
        i = _feld(objekt, "id", str, ort)
        _nicht_leer(i, "id", ort)
        if i in ids:
            raise RezeptFehler(f"ID '{i}' ist mehrfach vergeben{ort}.")
        ids.add(i)
        return i

    zutat_ids = []
    for n, z in enumerate(zutaten):
        ort = f" in zutaten[{n}]"
        zutat_ids.append(neue_id(z, ort))
        ort = f" in Zutat '{z['id']}'"
        _feld(z, "menge", str, ort)
        _feld(z, "einheit", str, ort)
        _nicht_leer(_feld(z, "name", str, ort), "name", ort)

    schritt_ids = []
    for n, s in enumerate(schritte):
        schritt_ids.append(neue_id(s, f" in schritte[{n}]"))
        ort = f" in Schritt '{s['id']}'"
        _nicht_leer(_feld(s, "text", str, ort), "text", ort)
        eingaenge = _feld(s, "eingaenge", list, ort)
        if not eingaenge:
            raise RezeptFehler(f"Schritt '{s['id']}' hat keine Eingänge.")

    # Verweise und Baumregel
    verwendet_in = {}
    for s in schritte:
        for e in s["eingaenge"]:
            if not isinstance(e, str) or e not in ids:
                raise RezeptFehler(f"Schritt '{s['id']}' verweist auf unbekannten Eingang {e!r}.")
            if e == s["id"]:
                raise RezeptFehler(f"Schritt '{e}' verweist auf sich selbst.")
            verwendet_in.setdefault(e, []).append(s["id"])

    for e, ziele in verwendet_in.items():
        if len(ziele) > 1:
            art = "Zutat" if e in zutat_ids else "Zwischenprodukt (Schritt)"
            raise RezeptFehler(
                f"{art} '{e}' geht mehrfach ein (in {', '.join(repr(z) for z in ziele)}). "
                "Das Rezept ist kein Baum; jede Zutat und jeder Schritt darf nur einmal "
                "eingehen. Aufgeteilte Zutaten als getrennte Zutatenzeilen erfassen.")

    for z in zutat_ids:
        if z not in verwendet_in:
            raise RezeptFehler(f"Zutat '{z}' wird in keinem Schritt verwendet.")

    letzte = [s for s in schritt_ids if s not in verwendet_in]
    if len(letzte) != 1:
        if letzte:
            text = f"mehrere letzte Schritte: {', '.join(repr(s) for s in letzte)}"
        else:
            text = "keinen letzten Schritt (Zyklus)"
        raise RezeptFehler(f"Das Rezept braucht genau einen letzten Schritt, hat aber {text}.")

    eingaenge_von = {s["id"]: s["eingaenge"] for s in schritte}
    erreicht = set()
    offen = [letzte[0]]
    while offen:
        knoten = offen.pop()
        if knoten in erreicht:
            continue
        erreicht.add(knoten)
        offen.extend(eingaenge_von.get(knoten, []))
    fehlend = [i for i in zutat_ids + schritt_ids if i not in erreicht]
    if fehlend:
        raise RezeptFehler(
            f"Vom letzten Schritt '{letzte[0]}' aus nicht erreichbar (Zyklus): "
            f"{', '.join(repr(i) for i in fehlend)}.")
