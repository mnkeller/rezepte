"""Paket 1: Datenmodell, Brownie-Referenz, Validierung (siehe rezepte/FORMAT.md)."""

import copy
import json
import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
FIXTURES = os.path.join(HIER, "fixtures")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402
from rezeptgraph import RezeptFehler  # noqa: E402

EU_ALLERGENE = [
    "Glutenhaltiges Getreide", "Krebstiere", "Eier", "Fische", "Erdnüsse",
    "Soja", "Milch", "Schalenfrüchte", "Sellerie", "Senf", "Sesam",
    "Schwefeldioxid und Sulfite", "Lupinen", "Weichtiere",
]


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def basis():
    """Kleines gültiges Rezept, wird in den Tests gezielt verändert."""
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


class Gueltig(unittest.TestCase):
    def test_basisrezept_gueltig(self):
        self.assertIsNone(rezeptgraph.validieren(basis()))

    def test_brownies_validieren(self):
        self.assertIsNone(rezeptgraph.validieren(fixture("brownies.json")))

    def test_brownies_laden(self):
        pfad = os.path.join(FIXTURES, "brownies.json")
        rezept = rezeptgraph.laden(pfad)
        self.assertEqual(rezept, fixture("brownies.json"))

    def test_aufgeteilte_zutat_gueltig(self):
        rezept = fixture("aufgeteilt.json")
        namen = [z["name"] for z in rezept["zutaten"]]
        self.assertIn("Zucker (1. Hälfte)", namen)
        self.assertIn("Zucker (2. Hälfte)", namen)
        self.assertIsNone(rezeptgraph.validieren(rezept))
        rezeptgraph.laden(os.path.join(FIXTURES, "aufgeteilt.json"))

    def test_quelle_optional(self):
        r = basis()
        del r["quelle"]
        rezeptgraph.validieren(r)
        r["quelle"] = None
        rezeptgraph.validieren(r)
        r["quelle"] = "http://example.org"
        rezeptgraph.validieren(r)

    def test_leere_listen_und_texte_erlaubt(self):
        r = basis()
        r["vorbereitung"] = []
        r["allergene"] = []
        r["zutaten"][0]["menge"] = ""
        r["zutaten"][0]["einheit"] = ""
        rezeptgraph.validieren(r)

    def test_alle_eu_allergene_erlaubt(self):
        r = basis()
        r["allergene"] = list(EU_ALLERGENE)
        rezeptgraph.validieren(r)

    def test_rezeptfehler_ist_exception(self):
        self.assertTrue(issubclass(RezeptFehler, Exception))


class BrownieReferenz(unittest.TestCase):
    """tests/fixtures/brownies.json bildet vorlage/brownies.png ab."""

    def setUp(self):
        self.r = fixture("brownies.json")
        self.zutaten = {z["id"]: z for z in self.r["zutaten"]}
        self.schritte = {s["id"]: s for s in self.r["schritte"]}

    def test_titel(self):
        self.assertIn("Brownie", self.r["titel"])

    def test_vorbereitung_zwei_zeilen_metrisch(self):
        vb = self.r["vorbereitung"]
        self.assertEqual(len(vb), 2)
        self.assertIn("20", vb[0])
        self.assertIn("170 °C", vb[1])

    def test_zutaten_reihenfolge_und_metrische_mengen(self):
        erwartet = [
            ("115", "g", "butter"),
            ("200", "g", "sugar"),
            ("2.5", "ml", "vanilla"),
            ("60", "ml", "espresso"),
            ("100", "g", "eggs"),
            ("80", "g", "flour"),
            ("80", "g", "cocoa"),
            ("1.3", "g", "soda"),
            ("1.5", "g", "salt"),
        ]
        zutaten = self.r["zutaten"]
        self.assertEqual(len(zutaten), len(erwartet))
        for z, (menge, einheit, wort) in zip(zutaten, erwartet):
            with self.subTest(zutat=z["id"]):
                self.assertEqual(z["menge"], menge)
                self.assertEqual(z["einheit"].lower(), einheit)
                self.assertIn(wort, z["name"].lower())

    def test_keine_us_einheiten(self):
        texte = list(self.r["vorbereitung"])
        texte += [" ".join((z["menge"], z["einheit"], z["name"])) for z in self.r["zutaten"]]
        texte += [s["text"] for s in self.r["schritte"]]
        for t in texte:
            for us in ("°F", " oz", "cup", "tsp", "Tbs", "-in "):
                with self.subTest(text=t, einheit=us):
                    self.assertNotIn(us, t)

    def test_schritte(self):
        s = self.r["schritte"]
        self.assertEqual([x["text"].split()[0] for x in s],
                         ["melt", "mix", "mix", "fold", "bake"])
        self.assertEqual(s[3]["text"], "fold in")
        self.assertIn("170 °C", s[4]["text"])
        self.assertIn("30", s[4]["text"])
        self.assertIn("40", s[4]["text"])

    def test_eingaenge(self):
        s = self.r["schritte"]
        ids = [x["id"] for x in s]

        def zutat(wort):
            treffer = [z["id"] for z in self.r["zutaten"] if wort in z["name"].lower()]
            self.assertEqual(len(treffer), 1, wort)
            return treffer[0]

        erwartet = [
            [zutat("butter")],
            [ids[0], zutat("sugar"), zutat("vanilla"), zutat("espresso")],
            [ids[1], zutat("eggs")],
            [ids[2], zutat("flour"), zutat("cocoa"), zutat("soda"), zutat("table salt")],
            [ids[3]],
        ]
        for schritt, eing in zip(s, erwartet):
            with self.subTest(schritt=schritt["id"]):
                self.assertEqual(sorted(schritt["eingaenge"]), sorted(eing))

    def test_allergene(self):
        self.assertEqual(sorted(self.r["allergene"]),
                         sorted(["Milch", "Eier", "Glutenhaltiges Getreide"]))


