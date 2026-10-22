"""Paket 5: Einlese-Ablauf in Claude Code, siehe SPEC.md (ABLAUF, Quelle) und PLAN.md.

Schnittstelle von preview.py (für diese Tests festgelegt):

    python3 preview.py <datei.json> [zielordner]

- Gültige Datei: Exit-Code 0, genau eine Vorschauseite (.html) im Zielordner,
  Inhalt = rezeptgraph.seite(rezeptgraph.laden(datei)). Der absolute Pfad der
  Seite steht in der Ausgabe. Die Allergene werden in der Konsole aufgelistet,
  bei leerer Liste ein deutlicher Hinweis.
- Ohne zielordner: ein Ordner unter tempfile.gettempdir(), nicht im Repo,
  nicht in docs/.
- Ungültige Datei: Exit-Code != 0, Meldung nennt Dateinamen und Grund,
  kein Traceback, keine Vorschau geschrieben.
- Dateiname muss den Slug-Regeln aus rezepte/FORMAT.md entsprechen
  (^[a-z0-9][a-z0-9-]*$ vor ".json", nicht "index"), sonst wie ungültige Datei.
  Fixtures mit anderem Namen (z.B. mit_quelle.json) werden deshalb vorher
  unter einem gültigen Slug in den Temp-Ordner kopiert.

preview.py wird per subprocess aufgerufen (cwd = temporärer Ordner).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
FIXTURES = os.path.join(HIER, "fixtures")
PREVIEW = os.path.join(REPO, "preview.py")
CLAUDE_MD = os.path.join(REPO, "CLAUDE.md")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def schreibe_json(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


def ordnerinhalt(pfad):
    """{relativer Pfad: Bytes} aller Dateien unter pfad (ohne __pycache__)."""
    inhalt = {}
    for wurzel, ordner, dateien in os.walk(pfad):
        ordner[:] = [o for o in ordner if o not in ("__pycache__", ".git")]
        for d in dateien:
            voll = os.path.join(wurzel, d)
            with open(voll, "rb") as f:
                inhalt[os.path.relpath(voll, pfad)] = f.read()
    return inhalt


def html_pfade(ausgabe):
    """Alle in der Ausgabe genannten absoluten Pfade auf .html-Dateien, die existieren."""
    treffer = []
    for kandidat in re.findall(r"(/[^\s'\"]*?\.html)", ausgabe):
        if os.path.isfile(kandidat) and kandidat not in treffer:
            treffer.append(kandidat)
    return treffer


def unter(pfad, ordner):
    pfad = os.path.realpath(pfad)
    ordner = os.path.realpath(ordner)
    return os.path.commonpath([pfad, ordner]) == ordner


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rezepte-preview-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ziel = os.path.join(self.tmp, "vorschau")

    def preview(self, datei, ziel=None):
        args = [sys.executable, PREVIEW, datei]
        if ziel is not None:
            args.append(ziel)
        return subprocess.run(args, cwd=self.tmp, capture_output=True, text=True, timeout=60)

    def preview_ok(self, datei, ziel=None):
        r = self.preview(datei, ziel)
        self.assertEqual(r.returncode, 0, f"preview fehlgeschlagen:\n{r.stdout}\n{r.stderr}")
        return r

    def kopie(self, name):
        """Fixture unter gültigem Slug (Unterstrich -> Bindestrich) in den Temp-Ordner kopieren."""
        ziel = os.path.join(self.tmp, name.replace("_", "-"))
        shutil.copy(os.path.join(FIXTURES, name), ziel)
        return ziel

    def aufraeumen(self, pfad):
        """Vorschau aus der Standardvariante wieder entfernen."""
        if not unter(pfad, tempfile.gettempdir()):
            return
        try:
            os.remove(pfad)
        except OSError:
            pass
        ordner = os.path.dirname(pfad)
        if os.path.realpath(ordner) != os.path.realpath(tempfile.gettempdir()):
            try:
                os.rmdir(ordner)
            except OSError:
                pass


# --- Kriterium 1: validiert, erzeugt Vorschau = seite(), Pfad ausgegeben, Allergene gelistet

class GueltigeDatei(PreviewTest):
    def test_exit_0_und_vorschau_gleich_seite(self):
        for name in ["brownies.json", "mit_quelle.json", "aufgeteilt.json"]:
            with self.subTest(datei=name):
                ziel = os.path.join(self.tmp, name + "-ziel")
                datei = self.kopie(name)
                r = self.preview_ok(datei, ziel)
                html = [f for f in os.listdir(ziel) if f.endswith(".html")]
                self.assertEqual(len(html), 1, os.listdir(ziel))
                with open(os.path.join(ziel, html[0]), encoding="utf-8") as f:
                    inhalt = f.read()
                self.assertEqual(inhalt, rezeptgraph.seite(rezeptgraph.laden(datei)))

    def test_pfad_wird_ausgegeben(self):
        r = self.preview_ok(os.path.join(FIXTURES, "brownies.json"), self.ziel)
        pfade = html_pfade(r.stdout + r.stderr)
        self.assertEqual(len(pfade), 1, r.stdout + r.stderr)
        self.assertTrue(os.path.isabs(pfade[0]))
        self.assertTrue(unter(pfade[0], self.ziel), pfade[0])

    def test_allergene_in_der_konsole(self):
        for name in ["brownies.json", "mit_quelle.json"]:
            with self.subTest(datei=name):
                r = self.preview_ok(self.kopie(name), self.ziel)
                ausgabe = r.stdout + r.stderr
                self.assertIn("Allergen", ausgabe)
                for allergen in fixture(name)["allergene"]:
                    self.assertIn(allergen, ausgabe)

    def test_leere_allergenliste_deutlicher_hinweis(self):
        rezept = fixture("mit_quelle.json")
        rezept["allergene"] = []
        datei = os.path.join(self.tmp, "ohne-allergene.json")
        schreibe_json(datei, rezept)
        r = self.preview_ok(datei, self.ziel)
        ausgabe = r.stdout + r.stderr
        self.assertIn("Allergen", ausgabe)
        # Deutlicher Hinweis: das Wort "kein"/"keine" in einer Zeile mit "Allergen"
        zeilen = [z for z in ausgabe.splitlines() if "allergen" in z.lower()]
        self.assertTrue(any(re.search(r"\bkein", z.lower()) for z in zeilen), ausgabe)
        # Keines der Allergene aus der Fixture taucht als Liste auf
        for allergen in fixture("mit_quelle.json")["allergene"]:
            self.assertNotIn(allergen, ausgabe)

    def test_relativer_dateipfad(self):
        shutil.copy(os.path.join(FIXTURES, "brownies.json"), os.path.join(self.tmp, "brownies.json"))
        self.preview_ok("brownies.json", self.ziel)
        html = [f for f in os.listdir(self.ziel) if f.endswith(".html")]
        self.assertEqual(len(html), 1)


# --- Kriterium 2: ungültige Datei

class UngueltigeDatei(PreviewTest):
    def pruefe_abbruch(self, datei, grund=None):
        r = self.preview(datei, self.ziel)
        ausgabe = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, ausgabe)
        self.assertIn(os.path.basename(datei), ausgabe)
        if grund is not None:
            self.assertIn(grund, ausgabe)
        self.assertNotIn("Traceback", ausgabe)
        if os.path.exists(self.ziel):
            self.assertEqual([f for f in os.listdir(self.ziel) if f.endswith(".html")], [])
        self.assertEqual(html_pfade(ausgabe), [])

    def test_pflichtfeld_fehlt(self):
        kaputt = fixture("mit_quelle.json")
        del kaputt["titel"]
        datei = os.path.join(self.tmp, "kaputt.json")
        schreibe_json(datei, kaputt)
        with self.assertRaises(rezeptgraph.RezeptFehler) as ctx:
            rezeptgraph.laden(datei)
        self.pruefe_abbruch(datei, str(ctx.exception))

    def test_unbekanntes_allergen(self):
        kaputt = fixture("brownies.json")
        kaputt["allergene"] = ["Milch", "Nüsse allgemein"]
        datei = os.path.join(self.tmp, "falsches-allergen.json")
        schreibe_json(datei, kaputt)
        with self.assertRaises(rezeptgraph.RezeptFehler) as ctx:
            rezeptgraph.laden(datei)
        self.pruefe_abbruch(datei, str(ctx.exception))

    def test_ungueltiges_json(self):
        datei = os.path.join(self.tmp, "halb.json")
        with open(datei, "w", encoding="utf-8") as f:
            f.write('{"titel": "Halb')
        self.pruefe_abbruch(datei)

    def test_datei_fehlt(self):
        self.pruefe_abbruch(os.path.join(self.tmp, "gibtsnicht.json"))

    def test_ungueltiger_slug(self):
        # Inhalt gültig, nur der Dateiname verstößt gegen die Slug-Regeln aus FORMAT.md.
        # Je Fall ein eigener Ordner (macOS: Index.json/index.json kollidieren sonst).
        for i, name in enumerate(["Karotten Kuchen.json", "Index.json", "index.json"]):
            with self.subTest(datei=name):
                ordner = os.path.join(self.tmp, f"fall{i}")
                os.makedirs(ordner)
                self.ziel = os.path.join(ordner, "vorschau")
                datei = os.path.join(ordner, name)
                shutil.copy(os.path.join(FIXTURES, "brownies.json"), datei)
                self.pruefe_abbruch(datei)
                self.assertFalse(
                    any(f.endswith(".html") for f in os.listdir(ordner)), os.listdir(ordner))


# --- Kriterium 3: Vorschau in temporärem Ordner, nicht im Repo, nicht in docs/

class Zielordner(PreviewTest):
    def test_mit_zielordner(self):
        datei = os.path.join(FIXTURES, "brownies.json")
        r = self.preview_ok(datei, self.ziel)
        pfade = html_pfade(r.stdout + r.stderr)
        self.assertEqual(len(pfade), 1, r.stdout + r.stderr)
        self.assertTrue(unter(pfade[0], self.ziel))
        with open(pfade[0], encoding="utf-8") as f:
            self.assertEqual(f.read(), rezeptgraph.seite(rezeptgraph.laden(datei)))

    def test_zielordner_wird_angelegt(self):
        ziel = os.path.join(self.tmp, "a", "b")
        self.preview_ok(os.path.join(FIXTURES, "brownies.json"), ziel)
        self.assertEqual(len([f for f in os.listdir(ziel) if f.endswith(".html")]), 1)

    def test_standard_unter_tempdir_nicht_im_repo(self):
        datei = os.path.join(FIXTURES, "brownies.json")
        repo_vorher = ordnerinhalt(REPO)
        r = self.preview_ok(datei)
        pfade = html_pfade(r.stdout + r.stderr)
        self.assertEqual(len(pfade), 1, r.stdout + r.stderr)
        pfad = pfade[0]
        self.addCleanup(self.aufraeumen, pfad)
        self.assertTrue(os.path.isfile(pfad))
        self.assertTrue(unter(pfad, tempfile.gettempdir()), pfad)
        self.assertFalse(unter(pfad, REPO), pfad)
        self.assertFalse(unter(pfad, os.path.join(REPO, "docs")), pfad)
        with open(pfad, encoding="utf-8") as f:
            self.assertEqual(f.read(), rezeptgraph.seite(rezeptgraph.laden(datei)))
        self.assertEqual(ordnerinhalt(REPO), repo_vorher, "Repo wurde verändert")

    def test_mit_zielordner_repo_unveraendert(self):
        repo_vorher = ordnerinhalt(REPO)
        self.preview_ok(os.path.join(FIXTURES, "brownies.json"), self.ziel)
        self.assertEqual(ordnerinhalt(REPO), repo_vorher, "Repo wurde verändert")


# --- Kriterium 4: Anleitung in CLAUDE.md, Abschnitt "Rezept einlesen"

class Anleitung(unittest.TestCase):
    STICHWORTE = ["FORMAT.md", "preview.py", "build.py", "Quelle", "Allergene", "Bestätigung",
                  "Dezimalkomma", "vorbereitung", "Screenshot"]

    def abschnitt(self):
        with open(CLAUDE_MD, encoding="utf-8") as f:
            zeilen = f.read().splitlines()
        for i, zeile in enumerate(zeilen):
            m = re.match(r"^(#+)\s*Rezept einlesen\s*$", zeile)
            if m:
                ebene = len(m.group(1))
                inhalt = []
                for z in zeilen[i + 1:]:
                    n = re.match(r"^(#+)\s", z)
                    if n and len(n.group(1)) <= ebene:
                        break
                    inhalt.append(z)
                return "\n".join(inhalt)
        return None

    def test_abschnitt_existiert(self):
        self.assertIsNotNone(self.abschnitt(), 'Kein Abschnitt "Rezept einlesen" in CLAUDE.md')

    def test_stichworte(self):
        text = self.abschnitt()
        self.assertIsNotNone(text, 'Kein Abschnitt "Rezept einlesen" in CLAUDE.md')
        for wort in self.STICHWORTE:
            with self.subTest(stichwort=wort):
                self.assertIn(wort, text)


if __name__ == "__main__":
    unittest.main()
