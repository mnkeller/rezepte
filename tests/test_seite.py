"""Paket 3: Rezeptseite (HTML), siehe SPEC.md (SEITEN, LAYOUT-REGELN) und PLAN.md.

Die Seite wird mit html.parser wieder eingelesen; geprüft wird das Ergebnis
(Tabellenstruktur, Texte, CSS in der Seite), nicht die Umsetzung.
"""

import copy
import json
import os
import re
import sys
import unittest
from html.parser import HTMLParser

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
FIXTURES = os.path.join(HIER, "fixtures")
sys.path.insert(0, REPO)

import rezeptgraph  # noqa: E402

ZELL_TAGS = ("td", "th")
LEERE_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
              "link", "meta", "source", "track", "wbr"}


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def norm(text):
    return " ".join(text.split())


def sonderzeichen():
    """Testrezept mit <, > und & in Titel, Zutaten, Schritten und Quelle."""
    return {
        "titel": "Mac & Cheese <scharf>",
        "portionen": "2",
        "quelle": "https://example.org/r?a=1&b=<2>",
        "vorbereitung": ["Ofen auf 200 °C & Form <fetten>"],
        "zutaten": [
            {"id": "nudeln", "menge": "250", "einheit": "g", "name": "Nudeln <kurz>"},
            {"id": "kaese", "menge": "100", "einheit": "g", "name": "<b>Käse</b> & Co"},
        ],
        "schritte": [
            {"id": "mischen", "text": "mischen & <backen>", "eingaenge": ["nudeln", "kaese"]},
        ],
        "allergene": ["Milch", "Glutenhaltiges Getreide"],
    }


class Seitenleser(HTMLParser):
    """Liest die Seite ein: Tabellenzellen, Texte, CSS, Links, Meta."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stapel = []          # offene Elemente: (tag, attrs)
        self.elemente = []        # alle Starttags: (tag, attrs, vorfahren)
        self.tabellen = 0
        self.zeilen = []          # Liste von Zeilen, je Liste von Zellen
        self.zelle = None
        self.in_tabelle = 0
        self.css = []
        self.in_style = False
        self.in_script = False
        self.text_ausserhalb = []
        self.title = []
        self.in_title = False
        self.h1 = []
        self.in_h1 = 0
        self.tabellen_vorfahren = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elemente.append((tag, attrs, list(self.stapel)))
        if tag == "table":
            self.tabellen += 1
            self.in_tabelle += 1
            self.tabellen_vorfahren = list(self.stapel)
        elif tag == "tr" and self.in_tabelle:
            self.zeilen.append([])
        elif tag in ZELL_TAGS and self.in_tabelle:
            self.zelle = {"tag": tag, "attrs": attrs,
                          "rowspan": int(attrs.get("rowspan") or 1),
                          "colspan": int(attrs.get("colspan") or 1),
                          "text": []}
            self.zeilen[-1].append(self.zelle)
        elif tag == "style":
            self.in_style = True
        elif tag == "script":
            self.in_script = True
        elif tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 += 1
        if tag not in LEERE_TAGS:
            self.stapel.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_tabelle -= 1
        elif tag in ZELL_TAGS:
            self.zelle = None
        elif tag == "style":
            self.in_style = False
        elif tag == "script":
            self.in_script = False
        elif tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 -= 1
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i][0] == tag:
                del self.stapel[i:]
                break

    def handle_data(self, data):
        if self.in_style:
            self.css.append(data)
            return
        if self.in_script:
            return
        if self.in_title:
            self.title.append(data)
            return
        if self.in_h1:
            self.h1.append(data)
        if self.zelle is not None:
            self.zelle["text"].append(data)
        elif not self.in_tabelle:
            self.text_ausserhalb.append(data)


def einlesen(html):
    p = Seitenleser()
    p.feed(html)
    p.close()
    return p


def zellen_aus_tabelle(zeilen):
    """Rekonstruiert (zeile, spalte) nach dem HTML-Tabellenmodell."""
    belegt = set()
    ergebnis = []
    for r, zeile in enumerate(zeilen):
        c = 0
        for z in zeile:
            while (r, c) in belegt:
                c += 1
            for dr in range(z["rowspan"]):
                for dc in range(z["colspan"]):
                    belegt.add((r + dr, c + dc))
            ergebnis.append({"zeile": r, "spalte": c, "rowspan": z["rowspan"],
                             "colspan": z["colspan"], "inhalt": norm("".join(z["text"]))})
            c += z["colspan"]
    return sorted(ergebnis, key=lambda z: (z["zeile"], z["spalte"]))


def css_regeln(css):
    """Liefert (selektor, {eigenschaft: wert}) für alle innersten Regeln."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    regeln = []
    for selektor, block in re.findall(r"([^{}]*)\{([^{}]*)\}", css):
        decl = {}
        for teil in block.split(";"):
            if ":" in teil:
                k, v = teil.split(":", 1)
                decl[k.strip().lower()] = v.strip().lower()
        regeln.append((selektor.strip(), decl))
    return regeln


