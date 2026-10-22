"""Paket 2: Layout (Zellraster), siehe SPEC.md (LAYOUT-REGELN, TESTS) und PLAN.md."""

import copy
import json
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
FIXTURES = os.path.join(HIER, "fixtures")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402

SCHLUESSEL = {"zeile", "spalte", "rowspan", "colspan", "inhalt"}


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def zelle(zeile, spalte, rowspan, colspan, inhalt):
    return {"zeile": zeile, "spalte": spalte, "rowspan": rowspan,
            "colspan": colspan, "inhalt": inhalt}


def zutatentext(z):
    return " ".join(t for t in (z["menge"], z["einheit"], z["name"]) if t)


def basis():
    """Wie in test_validierung.py: bereits zusammenhängend."""
    return {
        "titel": "Test",
        "portionen": "2",
        "quelle": "https://example.org/rezept",
        "vorbereitung": ["Ofen auf 180 °C vorheizen"],
        "zutaten": [
            {"id": "mehl", "menge": "100", "einheit": "g", "name": "Mehl"},
            {"id": "milch", "menge": "200", "einheit": "ml", "name": "Milch"},
            {"id": "salz", "menge": "", "einheit": "", "name": "Salz"},
        ],
        "schritte": [
            {"id": "ruehren", "text": "verrühren", "eingaenge": ["mehl", "milch"]},
            {"id": "backen", "text": "backen", "eingaenge": ["ruehren", "salz"]},
        ],
        "allergene": ["Glutenhaltiges Getreide", "Milch"],
    }


def verschachtelt():
    """Zwei verschränkte Teilbäume: a1 a2 / b1 b2 abwechselnd."""
    return {
        "titel": "Verschränkt",
        "portionen": "1",
        "vorbereitung": [],
        "zutaten": [
            {"id": "a1", "menge": "1", "einheit": "", "name": "A eins"},
            {"id": "b1", "menge": "1", "einheit": "", "name": "B eins"},
            {"id": "a2", "menge": "1", "einheit": "", "name": "A zwei"},
            {"id": "b2", "menge": "1", "einheit": "", "name": "B zwei"},
            {"id": "c", "menge": "1", "einheit": "", "name": "C"},
        ],
        "schritte": [
            {"id": "sa", "text": "A mischen", "eingaenge": ["a1", "a2"]},
            {"id": "sb", "text": "B mischen", "eingaenge": ["b1", "b2"]},
            {"id": "sab", "text": "zusammen", "eingaenge": ["sa", "sb", "c"]},
        ],
        "allergene": [],
    }


def ein_ausreisser():
    """a1 a2 a3 b a4: nur a4 steht falsch. Einzige Umsortierung, die die
    Reihenfolge so weit wie möglich erhält: b ans Ende (bzw. a4 vor b)."""
    return {
        "titel": "Ausreißer",
        "portionen": "1",
        "vorbereitung": [],
        "zutaten": [
            {"id": "a1", "menge": "", "einheit": "", "name": "A1"},
            {"id": "a2", "menge": "", "einheit": "", "name": "A2"},
            {"id": "a3", "menge": "", "einheit": "", "name": "A3"},
            {"id": "b", "menge": "", "einheit": "", "name": "B"},
            {"id": "a4", "menge": "", "einheit": "", "name": "A4"},
        ],
        "schritte": [
            {"id": "sa", "text": "A", "eingaenge": ["a1", "a2", "a3", "a4"]},
            {"id": "ende", "text": "Ende", "eingaenge": ["sa", "b"]},
        ],
        "allergene": [],
    }


def spalten_der_schritte(rezept):
    """Spalte eines Schritts = höchste Spalte seiner Eingänge + 1, Zutaten in 0."""
    schritte = {s["id"]: s for s in rezept["schritte"]}
    spalte = {z["id"]: 0 for z in rezept["zutaten"]}

    def berechne(i):
        if i not in spalte:
            spalte[i] = max(berechne(e) for e in schritte[i]["eingaenge"]) + 1
        return spalte[i]

    for i in schritte:
        berechne(i)
    return spalte


