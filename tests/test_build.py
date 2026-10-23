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
import re
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


# --- Paket 5d: Startseite im Stil von moinsdifficile.de, Hinweis auf Cooking for Engineers

MOTTO = "Rezepte, weniger schwer"
CFE = "https://www.cookingforengineers.com/"
GRUND = ("body", "html", "html, body", "body, html")


def sichtbar(p):
    return norm(" ".join(p.texte)).replace(" ,", ",")


def regeln(css):
    """[(selektor, {eigenschaft: wert})] aus einfachem CSS (ohne Verschachtelung)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    ergebnis = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        deklarationen = {}
        for dekl in body.split(";"):
            if ":" in dekl:
                k, v = dekl.split(":", 1)
                deklarationen[k.strip().lower()] = norm(v).lower()
        ergebnis.append((norm(sel).lower(), deklarationen))
    return ergebnis


def farbe(wert):
    """'#rgb'/'#rrggbb'/black/white -> (r, g, b) oder None."""
    wert = (wert or "").strip().lower().replace("!important", "").strip()
    wert = {"black": "#000000", "white": "#ffffff"}.get(wert, wert)
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", wert)
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def dunkel(wert):
    f = farbe(wert)
    return f is not None and max(f) <= 0x44


def hell(wert):
    f = farbe(wert)
    return f is not None and min(f) >= 0xF8


def hintergrund(deklarationen):
    return deklarationen.get("background-color") or deklarationen.get("background")


class StartseitePaket5d(unittest.TestCase):
    def setUp(self):
        self.paare = [(s, fixture(n)) for s, n in REZEPTE.items()]
        self.html = rezeptgraph.startseite(self.paare)
        self.p = einlesen(self.html)
        self.css = "\n".join(self.p.css)
        self.regeln = regeln(self.css)

    # Titel und Motto

    def test_h1_enthaelt_rezepte(self):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.S | re.I)
        self.assertIsNotNone(m, "keine h1")
        self.assertIn("Rezepte", norm(re.sub(r"<[^>]+>", " ", m.group(1))))

    def _body(self):
        m = re.search(r"<body[^>]*>(.*)</body>", self.html, flags=re.S | re.I)
        self.assertIsNotNone(m, "kein body")
        return m.group(1)

    def _body_text(self):
        roh = re.sub(r"<(style|script)\b.*?</\1>", " ", self._body(), flags=re.S | re.I)
        return norm(re.sub(r"<[^>]+>", " ", roh)).replace(" ,", ",")

    def test_motto_steht_in_der_h1(self):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.S | re.I)
        self.assertIsNotNone(m, "keine h1")
        self.assertEqual(norm(re.sub(r"<[^>]+>", " ", m.group(1))), "Rezepte weniger schwer")

    def test_motto_mit_komma_nicht_im_sichtbaren_body(self):
        self.assertNotIn(MOTTO, self._body_text())

    def test_kein_motto_element_im_body(self):
        self.assertFalse([1 for t, a in self.p.elemente
                          if "motto" in (a.get("class") or "").split()])
        self.assertNotRegex(self._body(), r"class\s*=\s*[\"'][^\"']*\bmotto\b")

    def test_css_ohne_motto_klasse(self):
        self.assertNotRegex(self.css, r"\.motto\b")

    def test_untertitel(self):
        text = self._body_text()
        self.assertIn("Zutaten, Schritte und Allergene auf einen Blick.", text)
        self.assertNotIn("qr", text.lower())

    def test_motto_im_title(self):
        self.assertIn(MOTTO, norm("".join(self.p.title)).replace(" ,", ","))

    # Hinweis auf Cooking for Engineers

    def test_hinweis_text_und_link(self):
        self.assertIn("Darstellung inspiriert von Cooking for Engineers", sichtbar(self.p))
        self.assertIn((CFE, "Cooking for Engineers"), self.p.links)

    def test_hinweis_nach_der_rezeptliste(self):
        letzter = max(self.html.rfind('href="%s.html"' % s) for s in REZEPTE)
        self.assertGreater(letzter, 0)
        self.assertGreater(self.html.find("Darstellung inspiriert von"), letzter)
        self.assertGreater(self.html.find(CFE), letzter)

    def test_einziger_externer_link_mit_noopener(self):
        extern = [a for t, a in self.p.elemente
                  if t == "a" and re.match(r"^(https?:)?//", a.get("href") or "")]
        self.assertEqual([a["href"] for a in extern], [CFE])
        self.assertIn("noopener", (extern[0].get("rel") or "").lower())

    # Eigenständigkeit: Links ja, Laden nein

    def test_nichts_externes_wird_geladen(self):
        for tag, attrs in self.p.elemente:
            with self.subTest(tag=tag, attrs=attrs):
                if tag != "a":
                    for k in ("href", "src", "data", "srcset", "poster"):
                        self.assertNotRegex(attrs.get(k) or "", r"^(https?:)?//")
                self.assertNotIn("url(", (attrs.get("style") or "").lower())
        self.assertNotIn("@import", self.css.lower())
        self.assertNotIn("url(", self.css.lower())
        self.assertNotIn("@font-face", self.css.lower())
        self.assertFalse([1 for t, _ in self.p.elemente if t == "script"])

    # CSS: schwarz auf weiß

    def test_text_dunkel_auf_weissem_grund(self):
        farben = [d.get("color") for s, d in self.regeln if s in GRUND]
        grund = [hintergrund(d) for s, d in self.regeln if s in GRUND]
        self.assertTrue(any(dunkel(f) for f in farben), f"Textfarbe: {farben}")
        self.assertTrue(any(hell(g) for g in grund), f"Hintergrund: {grund}")

    def test_kein_gruen(self):
        self.assertNotIn("#1e8c2e", self.css.lower())

    def test_ueberschrift_kraeftig_und_leicht(self):
        # Tag-Struktur der Überschrift bleibt offen: geprüft werden die font-weight-Werte im CSS.
        gewichte = set()
        for _, d in self.regeln:
            w = d.get("font-weight")
            if w:
                gewichte.add({"bold": "700", "normal": "400", "lighter": "300"}.get(w, w))
        zahlen = [int(w) for w in gewichte if w.isdigit()]
        self.assertTrue(any(w >= 700 for w in zahlen), gewichte)
        self.assertTrue(any(w <= 400 for w in zahlen), gewichte)

    def test_hover_fokus_dunkel_mit_heller_schrift(self):
        treffer = [sel for sel, d in self.regeln
                   if re.search(r":(hover|focus)", sel) and dunkel(hintergrund(d)) and hell(d.get("color"))]
        self.assertTrue(treffer, "keine :hover/:focus-Regel mit dunklem Hintergrund und heller Schrift")

    def test_kein_dunkler_balken_ausser_hover_fokus(self):
        andere = [sel for sel, d in self.regeln
                  if dunkel(hintergrund(d)) and hell(d.get("color")) and not re.search(r":(hover|focus)", sel)]
        self.assertFalse(andere, f"dunkle Balken außerhalb von Hover/Fokus: {andere}")

    def test_hover_oder_fokus_fuer_links(self):
        treffer = [s for s, _ in self.regeln
                   if re.search(r"(^|[\s>+~,])(a|\.[\w-]+)?:(hover|focus)|\ba:(hover|focus)|\ba\b.*:(hover|focus)", s)]
        self.assertTrue(treffer, "keine :hover/:focus-Regel für Links")

    def test_schrift_endet_auf_systemschrift(self):
        familien = [d["font-family"] for _, d in self.regeln if "font-family" in d]
        self.assertTrue(familien, "keine font-family")
        for f in familien:
            with self.subTest(font=f):
                letzte = f.split(",")[-1].strip().strip("\"'")
                self.assertIn(letzte, ("sans-serif", "system-ui", "serif", "ui-sans-serif"))

    # Lange Wörter sprengen die Listenzeile nicht

    def _listenlink_regeln(self):
        return [d for s, d in self.regeln
                if ".rezepte" in s and re.search(r"(^|[\s>])a\b(?!:)", s) and "::after" not in s
                and ":hover" not in s and ":focus" not in s]

    def test_listenlink_bricht_lange_woerter_um(self):
        regs = self._listenlink_regeln()
        self.assertTrue(regs, "keine CSS-Regel für die Links der Rezeptliste")
        ok = any(d.get("overflow-wrap") in ("anywhere", "break-word")
                 or d.get("word-wrap") in ("break-word", "anywhere")
                 or d.get("word-break") in ("break-word", "break-all") for d in regs)
        self.assertTrue(ok, f"kein overflow-wrap: anywhere / word-break in {regs}")

    def test_pfeil_schrumpft_nicht_im_flex_link(self):
        regs = self._listenlink_regeln()
        if not any(d.get("display") in ("flex", "inline-flex") for d in regs):
            self.skipTest("Link ist kein Flex-Container")
        pfeil = [d for s, d in self.regeln if ".rezepte" in s and "::after" in s]
        self.assertTrue(pfeil, "keine ::after-Regel für den Pfeil")
        self.assertTrue(any(d.get("flex-shrink") == "0" or d.get("flex", "").split()[:2] == ["0", "0"]
                            for d in pfeil), f"Pfeil ohne flex-shrink: 0: {pfeil}")

    def test_titel_ohne_leerzeichen_70_zeichen(self):
        lang = fixture("brownies.json")
        lang["titel"] = "x" * 70
        html = rezeptgraph.startseite([("lang", lang)])
        p = einlesen(html)
        self.assertIn(("lang.html", "x" * 70), p.links)

    def test_title_ist_genau_das_motto(self):
        self.assertEqual(norm("".join(self.p.title)), MOTTO)

    # Rezeptseiten im selben Look (Paket 5f)

    def test_rezeptseite_ohne_gruen_mit_111_und_ohne_motto(self):
        html = rezeptgraph.seite(fixture("brownies.json"))
        low = html.lower()
        self.assertNotIn("#1e8c2e", low)
        self.assertNotRegex(low, r"\bgreen\b")
        css = "\n".join(einlesen(html).css)
        rs = regeln(css)
        rahmen = [d for s, d in rs if s in ("table", "td") and "#111" in
                  " ".join(v for k, v in d.items() if k.startswith("border"))]
        self.assertEqual(len(rahmen), 2, "table und td brauchen einen #111-Rahmen")
        grund = [d.get("color") for s, d in rs if s in GRUND]
        self.assertTrue(any(farbe(c) == (0x11, 0x11, 0x11) for c in grund), grund)
        self.assertNotIn("weniger schwer", html)

    def test_rezeptseite_und_startseite_teilen_schrift_und_textfarbe(self):
        rez = einlesen(rezeptgraph.seite(fixture("brownies.json")))
        fam = lambda p: {d["font-family"] for s, d in regeln("\n".join(p.css)) if s in GRUND and "font-family" in d}
        col = lambda p: {d["color"] for s, d in regeln("\n".join(p.css)) if s in GRUND and "color" in d}
        self.assertTrue(fam(self.p))
        self.assertEqual(fam(rez), fam(self.p))
        self.assertEqual(col(rez), col(self.p))
        self.assertTrue(next(iter(fam(rez))).startswith('"plus jakarta sans"'))


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


# --- Nachbesserung aus dem Review: Slugs, versteckte Dateien, Zielschutz, Schreibfehler

class SlugPruefung(BuildTest):
    """Slugs müssen ^[a-z0-9][a-z0-9-]*$ entsprechen, 'index' ist reserviert."""

    UNGUELTIG = ["Index.json", "Brownies.json", "mein rezept.json", "rührteig.json", "index.json"]

    def test_ungueltiger_slug_bricht_ab(self):
        for name in self.UNGUELTIG:
            with self.subTest(datei=name):
                shutil.rmtree(self.ziel, ignore_errors=True)
                pfad = os.path.join(self.quelle, name)
                shutil.copy(os.path.join(FIXTURES, "brownies.json"), pfad)
                try:
                    r = self.build()
                    self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                    self.assertIn(name, r.stdout + r.stderr)
                    self.assertNotIn("Traceback", r.stdout + r.stderr)
                    self.assertFalse(os.path.exists(self.ziel))
                finally:
                    os.remove(pfad)

    def test_ungueltiger_slug_laesst_bestehendes_ziel_unveraendert(self):
        for name in self.UNGUELTIG:
            with self.subTest(datei=name):
                shutil.rmtree(self.ziel, ignore_errors=True)
                self.build_ok()
                vorher = ordnerinhalt(self.ziel)
                pfad = os.path.join(self.quelle, name)
                shutil.copy(os.path.join(FIXTURES, "brownies.json"), pfad)
                try:
                    r = self.build()
                    self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                    self.assertEqual(ordnerinhalt(self.ziel), vorher)
                finally:
                    os.remove(pfad)

    def test_gueltige_slugs_werden_gebaut(self):
        for name in ["0-rezept.json", "a.json", "rezept-2.json"]:
            shutil.copy(os.path.join(FIXTURES, "brownies.json"), os.path.join(self.quelle, name))
        self.build_ok()
        for name in ["0-rezept.html", "a.html", "rezept-2.html"]:
            with self.subTest(datei=name):
                self.assertTrue(os.path.isfile(os.path.join(self.ziel, name)))


class VersteckteDateien(BuildTest):
    """Dateien, deren Name mit '.' beginnt, werden ignoriert und nicht gelesen."""

    def setUp(self):
        super().setUp()
        # AppleDouble-artiger Müll, kein gültiges UTF-8 und kein JSON
        with open(os.path.join(self.quelle, "._brownies.json"), "wb") as f:
            f.write(b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        \xff\xfe\x80")
        with open(os.path.join(self.quelle, ".json"), "wb") as f:
            f.write(b"{kaputt")

    def test_build_gelingt(self):
        self.build_ok()

    def test_keine_seite_und_kein_link_fuer_versteckte(self):
        self.build_ok()
        html_dateien = sorted(f for f in os.listdir(self.ziel) if f.endswith(".html"))
        self.assertEqual(html_dateien, sorted(["index.html"] + [s + ".html" for s in REZEPTE]))
        p = einlesen(self.lies("index.html"))
        rezeptlinks = sorted(h for h, _ in p.links if h and h.endswith(".html"))
        self.assertEqual(rezeptlinks, sorted(s + ".html" for s in REZEPTE))

    def test_unlesbare_versteckte_datei_wird_nicht_geoeffnet(self):
        pfad = os.path.join(self.quelle, "._brownies.json")
        os.chmod(pfad, 0)
        self.addCleanup(os.chmod, pfad, 0o644)
        if os.access(pfad, os.R_OK):
            self.skipTest("Datei trotz chmod 0 lesbar (z.B. als root)")
        self.build_ok()


class ZielSchutz(BuildTest):
    """Ziel = Quelle oder Elternordner der Quelle: Abbruch, nichts gelöscht."""

    def pruefe_abbruch(self, ziel, ordner):
        alt = {"alt.html": b"<p>alt</p>\n", "z-brownies.html": b"<p>handgeschrieben</p>"}
        for name, daten in alt.items():
            with open(os.path.join(ordner, name), "wb") as f:
                f.write(daten)
        vorher = ordnerinhalt(ordner)
        r = self.build(ziel=ziel)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((r.stdout + r.stderr).strip(), "keine Meldung")
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        for name, daten in alt.items():
            with open(os.path.join(ordner, name), "rb") as f:
                self.assertEqual(f.read(), daten, name)
        self.assertEqual(ordnerinhalt(ordner), vorher)

    def test_ziel_gleich_quelle(self):
        self.pruefe_abbruch(self.quelle, self.quelle)

    def test_ziel_gleich_quelle_anders_geschrieben(self):
        self.pruefe_abbruch(os.path.join(self.quelle, "..", "quelle", "."), self.quelle)

    def test_ziel_gleich_quelle_relativ(self):
        # cwd des Builds ist self.tmp
        self.pruefe_abbruch("quelle", self.quelle)

    def test_ziel_ist_elternordner(self):
        self.pruefe_abbruch(self.tmp, self.tmp)

    def test_ziel_ist_grosselternordner(self):
        tief = os.path.join(self.tmp, "a", "b")
        os.makedirs(tief)
        os.rename(self.quelle, os.path.join(tief, "quelle"))
        self.quelle = os.path.join(tief, "quelle")
        self.pruefe_abbruch(os.path.join(self.tmp, "a"), os.path.join(self.tmp, "a"))

    def test_geschwisterordner_ist_erlaubt(self):
        # Gegenprobe: ziel neben quelle (Standardfall rezepte/ -> docs/) bleibt erlaubt
        self.build_ok()


class Schreibfehler(BuildTest):
    def test_ziel_ist_datei(self):
        with open(self.ziel, "w", encoding="utf-8") as f:
            f.write("ich bin eine Datei")
        r = self.build()
        ausgabe = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, ausgabe)
        self.assertTrue(ausgabe.strip(), "keine Meldung")
        self.assertNotIn("Traceback", ausgabe)
        with open(self.ziel, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ich bin eine Datei")


if __name__ == "__main__":
    unittest.main()