def inline_decl(style):
    decl = {}
    for teil in (style or "").split(";"):
        if ":" in teil:
            k, v = teil.split(":", 1)
            decl[k.strip().lower()] = v.strip().lower()
    return decl


def selektor_trifft_tag(selektor, tag):
    """True, wenn eine der Komma-Alternativen auf das Element `tag` endet."""
    for alt in selektor.split(","):
        letztes = re.split(r"[\s>+~]+", alt.strip())[-1]
        if re.fullmatch(rf"{tag}(\.[\w-]+|#[\w-]+|:[\w-]+)*", letztes, flags=re.I):
            return True
    return False


def selektor_erwaehnt(selektor, token):
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", selektor) is not None


def rahmen_entfernt(decl):
    for k, v in decl.items():
        if not k.startswith("border") or k in ("border-collapse", "border-spacing", "border-radius"):
            continue
        if k.endswith("-color"):
            if "transparent" in v:
                return True
            continue
        if re.search(r"\b(none|hidden)\b", v) or re.fullmatch(r"0(px|em|rem)?", v):
            return True
        if k.endswith("-width") and re.fullmatch(r"0(px|em|rem)?(\s+0(px|em|rem)?)*", v):
            return True
    return False


def voller_rahmen(decl):
    """border-Shorthand oder alle vier Seiten mit sichtbarem Rahmen."""
    def sichtbar(v):
        return bool(v) and not re.search(r"\b(none|hidden)\b", v) \
            and not re.fullmatch(r"0(px|em|rem)?", v)
    if sichtbar(decl.get("border")):
        return True
    return all(sichtbar(decl.get(f"border-{s}"))
               for s in ("top", "right", "bottom", "left"))


class SeitenTest(unittest.TestCase):
    rezept_name = "brownies.json"

    def setUp(self):
        self.rezept = fixture(self.rezept_name)
        self.html = rezeptgraph.seite(copy.deepcopy(self.rezept))
        self.assertIsInstance(self.html, str)
        self.p = einlesen(self.html)
        self.regeln = css_regeln("\n".join(self.p.css))

    def text_ausserhalb(self):
        return norm(" ".join(self.p.text_ausserhalb))


class Tabellenstruktur(SeitenTest):
    def test_genau_eine_tabelle(self):
        self.assertEqual(self.p.tabellen, 1)

    def test_zellstruktur_gleich_fixture(self):
        self.assertEqual(zellen_aus_tabelle(self.p.zeilen), fixture("brownies_cells.json"))

    def test_leere_zellen_sind_eigene_td(self):
        leere = [z for zeile in self.p.zeilen for z in zeile if norm("".join(z["text"])) == ""]
        self.assertEqual(len(leere), 3)
        for z in leere:
            self.assertEqual(z["tag"], "td")

    def test_aufgeteilt_gleich_layout(self):
        r = fixture("aufgeteilt.json")
        p = einlesen(rezeptgraph.seite(copy.deepcopy(r)))
        self.assertEqual(zellen_aus_tabelle(p.zeilen), rezeptgraph.layout(r))