def zutaten_im_teilbaum(rezept, schritt_id):
    schritte = {s["id"]: s for s in rezept["schritte"]}
    ergebnis, offen = set(), [schritt_id]
    while offen:
        i = offen.pop()
        if i in schritte:
            offen.extend(schritte[i]["eingaenge"])
        else:
            ergebnis.add(i)
    return ergebnis


class RasterPruefung(unittest.TestCase):
    """Allgemeine Eigenschaften, die für jedes gültige Rezept gelten müssen."""

    def pruefe_raster(self, rezept):
        """Prüft das Raster und gibt die Zutaten-IDs in Zeilenreihenfolge zurück."""
        zellen = rezeptgraph.layout(copy.deepcopy(rezept))
        self.assertIsInstance(zellen, list)

        for z in zellen:
            self.assertEqual(set(z), SCHLUESSEL, z)
            for k in ("zeile", "spalte", "rowspan", "colspan"):
                self.assertIsInstance(z[k], int, z)
            self.assertGreaterEqual(z["zeile"], 0, z)
            self.assertGreaterEqual(z["spalte"], 0, z)
            self.assertGreaterEqual(z["rowspan"], 1, z)
            self.assertGreaterEqual(z["colspan"], 1, z)
            self.assertIsInstance(z["inhalt"], str, z)

        positionen = [(z["zeile"], z["spalte"]) for z in zellen]
        self.assertEqual(positionen, sorted(positionen), "nicht nach (zeile, spalte) sortiert")

        spalte = spalten_der_schritte(rezept)
        letzte_ids = {s["id"] for s in rezept["schritte"]} - {
            e for s in rezept["schritte"] for e in s["eingaenge"]}
        letzter = letzte_ids.pop()
        n_spalten = spalte[letzter] + 1
        n_vb = len(rezept["vorbereitung"])
        n_zeilen = n_vb + len(rezept["zutaten"])

        # Lückenlos und überlappungsfrei
        belegt = {}
        for z in zellen:
            for r in range(z["zeile"], z["zeile"] + z["rowspan"]):
                for c in range(z["spalte"], z["spalte"] + z["colspan"]):
                    self.assertLess(r, n_zeilen, f"Zelle ragt unten hinaus: {z}")
                    self.assertLess(c, n_spalten, f"Zelle ragt rechts hinaus: {z}")
                    self.assertNotIn((r, c), belegt,
                                     f"Überlappung bei {(r, c)}: {belegt.get((r, c))} und {z}")
                    belegt[(r, c)] = z
        fehlend = [(r, c) for r in range(n_zeilen) for c in range(n_spalten)
                   if (r, c) not in belegt]
        self.assertEqual(fehlend, [], "Lücken im Raster")

        # Vorbereitung: volle Breite oben
        for i, text in enumerate(rezept["vorbereitung"]):
            self.assertEqual(belegt[(i, 0)], zelle(i, 0, 1, n_spalten, text))

        # Spalte 0: jede Zutat genau einmal, eine Zeile
        text_zu_id = {zutatentext(z): z["id"] for z in rezept["zutaten"]}
        self.assertEqual(len(text_zu_id), len(rezept["zutaten"]), "Testrezept braucht eindeutige Zutatentexte")
        reihenfolge = []
        for r in range(n_vb, n_zeilen):
            z = belegt[(r, 0)]
            self.assertEqual((z["zeile"], z["rowspan"], z["colspan"]), (r, 1, 1), z)
            self.assertIn(z["inhalt"], text_zu_id, z)
            reihenfolge.append(text_zu_id[z["inhalt"]])
        self.assertEqual(sorted(reihenfolge), sorted(text_zu_id.values()))
        zeile_von = {i: n_vb + k for k, i in enumerate(reihenfolge)}

        # Schritte: richtige Spalte, überspannen genau die Zeilen ihrer Zutaten
        schrittzellen = set()
        for s in rezept["schritte"]:
            with self.subTest(schritt=s["id"]):
                zeilen = sorted(zeile_von[i] for i in zutaten_im_teilbaum(rezept, s["id"]))
                self.assertEqual(zeilen, list(range(zeilen[0], zeilen[-1] + 1)),
                                 f"Teilbaum von {s['id']} hängt nicht zusammen: {reihenfolge}")
                erwartet = zelle(zeilen[0], spalte[s["id"]], len(zeilen), 1, s["text"])
                self.assertEqual(belegt[(zeilen[0], spalte[s["id"]])], erwartet)
                schrittzellen.add((zeilen[0], spalte[s["id"]]))

        # Alle übrigen Zellen sind leer
        for z in zellen:
            pos = (z["zeile"], z["spalte"])
            if z["zeile"] < n_vb or z["spalte"] == 0 or pos in schrittzellen:
                continue
            self.assertEqual(z["inhalt"], "", z)
        return reihenfolge


