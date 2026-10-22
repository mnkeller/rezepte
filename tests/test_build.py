"""Paket 4: Startseite und Build, siehe SPEC.md (SEITEN) und PLAN.md.

Schnittstelle von build.py (für diese Tests festgelegt):

    python3 build.py [quelle] [ziel]      Standard: rezepte docs

- Rezeptdateien sind die *.json in `quelle`; slug = Dateiname ohne Endung.
  Andere Dateien (z.B. FORMAT.md) sind keine Rezepte.
- Erfolg: Exit-Code 0, `ziel/index.html` und `ziel/<slug>.html` je Rezept.
- Ungültiges Rezept: Exit-Code != 0, Meldung (stdout oder stderr) nennt
  Dateinamen und Grund; `ziel` bleibt unverändert bzw. wird nicht angelegt.
- Veraltete .html in `ziel` werden entfernt, andere Dateien bleiben.

Die Tests arbeiten nur in temporären Ordnern und rufen build.py per
subprocess auf (cwd = temporärer Ordner), damit das echte rezepte/ und
docs/ unberührt bleiben.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
FIXTURES = os.path.join(HIER, "fixtures")
BUILD = os.path.join(REPO, "build.py")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402

# slug -> Fixture. Slug-Reihenfolge weicht absichtlich von der Titel-Reihenfolge ab.
REZEPTE = {
    "z-brownies": "brownies.json",        # "Brownies"
    "pfannkuchen": "mit_quelle.json",     # "Pfannkuchen"
    "a-ruehrteig": "aufgeteilt.json",     # "Rührteig mit aufgeteiltem Zucker"
}
TITEL_SORTIERT = ["Brownies", "Pfannkuchen", "Rührteig mit aufgeteiltem Zucker"]
SLUGS_NACH_TITEL = ["z-brownies", "pfannkuchen", "a-ruehrteig"]


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def norm(text):
    return " ".join(text.split())


def schreibe_json(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


def ordnerinhalt(pfad):
    """{relativer Pfad: Bytes} aller Dateien unter pfad."""
    inhalt = {}
    for wurzel, _, dateien in os.walk(pfad):
        for d in dateien:
            voll = os.path.join(wurzel, d)
            with open(voll, "rb") as f:
                inhalt[os.path.relpath(voll, pfad)] = f.read()
    return inhalt


class Leser(HTMLParser):
    """Links (href, Text), Starttags, Texte, CSS, <title>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elemente = []
        self.links = []
        self._link = None
        self.texte = []
        self.css = []
        self.title = []
        self._in = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.elemente.append((tag, a))
        if tag == "a":
            self._link = [a.get("href"), []]
        elif tag in ("style", "script", "title"):
            self._in = tag

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], norm("".join(self._link[1]))))
            self._link = None
        elif tag == self._in:
            self._in = None

    def handle_data(self, data):
        if self._in == "style":
            self.css.append(data)
            return
        if self._in == "script":
            return
        if self._in == "title":
            self.title.append(data)
        self.texte.append(data)
        if self._link is not None:
            self._link[1].append(data)


def einlesen(html):
    p = Leser()
    p.feed(html)
    p.close()
    return p