class Rahmen(SeitenTest):
    def test_border_collapse_an_tabelle(self):
        treffer = [s for s, d in self.regeln
                   if selektor_trifft_tag(s, "table") and d.get("border-collapse") == "collapse"]
        self.assertTrue(treffer, f"keine Regel 'table {{border-collapse: collapse}}' in {self.regeln}")

    def test_rahmen_an_allen_zellen(self):
        verwendet = {z["tag"] for zeile in self.p.zeilen for z in zeile}
        self.assertIn("td", verwendet)
        for tag in verwendet:
            with self.subTest(tag=tag):
                treffer = [s for s, d in self.regeln
                           if selektor_trifft_tag(s, tag) and voller_rahmen(d)]
                self.assertTrue(treffer, f"keine CSS-Regel mit vollem Rahmen für {tag}")

    def test_keine_zelle_entfernt_rahmen(self):
        klassen, ids = set(), set()
        for zeile in self.p.zeilen:
            for z in zeile:
                with self.subTest(zelle=z["text"]):
                    self.assertFalse(rahmen_entfernt(inline_decl(z["attrs"].get("style"))),
                                     z["attrs"])
                klassen.update((z["attrs"].get("class") or "").split())
                if z["attrs"].get("id"):
                    ids.add(z["attrs"]["id"])
        for s, d in self.regeln:
            if not rahmen_entfernt(d):
                continue
            betrifft = (any(selektor_trifft_tag(s, t) for t in ZELL_TAGS + ("tr", "*"))
                        or any(selektor_erwaehnt(s, "." + k) for k in klassen)
                        or any(selektor_erwaehnt(s, "#" + i) for i in ids))
            self.assertFalse(betrifft, f"Regel entfernt Rahmen von Zellen: {s} {d}")


class Inhalt(SeitenTest):
    def test_title_und_ueberschrift(self):
        self.assertIn("Brownies", norm("".join(self.p.title)))
        self.assertIn("Brownies", norm("".join(self.p.h1)))

    def test_allergen_hinweis(self):
        text = self.text_ausserhalb()
        self.assertIn("Allergen", text)
        for a in self.rezept["allergene"]:
            self.assertIn(a, text)

    def test_unvollstaendigkeit(self):
        text = self.text_ausserhalb()
        for wort in ("Spuren", "Hersteller", "Gewähr"):
            self.assertIn(wort, text)

    def test_ohne_quelle_kein_quellenabschnitt(self):
        self.assertNotIn("quelle", self.rezept)
        self.assertNotIn("quelle", self.text_ausserhalb().lower())
        links = [a for t, a, _ in self.p.elemente if t == "a" and a.get("href")]
        self.assertEqual(links, [])

    def test_quelle_null_kein_quellenabschnitt(self):
        r = copy.deepcopy(self.rezept)
        r["quelle"] = None
        p = einlesen(rezeptgraph.seite(r))
        self.assertNotIn("quelle", norm(" ".join(p.text_ausserhalb)).lower())
        self.assertEqual([a for t, a, _ in p.elemente if t == "a" and a.get("href")], [])

    def test_leere_allergenliste(self):
        r = copy.deepcopy(self.rezept)
        r["allergene"] = []
        p = einlesen(rezeptgraph.seite(r))
        text = norm(" ".join(p.text_ausserhalb))
        self.assertIn("14", text)
        self.assertIn("Hauptallergene", text)
        self.assertRegex(text, r"\b[Kk]eines der 14\b")
        for wort in ("Spuren", "Hersteller", "Gewähr"):
            self.assertIn(wort, text)


class MitQuelle(SeitenTest):
    rezept_name = "mit_quelle.json"

    def test_quelle_als_link(self):
        links = [a.get("href") for t, a, _ in self.p.elemente if t == "a"]
        self.assertIn(self.rezept["quelle"], links)
        self.assertIn("Quelle", self.text_ausserhalb())

    def test_allergene(self):
        text = self.text_ausserhalb()
        for a in self.rezept["allergene"]:
            self.assertIn(a, text)

    def test_tabelle_gleich_layout(self):
        self.assertEqual(zellen_aus_tabelle(self.p.zeilen), rezeptgraph.layout(self.rezept))


