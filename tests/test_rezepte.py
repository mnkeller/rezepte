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


def doc_seiten():
    return sorted(d for d in os.listdir(DOCS) if d.endswith(".html"))


def gruen(css):
    css = css.lower()
    treffer = re.findall(r"\b(?:green|lime|olive|teal|darkgreen|lightgreen|seagreen|forestgreen)\b", css)
    for h in re.findall(r"#(?:[0-9a-f]{6}|[0-9a-f]{3})\b", css):
        h = h[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        if g - max(r, b) >= 24:
            treffer.append("#" + h)
    return treffer


FAMILIE = re.compile(r'font-family\s*:\s*"Plus Jakarta Sans"\s*,[^;}]*?(?:sans-serif|system-ui)\s*[;}]')


class AlleSeitenInDocs(unittest.TestCase):
    """Paket 5f: jede Seite in docs/ (auch künftige) hat den gemeinsamen Look."""

    def test_es_gibt_seiten(self):
        self.assertIn("index.html", doc_seiten())
        self.assertGreaterEqual(len(doc_seiten()), 2)

    def lies(self, name):
        with open(os.path.join(DOCS, name), encoding="utf-8") as f:
            return f.read()

    def test_gemeinsame_merkmale(self):
        familien = set()
        for name in doc_seiten():
            html = self.lies(name)
            css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I))
            with self.subTest(seite=name):
                self.assertIn('lang="de"', html)
                self.assertRegex(html, r'<meta[^>]+name="viewport"')
                m = FAMILIE.search(css)
                self.assertIsNotNone(m, "gemeinsame Schriftfamilie fehlt")
                familien.add(re.sub(r"\s+", " ", re.search(r"font-family\s*:([^;}]*)", m.group(0)).group(1)).strip())
                self.assertRegex(css, r"(?<![-\w])color\s*:\s*#111(?:111)?\s*[;}]")
                self.assertNotIn("#1e8c2e", html.lower())
                self.assertEqual(gruen(css), [])
                self.assertNotRegex(html, r"(?i)(@import|url\(|<link[^>]+stylesheet|<script[^>]+src)")
        self.assertEqual(len(familien), 1, f"Seiten nutzen verschiedene Schriftfamilien: {familien}")

    def test_zurueck_link(self):
        for name in doc_seiten():
            html = self.lies(name)
            n = len(re.findall(r'<a\b[^>]*href="index\.html"', html))
            with self.subTest(seite=name):
                if name == "index.html":
                    self.assertEqual(n, 0, "Startseite hat keinen Zurück-Link")
                else:
                    self.assertEqual(n, 1)
                    self.assertRegex(html, r'<a\b[^>]*href="index\.html"[^>]*>\s*← Alle Rezepte\s*</a>')
                    self.assertLess(html.index('href="index.html"'), html.index("<h1"))


class ClaudeMdLook(unittest.TestCase):
    def test_abschnitt_look(self):
        with open(os.path.join(REPO, "CLAUDE.md"), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"^#+[^\n]*Look[^\n]*\n(.*?)(?=^#+ |\Z)", text, flags=re.S | re.M)
        self.assertIsNotNone(m, "kein Abschnitt mit 'Look' in der Überschrift")
        abschnitt = m.group(1)
        for stichwort in ("seite.py", "docs/"):
            self.assertIn(stichwort, abschnitt)
        self.assertRegex(abschnitt, r"Tests?\b")
        self.assertRegex(abschnitt, r"(?i)nicht von hand|nie von hand|nicht per hand|von hand.{0,20}(nicht|nie)")

    def test_look_aenderung_build_und_plan(self):
        with open(os.path.join(REPO, "CLAUDE.md"), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"^#+[^\n]*Look[^\n]*\n(.*?)(?=^#+ |\Z)", text, flags=re.S | re.M)
        self.assertIsNotNone(m)
        self.assertIn("build.py", m.group(1))
        self.assertIn("PLAN.md", m.group(1))


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