class BuildTest(unittest.TestCase):
    """Temporärer Arbeitsordner mit quelle/ (Fixtures + FORMAT.md) und ziel/."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rezepte-build-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.quelle = os.path.join(self.tmp, "quelle")
        self.ziel = os.path.join(self.tmp, "ziel")
        os.mkdir(self.quelle)
        for slug, name in REZEPTE.items():
            shutil.copy(os.path.join(FIXTURES, name), os.path.join(self.quelle, slug + ".json"))
        shutil.copy(os.path.join(REPO, "rezepte", "FORMAT.md"), os.path.join(self.quelle, "FORMAT.md"))

    def build(self, quelle=None, ziel=None):
        return subprocess.run(
            [sys.executable, BUILD, quelle or self.quelle, ziel or self.ziel],
            cwd=self.tmp, capture_output=True, text=True, timeout=60,
        )

    def build_ok(self, quelle=None, ziel=None):
        r = self.build(quelle, ziel)
        self.assertEqual(r.returncode, 0, f"Build fehlgeschlagen:\n{r.stdout}\n{r.stderr}")
        return r

    def lies(self, name, ziel=None):
        with open(os.path.join(ziel or self.ziel, name), encoding="utf-8") as f:
            return f.read()


# --- Kriterium 1: index.html und je Rezept <slug>.html; FORMAT.md ist kein Rezept

class ErzeugtDateien(BuildTest):
    def test_index_und_je_rezept_eine_seite(self):
        self.build_ok()
        html_dateien = sorted(f for f in os.listdir(self.ziel) if f.endswith(".html"))
        self.assertEqual(html_dateien, sorted(["index.html"] + [s + ".html" for s in REZEPTE]))

    def test_format_md_ist_kein_rezept(self):
        self.build_ok()
        self.assertFalse(os.path.exists(os.path.join(self.ziel, "FORMAT.html")))
        self.assertFalse(os.path.exists(os.path.join(self.ziel, "FORMAT.md.html")))

    def test_rezeptseite_ist_seite_des_rezepts(self):
        self.build_ok()
        for slug, name in REZEPTE.items():
            with self.subTest(slug=slug):
                erwartet = rezeptgraph.seite(rezeptgraph.laden(os.path.join(FIXTURES, name)))
                self.assertEqual(self.lies(slug + ".html"), erwartet)

    def test_index_ist_startseite(self):
        self.build_ok()
        paare = [(s, rezeptgraph.laden(os.path.join(FIXTURES, n))) for s, n in REZEPTE.items()]
        self.assertEqual(self.lies("index.html"), rezeptgraph.startseite(paare))

    def test_ziel_wird_angelegt(self):
        ziel = os.path.join(self.tmp, "neu", "docs")
        self.build_ok(ziel=ziel)
        self.assertTrue(os.path.isfile(os.path.join(ziel, "index.html")))


# --- Kriterium 2: Startseite listet alle Rezepte, sortiert, Links relativ und funktionierend

class StartseiteImBuild(BuildTest):
    def setUp(self):
        super().setUp()
        self.build_ok()
        self.p = einlesen(self.lies("index.html"))
        self.rezeptlinks = [(h, t) for h, t in self.p.links if h and h.endswith(".html")]

    def test_alle_rezepte_mit_titel_und_link(self):
        erwartet = [(s + ".html", t) for s, t in zip(SLUGS_NACH_TITEL, TITEL_SORTIERT)]
        self.assertEqual(sorted(self.rezeptlinks), sorted(erwartet))

    def test_sortiert_nach_titel(self):
        self.assertEqual([t for _, t in self.rezeptlinks], TITEL_SORTIERT)

    def test_links_relativ_und_ziel_existiert(self):
        for href, _ in self.rezeptlinks:
            with self.subTest(href=href):
                self.assertNotIn("/", href)
                self.assertNotIn(":", href)
                self.assertTrue(os.path.isfile(os.path.join(self.ziel, href)))


class StartseiteDirekt(unittest.TestCase):
    """rezeptgraph.startseite(rezepte: list[tuple[str, dict]]) -> str"""

    def paare(self):
        return [(s, fixture(n)) for s, n in REZEPTE.items()]

    def test_listet_und_sortiert(self):
        p = einlesen(rezeptgraph.startseite(self.paare()))
        links = [(h, t) for h, t in p.links if h and h.endswith(".html")]
        self.assertEqual(links, [(s + ".html", t) for s, t in zip(SLUGS_NACH_TITEL, TITEL_SORTIERT)])

    def test_reihenfolge_der_eingabe_egal(self):
        a = rezeptgraph.startseite(self.paare())
        b = rezeptgraph.startseite(list(reversed(self.paare())))
        self.assertEqual(a, b)

    def test_viewport_meta(self):
        p = einlesen(rezeptgraph.startseite(self.paare()))
        vp = [a for t, a in p.elemente if t == "meta" and (a.get("name") or "").lower() == "viewport"]
        self.assertEqual(len(vp), 1)
        self.assertIn("width=device-width", (vp[0].get("content") or "").replace(" ", ""))

    def test_lang_de(self):
        p = einlesen(rezeptgraph.startseite(self.paare()))
        html_tags = [a for t, a in p.elemente if t == "html"]
        self.assertEqual(len(html_tags), 1)
        self.assertEqual((html_tags[0].get("lang") or "").lower(), "de")

    def test_hat_title(self):
        p = einlesen(rezeptgraph.startseite(self.paare()))
        self.assertTrue(norm("".join(p.title)))

    def test_eigenstaendig(self):
        html = rezeptgraph.startseite(self.paare())
        p = einlesen(html)
        for tag, attrs in p.elemente:
            with self.subTest(tag=tag, attrs=attrs):
                if tag == "script":
                    self.assertNotIn("src", attrs)
                if tag == "link":
                    rel = (attrs.get("rel") or "").lower()
                    self.assertFalse(any(r in rel for r in ("stylesheet", "preload", "preconnect", "import")),
                                     attrs)
                    self.assertNotRegex(attrs.get("href") or "", r"^(https?:)?//")
                if tag in ("img", "iframe", "object", "embed"):
                    self.assertNotRegex(attrs.get("src") or attrs.get("data") or "", r"^(https?:)?//")
                self.assertNotIn("url(", (attrs.get("style") or "").lower())
        css = "\n".join(p.css).lower()
        self.assertNotIn("@import", css)
        self.assertNotIn("url(", css)

    def test_titel_escaped(self):
        r = copy.deepcopy(fixture("mit_quelle.json"))
        r["titel"] = "Mac & Cheese <scharf>"
        html = rezeptgraph.startseite([("mac", r)])
        p = einlesen(html)
        self.assertNotIn("<scharf>", html)
        self.assertNotIn("scharf", {t for t, _ in p.elemente})
        self.assertIn(("mac.html", "Mac & Cheese <scharf>"), p.links)


# --- Kriterium 3: ungültiges Rezept bricht ab, ziel bleibt unberührt

class UngueltigesRezept(BuildTest):
    def setUp(self):
        super().setUp()
        kaputt = fixture("mit_quelle.json")
        del kaputt["titel"]
        # Name sortiert hinter die gültigen Rezepte, damit ein naiver Build
        # vorher schon Seiten geschrieben hätte.
        self.kaputt_pfad = os.path.join(self.quelle, "zz-kaputt.json")
        schreibe_json(self.kaputt_pfad, kaputt)
        with self.assertRaises(rezeptgraph.RezeptFehler) as ctx:
            rezeptgraph.laden(self.kaputt_pfad)
        self.grund = str(ctx.exception)

    def test_exit_code_und_meldung(self):
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        ausgabe = r.stdout + r.stderr
        self.assertIn("zz-kaputt.json", ausgabe)
        self.assertIn(self.grund, ausgabe)

    def test_kein_python_traceback(self):
        r = self.build()
        self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_ziel_wird_nicht_angelegt(self):
        self.build()
        self.assertFalse(os.path.exists(self.ziel))

    def test_bestehendes_ziel_bleibt_unveraendert(self):
        # Erst gültiger Build (ohne das kaputte Rezept), dann .nojekyll dazu.
        os.rename(self.kaputt_pfad, os.path.join(self.tmp, "zz-kaputt.json"))
        self.build_ok()
        with open(os.path.join(self.ziel, ".nojekyll"), "w") as f:
            f.write("")
        vorher = ordnerinhalt(self.ziel)
        # Kaputtes Rezept zurück, ein gültiges Rezept geändert und eins entfernt:
        # nichts davon darf in ziel ankommen.
        os.rename(os.path.join(self.tmp, "zz-kaputt.json"), self.kaputt_pfad)
        geaendert = fixture("brownies.json")
        geaendert["titel"] = "Brownies NEU"
        schreibe_json(os.path.join(self.quelle, "z-brownies.json"), geaendert)
        os.remove(os.path.join(self.quelle, "pfannkuchen.json"))
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(ordnerinhalt(self.ziel), vorher)

    def test_ungueltiges_json(self):
        with open(self.kaputt_pfad, "w", encoding="utf-8") as f:
            f.write('{"titel": "Halb')
        r = self.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("zz-kaputt.json", r.stdout + r.stderr)
        self.assertFalse(os.path.exists(self.ziel))


# --- Kriterium 4: deterministisch

class Deterministisch(BuildTest):
    def test_zweimal_gleiches_ziel(self):
        self.build_ok()
        erst = ordnerinhalt(self.ziel)
        self.build_ok()
        self.assertEqual(ordnerinhalt(self.ziel), erst)

    def test_zwei_ziele_byteweise_gleich(self):
        ziel2 = os.path.join(self.tmp, "ziel2")
        self.build_ok()
        self.build_ok(ziel=ziel2)
        self.assertEqual(ordnerinhalt(self.ziel), ordnerinhalt(ziel2))


# --- Kriterium 5: veraltete .html verschwinden, andere Dateien bleiben

class Aufraeumen(BuildTest):
    def test_entferntes_rezept_verschwindet(self):
        self.build_ok()
        self.assertTrue(os.path.exists(os.path.join(self.ziel, "pfannkuchen.html")))
        os.remove(os.path.join(self.quelle, "pfannkuchen.json"))
        self.build_ok()
        self.assertFalse(os.path.exists(os.path.join(self.ziel, "pfannkuchen.html")))
        p = einlesen(self.lies("index.html"))
        self.assertNotIn("pfannkuchen.html", [h for h, _ in p.links])

    def test_fremde_html_wird_entfernt(self):
        os.mkdir(self.ziel)
        with open(os.path.join(self.ziel, "alt.html"), "w", encoding="utf-8") as f:
            f.write("<p>alt</p>")
        self.build_ok()
        self.assertFalse(os.path.exists(os.path.join(self.ziel, "alt.html")))

    def test_andere_dateien_bleiben(self):
        os.mkdir(self.ziel)
        andere = {".nojekyll": b"", "CNAME": b"rezepte.example.org\n", "bild.png": b"\x89PNG"}
        for name, daten in andere.items():
            with open(os.path.join(self.ziel, name), "wb") as f:
                f.write(daten)
        self.build_ok()
        self.build_ok()
        for name, daten in andere.items():
            with self.subTest(name=name):
                with open(os.path.join(self.ziel, name), "rb") as f:
                    self.assertEqual(f.read(), daten)


if __name__ == "__main__":
    unittest.main()