class Abgelehnt(unittest.TestCase):
    def assertAbgelehnt(self, rezept, *stichworte):
        with self.assertRaises(RezeptFehler) as ctx:
            rezeptgraph.validieren(rezept)
        meldung = str(ctx.exception)
        self.assertTrue(meldung.strip(), "Meldung ist leer")
        for wort in stichworte:
            self.assertIn(wort, meldung)
        return meldung

    # Baumregel

    def test_nicht_baum_zwischenprodukt_aufgeteilt(self):
        r = basis()
        r["zutaten"].append({"id": "ei", "menge": "1", "einheit": "", "name": "Ei"})
        r["schritte"] = [
            {"id": "ruehren", "text": "verrühren", "eingaenge": ["mehl", "milch"]},
            {"id": "teil1", "text": "mit Salz", "eingaenge": ["ruehren", "salz"]},
            {"id": "teil2", "text": "mit Ei", "eingaenge": ["ruehren", "ei"]},
            {"id": "backen", "text": "backen", "eingaenge": ["teil1", "teil2"]},
        ]
        self.assertAbgelehnt(r, "ruehren")

    def test_nicht_baum_brownies_variante(self):
        r = fixture("brownies.json")
        # Zwischenprodukt "melt" geht zusätzlich in "fold" ein.
        r["schritte"][3]["eingaenge"].append("melt")
        self.assertAbgelehnt(r, "melt")

    def test_zutat_in_zwei_schritten(self):
        r = basis()
        r["schritte"][1]["eingaenge"].append("mehl")
        self.assertAbgelehnt(r, "mehl")

    def test_zutat_zweimal_im_selben_schritt(self):
        r = basis()
        r["schritte"][0]["eingaenge"].append("mehl")
        self.assertAbgelehnt(r, "mehl")

    def test_unbenutzte_zutat(self):
        r = basis()
        r["zutaten"].append({"id": "zimt", "menge": "1", "einheit": "TL", "name": "Zimt"})
        self.assertAbgelehnt(r, "zimt")

    def test_mehrere_letzte_schritte(self):
        r = basis()
        r["zutaten"].append({"id": "zimt", "menge": "1", "einheit": "TL", "name": "Zimt"})
        r["schritte"].append({"id": "extra", "text": "rösten", "eingaenge": ["zimt"]})
        self.assertAbgelehnt(r)

    def test_zyklus(self):
        r = basis()
        r["zutaten"].append({"id": "zimt", "menge": "1", "einheit": "TL", "name": "Zimt"})
        r["schritte"] = [
            {"id": "a", "text": "a", "eingaenge": ["mehl", "b"]},
            {"id": "b", "text": "b", "eingaenge": ["milch", "a"]},
            {"id": "backen", "text": "backen", "eingaenge": ["salz", "zimt"]},
        ]
        self.assertAbgelehnt(r)

    def test_schritt_verweist_auf_sich_selbst(self):
        r = basis()
        r["schritte"][0]["eingaenge"].append("ruehren")
        self.assertAbgelehnt(r)

    # Verweise und IDs

    def test_unbekannter_eingang(self):
        r = basis()
        r["schritte"][1]["eingaenge"].append("gibtsnicht")
        self.assertAbgelehnt(r, "gibtsnicht")

    def test_doppelte_zutaten_id(self):
        r = basis()
        r["zutaten"][1]["id"] = "mehl"
        self.assertAbgelehnt(r, "mehl")

    def test_doppelte_schritt_id(self):
        r = basis()
        r["zutaten"].append({"id": "zimt", "menge": "1", "einheit": "TL", "name": "Zimt"})
        r["schritte"] = [
            {"id": "ruehren", "text": "verrühren", "eingaenge": ["mehl", "milch"]},
            {"id": "ruehren", "text": "verrühren", "eingaenge": ["zimt"]},
            {"id": "backen", "text": "backen", "eingaenge": ["ruehren", "salz"]},
        ]
        self.assertAbgelehnt(r, "ruehren")

    def test_schritt_id_gleich_zutaten_id(self):
        r = basis()
        r["schritte"][0]["id"] = "salz"
        r["schritte"][1]["eingaenge"] = ["salz"]
        self.assertAbgelehnt(r, "salz")

    # Pflichtfelder

    def test_pflichtfeld_oben_fehlt(self):
        for feld in ("titel", "portionen", "vorbereitung", "zutaten", "schritte", "allergene"):
            with self.subTest(feld=feld):
                r = basis()
                del r[feld]
                self.assertAbgelehnt(r, feld)

    def test_pflichtfeld_zutat_fehlt(self):
        for feld in ("id", "menge", "einheit", "name"):
            with self.subTest(feld=feld):
                r = basis()
                del r["zutaten"][2][feld]
                self.assertAbgelehnt(r, feld)

    def test_pflichtfeld_schritt_fehlt(self):
        for feld in ("id", "text", "eingaenge"):
            with self.subTest(feld=feld):
                r = basis()
                del r["schritte"][0][feld]
                self.assertAbgelehnt(r, feld)

    def test_leerer_titel(self):
        r = basis()
        r["titel"] = ""
        self.assertAbgelehnt(r)
        r["titel"] = "   "
        self.assertAbgelehnt(r)

    def test_leerer_zutatenname(self):
        r = basis()
        r["zutaten"][0]["name"] = ""
        self.assertAbgelehnt(r)

    def test_keine_zutaten(self):
        r = basis()
        r["zutaten"] = []
        r["schritte"] = [{"id": "backen", "text": "backen", "eingaenge": []}]
        self.assertAbgelehnt(r)

    def test_keine_schritte(self):
        r = basis()
        r["schritte"] = []
        self.assertAbgelehnt(r)

    def test_leere_eingaenge(self):
        r = basis()
        r["schritte"].insert(0, {"id": "leer", "text": "nichts", "eingaenge": []})
        self.assertAbgelehnt(r)

    def test_falsche_typen(self):
        faelle = [
            ("titel", 5),
            ("portionen", 4),
            ("vorbereitung", "Ofen vorheizen"),
            ("zutaten", {"mehl": "100 g"}),
            ("allergene", "Milch"),
        ]
        for feld, wert in faelle:
            with self.subTest(feld=feld):
                r = basis()
                r[feld] = wert
                self.assertAbgelehnt(r)

    def test_menge_als_zahl(self):
        r = basis()
        r["zutaten"][0]["menge"] = 100
        self.assertAbgelehnt(r)

    def test_quelle_kein_link(self):
        for wert in ("Omas Kochbuch", "ftp://example.org/x", ""):
            with self.subTest(quelle=wert):
                r = basis()
                r["quelle"] = wert
                self.assertAbgelehnt(r)

    # Allergene

    def test_allergen_nicht_eu_liste(self):
        r = basis()
        r["allergene"] = ["Milch", "Gluten"]
        self.assertAbgelehnt(r, "Gluten")

    def test_allergen_falsche_schreibweise(self):
        for wert in ("milch", "Ei", "Nüsse", "Sulfite"):
            with self.subTest(allergen=wert):
                r = basis()
                r["allergene"] = [wert]
                self.assertAbgelehnt(r, wert)

    def test_validieren_veraendert_rezept_nicht(self):
        r = fixture("brownies.json")
        vorher = copy.deepcopy(r)
        rezeptgraph.validieren(r)
        self.assertEqual(r, vorher)


class Laden(unittest.TestCase):
    def schreiben(self, inhalt):
        fd, pfad = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(inhalt)
        self.addCleanup(os.remove, pfad)
        return pfad

    def test_laden_gueltig(self):
        pfad = self.schreiben(json.dumps(basis(), ensure_ascii=False))
        self.assertEqual(rezeptgraph.laden(pfad), basis())

    def test_laden_utf8(self):
        r = basis()
        r["titel"] = "Möhrenkuchen für Größere"
        pfad = self.schreiben(json.dumps(r, ensure_ascii=False))
        self.assertEqual(rezeptgraph.laden(pfad)["titel"], "Möhrenkuchen für Größere")

    def test_laden_validiert(self):
        r = basis()
        r["schritte"][1]["eingaenge"].append("gibtsnicht")
        pfad = self.schreiben(json.dumps(r))
        with self.assertRaises(RezeptFehler) as ctx:
            rezeptgraph.laden(pfad)
        self.assertIn("gibtsnicht", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