class Brownies(RasterPruefung):
    def setUp(self):
        self.rezept = fixture("brownies.json")
        self.zellen = rezeptgraph.layout(self.rezept)

    def test_raster_gleich_fixture(self):
        self.assertEqual(self.zellen, fixture("brownies_cells.json"))

    def test_schrittspalten(self):
        erste_zutatenzeile = len(self.rezept["vorbereitung"])
        kopf = sorted((z for z in self.zellen
                       if z["zeile"] == erste_zutatenzeile and z["spalte"] > 0),
                      key=lambda z: z["spalte"])
        self.assertEqual([z["inhalt"].split(" 170")[0] for z in kopf],
                         ["melt", "mix", "mix", "fold in", "bake"])
        self.assertEqual([z["spalte"] for z in kopf], [1, 2, 3, 4, 5])

    def test_leere_zellen(self):
        zeile = {z["id"]: len(self.rezept["vorbereitung"]) + i
                 for i, z in enumerate(self.rezept["zutaten"])}
        leer = sorted((z["zeile"], z["spalte"], z["rowspan"], z["colspan"])
                      for z in self.zellen if z["inhalt"] == "")
        self.assertEqual(leer, [
            (zeile["sugar"], 1, 3, 1),   # Zucker bis Espresso: 1 Spalte × 3 Zeilen
            (zeile["eggs"], 1, 1, 2),    # Eier: 2 Spalten × 1 Zeile
            (zeile["flour"], 1, 4, 3),   # Mehl bis Salz: 3 Spalten × 4 Zeilen
        ])

    def test_vorbereitung_volle_breite_oben(self):
        breite = max(z["spalte"] + z["colspan"] for z in self.zellen)
        self.assertEqual(breite, 6)
        for i, text in enumerate(self.rezept["vorbereitung"]):
            self.assertIn(zelle(i, 0, 1, breite, text), self.zellen)

    def test_lueckenlos_und_reihenfolge_unveraendert(self):
        reihenfolge = self.pruefe_raster(self.rezept)
        self.assertEqual(reihenfolge, [z["id"] for z in self.rezept["zutaten"]])

    def test_layout_veraendert_rezept_nicht(self):
        r = fixture("brownies.json")
        rezeptgraph.layout(r)
        self.assertEqual(r, fixture("brownies.json"))

    def test_zusammenhaengende_abweichende_reihenfolge_bleibt(self):
        # Salz zuerst: alle Teilbäume hängen trotzdem zusammen (Salz geht erst in
        # "fold in" ein, das alles umfasst). Also keine Umsortierung.
        r = fixture("brownies.json")
        salz = r["zutaten"].pop()
        r["zutaten"].insert(0, salz)
        reihenfolge = self.pruefe_raster(r)
        self.assertEqual(reihenfolge, [z["id"] for z in r["zutaten"]])
        zellen = rezeptgraph.layout(r)
        self.assertIn(zelle(2, 1, 1, 3, ""), zellen)