class Mobil(SeitenTest):
    def test_viewport_meta(self):
        metas = [a for t, a, _ in self.p.elemente
                 if t == "meta" and (a.get("name") or "").lower() == "viewport"]
        self.assertEqual(len(metas), 1)
        self.assertIn("width=device-width", (metas[0].get("content") or "").replace(" ", ""))

    def test_tabelle_in_scrollbarem_container(self):
        vorfahren = self.p.tabellen_vorfahren
        self.assertIsNotNone(vorfahren)

        def scrollt(decl):
            return (decl.get("overflow-x") in ("auto", "scroll")
                    or decl.get("overflow") in ("auto", "scroll"))

        gefunden = False
        for tag, attrs in vorfahren:
            if tag in ("html", "body"):
                continue
            if scrollt(inline_decl(attrs.get("style"))):
                gefunden = True
            for s, d in self.regeln:
                if not scrollt(d):
                    continue
                if (selektor_trifft_tag(s, tag)
                        or any(selektor_erwaehnt(s, "." + k)
                               for k in (attrs.get("class") or "").split())
                        or (attrs.get("id") and selektor_erwaehnt(s, "#" + attrs["id"]))):
                    gefunden = True
        self.assertTrue(gefunden, "Tabelle steckt in keinem Container mit overflow-x: auto")

    def test_kein_umbruch_in_tabelle(self):
        treffer = [s for s, d in self.regeln
                   if d.get("white-space") in ("nowrap", "pre")
                   and any(selektor_trifft_tag(s, t) for t in ("table", "tr") + ZELL_TAGS)]
        self.assertTrue(treffer, "keine Regel white-space: nowrap für die Tabelle")


class Deutsch(SeitenTest):
    def test_lang_de(self):
        html_tags = [a for t, a, _ in self.p.elemente if t == "html"]
        self.assertEqual(len(html_tags), 1)
        self.assertEqual((html_tags[0].get("lang") or "").lower(), "de")

    def test_feste_texte_deutsch(self):
        text = self.text_ausserhalb()
        for wort in ("Allergen", "Spuren", "Hersteller", "Gewähr"):
            self.assertIn(wort, text)


class Escaping(unittest.TestCase):
    def setUp(self):
        self.rezept = sonderzeichen()
        self.html = rezeptgraph.seite(copy.deepcopy(self.rezept))
        self.p = einlesen(self.html)

    def test_keine_eingeschleusten_tags(self):
        tags = {t for t, _, _ in self.p.elemente}
        self.assertNotIn("scharf", tags)
        self.assertNotIn("kurz", tags)
        self.assertNotIn("fetten", tags)
        self.assertNotIn("backen", tags)
        self.assertNotIn("<scharf>", self.html)
        self.assertNotIn("<b>Käse", self.html)

    def test_texte_kommen_wörtlich_an(self):
        self.assertIn("Mac & Cheese <scharf>", norm("".join(self.p.title)))
        self.assertIn("Mac & Cheese <scharf>", norm("".join(self.p.h1)))
        self.assertEqual(zellen_aus_tabelle(self.p.zeilen), rezeptgraph.layout(self.rezept))

    def test_quelle_href_escaped(self):
        links = [a.get("href") for t, a, _ in self.p.elemente if t == "a"]
        self.assertIn(self.rezept["quelle"], links)


class Eigenstaendig(SeitenTest):
    def pruefe(self, html):
        p = einlesen(html)
        for tag, attrs, _ in p.elemente:
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
                inline = (attrs.get("style") or "").lower()
                self.assertNotIn("url(", inline)
        css = "\n".join(p.css).lower()
        self.assertNotIn("@import", css)
        self.assertNotIn("url(", css)

    def test_brownies_eigenstaendig(self):
        self.pruefe(self.html)

    def test_mit_quelle_eigenstaendig(self):
        self.pruefe(rezeptgraph.seite(fixture("mit_quelle.json")))


class UngueltigesRezept(unittest.TestCase):
    def test_nicht_baum_wirft_rezeptfehler(self):
        r = fixture("mit_quelle.json")
        r["schritte"].append({"id": "extra", "text": "extra", "eingaenge": ["ruehren"]})
        with self.assertRaises(rezeptgraph.RezeptFehler):
            rezeptgraph.seite(r)

    def test_fehlender_titel_wirft_rezeptfehler(self):
        r = fixture("mit_quelle.json")
        del r["titel"]
        with self.assertRaises(rezeptgraph.RezeptFehler):
            rezeptgraph.seite(r)

    def test_fehlendes_pflichtfeld_wirft_rezeptfehler(self):
        for feld in ("titel", "portionen", "vorbereitung", "zutaten", "schritte", "allergene"):
            with self.subTest(feld=feld):
                r = fixture("mit_quelle.json")
                del r[feld]
                with self.assertRaises(rezeptgraph.RezeptFehler):
                    rezeptgraph.seite(r)


if __name__ == "__main__":
    unittest.main()
