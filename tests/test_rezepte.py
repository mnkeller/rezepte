"""Nachbesserung Paket 5: die echten Rezepte in rezepte/ und der Stand von docs/.

- Jede rezepte/*.json lädt fehlerfrei (rezeptgraph.laden), hat einen gültigen
  Slug (FORMAT.md: ^[a-z0-9][a-z0-9-]*$, nicht "index") und ist auf Deutsch.
  Deutsch wird einfach geprüft: kein Schritttext aus {"melt", "mix",
  "fold in", "bake"} (auch nicht als Anfang des Texts), kein "Preheat" in der
  Vorbereitung, Dezimalzahlen in `menge` mit Komma statt Punkt.
- docs/ ist aktuell: build.py von rezepte/ in einen Temp-Ordner ergibt
  byteweise dieselben .html wie docs/ (gleiche Dateimenge, gleicher Inhalt).
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
REZEPTE = os.path.join(REPO, "rezepte")
DOCS = os.path.join(REPO, "docs")
BUILD = os.path.join(REPO, "build.py")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ENGLISCHE_SCHRITTE = {"melt", "mix", "fold in", "bake"}


def rezeptdateien():
    return sorted(d for d in os.listdir(REZEPTE)
                  if d.endswith(".json") and not d.startswith("."))


def roh(datei):
    with open(os.path.join(REZEPTE, datei), encoding="utf-8") as f:
        return json.load(f)


class EchteRezepte(unittest.TestCase):
    def test_es_gibt_rezepte(self):
        self.assertTrue(rezeptdateien(), "keine Rezepte in rezepte/")

    def test_gueltig(self):
        for datei in rezeptdateien():
            with self.subTest(datei=datei):
                rezeptgraph.laden(os.path.join(REZEPTE, datei))

    def test_slug(self):
        for datei in rezeptdateien():
            with self.subTest(datei=datei):
                slug = datei[: -len(".json")]
                self.assertRegex(slug, SLUG)
                self.assertNotEqual(slug, "index")

    def test_schritte_deutsch(self):
        for datei in rezeptdateien():
            for schritt in roh(datei)["schritte"]:
                text = schritt["text"].strip().lower()
                with self.subTest(datei=datei, schritt=schritt["text"]):
                    self.assertNotIn(text, ENGLISCHE_SCHRITTE)
                    for wort in ENGLISCHE_SCHRITTE:
                        self.assertFalse(re.match(re.escape(wort) + r"\b", text),
                                         f"englischer Schritttext: {schritt['text']!r}")

    def test_vorbereitung_deutsch(self):
        for datei in rezeptdateien():
            for zeile in roh(datei)["vorbereitung"]:
                with self.subTest(datei=datei, zeile=zeile):
                    self.assertNotIn("preheat", zeile.lower())

    def test_dezimalkomma(self):
        for datei in rezeptdateien():
            for zutat in roh(datei)["zutaten"]:
                with self.subTest(datei=datei, zutat=zutat["id"]):
                    self.assertNotRegex(zutat["menge"], r"\d\.\d",
                                        "Dezimalpunkt statt Komma")


class DocsAktuell(unittest.TestCase):
    def test_build_gleich_docs(self):
        tmp = tempfile.mkdtemp(prefix="rezepte-docs-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        ziel = os.path.join(tmp, "docs")
        r = subprocess.run([sys.executable, BUILD, REZEPTE, ziel], cwd=tmp,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        def html(ordner):
            inhalt = {}
            for d in sorted(os.listdir(ordner)):
                if d.endswith(".html"):
                    with open(os.path.join(ordner, d), "rb") as f:
                        inhalt[d] = f.read()
            return inhalt

        neu, alt = html(ziel), html(DOCS)
        self.assertEqual(sorted(neu), sorted(alt), "andere .html-Dateien als in docs/")
        for name in neu:
            with self.subTest(datei=name):
                self.assertTrue(neu[name] == alt[name],
                                f"docs/{name} ist nicht aktuell (python3 build.py ausführen)")


class VorlageNichtImRepo(unittest.TestCase):
    def git(self, *args):
        try:
            return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, OSError):
            self.skipTest("git nicht verfügbar")

    def test_vorlage_ignoriert_und_nicht_getrackt(self):
        if self.git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            self.skipTest("kein Git-Repo")
        with open(os.path.join(REPO, ".gitignore"), encoding="utf-8") as f:
            zeilen = [z.strip() for z in f.read().splitlines()]
        self.assertTrue({"vorlage/", "/vorlage/", "vorlage", "/vorlage"} & set(zeilen),
                        "vorlage/ fehlt in .gitignore")
        r = self.git("ls-files", "vorlage")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "", "vorlage/ ist noch im Repo")


if __name__ == "__main__":
    unittest.main()