class Basis(RasterPruefung):
    def test_basis_exakt(self):
        self.assertEqual(rezeptgraph.layout(basis()), [
            zelle(0, 0, 1, 3, "Ofen auf 180 °C vorheizen"),
            zelle(1, 0, 1, 1, "100 g Mehl"),
            zelle(1, 1, 2, 1, "verrühren"),
            zelle(1, 2, 3, 1, "backen"),
            zelle(2, 0, 1, 1, "200 ml Milch"),
            zelle(3, 0, 1, 1, "Salz"),
            zelle(3, 1, 1, 1, ""),
        ])

    def test_basis_lueckenlos(self):
        self.pruefe_raster(basis())

    def test_ohne_vorbereitung_beginnt_mit_zutaten(self):
        r = basis()
        r["vorbereitung"] = []
        zellen = rezeptgraph.layout(r)
        self.assertEqual(zellen[0], zelle(0, 0, 1, 1, "100 g Mehl"))
        self.pruefe_raster(r)

    def test_nur_ein_schritt(self):
        r = basis()
        r["schritte"] = [{"id": "alles", "text": "alles verrühren",
                          "eingaenge": ["mehl", "milch", "salz"]}]
        r["vorbereitung"] = ["A", "B"]
        self.assertEqual(rezeptgraph.layout(r), [
            zelle(0, 0, 1, 2, "A"),
            zelle(1, 0, 1, 2, "B"),
            zelle(2, 0, 1, 1, "100 g Mehl"),
            zelle(2, 1, 3, 1, "alles verrühren"),
            zelle(3, 0, 1, 1, "200 ml Milch"),
            zelle(4, 0, 1, 1, "Salz"),
        ])


class AufgeteilteZutat(RasterPruefung):
    def test_lueckenlos(self):
        r = fixture("aufgeteilt.json")
        reihenfolge = self.pruefe_raster(r)
        self.assertEqual(reihenfolge, [z["id"] for z in r["zutaten"]])

    def test_exakt(self):
        # Eier und 2. Zuckerhälfte sind direkt benachbart und gehen beide erst in
        # "unterschlagen" ein: eine einzige leere Zelle.
        self.assertEqual(rezeptgraph.layout(fixture("aufgeteilt.json")), [
            zelle(0, 0, 1, 1, "100 g Butter"),
            zelle(0, 1, 2, 1, "schaumig rühren"),
            zelle(0, 2, 4, 1, "unterschlagen"),
            zelle(1, 0, 1, 1, "100 g Zucker (1. Hälfte)"),
            zelle(2, 0, 1, 1, "2 Eier"),
            zelle(2, 1, 2, 1, ""),
            zelle(3, 0, 1, 1, "100 g Zucker (2. Hälfte)"),
        ])


class Umsortieren(RasterPruefung):
    """Zutaten eines Schritts stehen in der JSON nicht direkt untereinander."""

    def test_fixture_ist_gueltig_und_nicht_zusammenhaengend(self):
        r = fixture("unzusammenhaengend.json")
        rezeptgraph.validieren(r)
        ids = [z["id"] for z in r["zutaten"]]
        pos = sorted(ids.index(i) for i in ("mehl", "salz", "zucker"))
        self.assertNotEqual(pos, list(range(pos[0], pos[0] + 3)))

    def test_fixture_wird_dargestellt(self):
        self.pruefe_raster(fixture("unzusammenhaengend.json"))

    def test_verschraenkte_teilbaeume(self):
        self.pruefe_raster(verschachtelt())

    def test_brownies_vermischt(self):
        # Eier zwischen Mehl und Kakao: Teilbaum von "mix" (2) hängt nicht zusammen.
        r = fixture("brownies.json")
        eier = r["zutaten"].pop(4)
        r["zutaten"].insert(5, eier)
        self.pruefe_raster(r)

    def test_ein_ausreisser_minimal_umsortiert(self):
        r = ein_ausreisser()
        reihenfolge = self.pruefe_raster(r)
        self.assertEqual(reihenfolge, ["a1", "a2", "a3", "a4", "b"])

    def test_rezept_bleibt_unveraendert(self):
        r = fixture("unzusammenhaengend.json")
        rezeptgraph.layout(r)
        self.assertEqual(r, fixture("unzusammenhaengend.json"))


if __name__ == "__main__":
    unittest.main()
