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


def zell_klassen(z):
    return (z["attrs"].get("class") or "").split()


def zellen_mit_klassen(zeilen):
    """Wie zellen_aus_tabelle, zusätzlich mit den Klassen jeder Zelle."""
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
                             "inhalt": norm("".join(z["text"])),
                             "klassen": set(zell_klassen(z))})
            c += z["colspan"]
    return ergebnis


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
        if re.fullmatch(rf"{re.escape(tag)}(\.[\w-]+|#[\w-]+|:[\w-]+)*", letztes, flags=re.I):
            return True
    return False


def selektor_erwaehnt(selektor, token):
    """True, wenn `token` (Klasse `.x`, ID `#x` oder Elementname) im Selektor vorkommt.
    Klassen/IDs duerfen direkt an einem Elementnamen oder einer anderen Klasse haengen
    (`td.senkrecht`, `.a.senkrecht`); Elementnamen muessen frei stehen."""
    vorne = "" if token[:1] in ".#" else r"(?<![\w.#-])"
    return re.search(rf"{vorne}{re.escape(token)}(?![\w-])", selektor) is not None


def ohne_not(selektor):
    """Entfernt `:not(...)`-Teile; was darin steht, schränkt nicht ein."""
    vorher = None
    while vorher != selektor:
        vorher = selektor
        selektor = re.sub(r":not\([^()]*\)", "", selektor, flags=re.I)
    return selektor


def eingeschraenkt_auf(selektor, token):
    """True, wenn `token` im Selektor außerhalb von `:not(...)` vorkommt."""
    return selektor_erwaehnt(ohne_not(selektor), token)


def child_elemente(p, attrs):
    """Direkte Kindelemente des Elements mit genau diesem attrs-Objekt."""
    return [(t, a) for t, a, vorfahren in p.elemente
            if vorfahren and vorfahren[-1][1] is attrs]


def rem_wert(wert):
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*rem\s*(!important)?\s*", wert or "")
    return float(m.group(1)) if m else None


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


class Hilfsfunktionen(unittest.TestCase):
    """Selbsttests fuer die Selektor-Helfer dieser Testdatei."""

    def test_trifft_tag(self):
        self.assertTrue(selektor_trifft_tag("td", "td"))
        self.assertTrue(selektor_trifft_tag("table td", "td"))
        self.assertTrue(selektor_trifft_tag("td.senkrecht", "td"))
        self.assertTrue(selektor_trifft_tag("th, td", "td"))
        self.assertTrue(selektor_trifft_tag("*", "*"))
        self.assertTrue(selektor_trifft_tag("table *", "*"))
        self.assertFalse(selektor_trifft_tag("table td", "table"))
        self.assertFalse(selektor_trifft_tag(".senkrecht > span", "td"))
        self.assertFalse(selektor_trifft_tag("td", "*"))
        self.assertFalse(selektor_trifft_tag("tdx", "td"))

    def test_trifft_tag_ohne_regexfehler(self):
        for sel in (".senkrecht", ".senkrecht > span", "*", "a:hover", "#x"):
            for tag in ("table", "tr", "td", "th", "*"):
                selektor_trifft_tag(sel, tag)

    def test_erwaehnt(self):
        self.assertTrue(selektor_erwaehnt("td.senkrecht", ".senkrecht"))
        self.assertTrue(selektor_erwaehnt(".senkrecht", ".senkrecht"))
        self.assertTrue(selektor_erwaehnt(".senkrecht > span", ".senkrecht"))
        self.assertTrue(selektor_erwaehnt("table td.a.senkrecht", ".senkrecht"))
        self.assertTrue(selektor_erwaehnt("div#rezept td", "#rezept"))
        self.assertFalse(selektor_erwaehnt(".senkrecht-x", ".senkrecht"))
        self.assertFalse(selektor_erwaehnt(".nicht-senkrecht", ".senkrecht"))
        self.assertFalse(selektor_erwaehnt("table td", ".senkrecht"))
        self.assertFalse(selektor_erwaehnt("*", ".senkrecht"))
        self.assertFalse(selektor_erwaehnt(".tdx", "td"))

    def test_eingeschraenkt_mit_not(self):
        self.assertTrue(eingeschraenkt_auf("td.senkrecht", ".senkrecht"))
        self.assertTrue(eingeschraenkt_auf(".senkrecht > span", ".senkrecht"))
        self.assertTrue(eingeschraenkt_auf(".senkrecht:not(.x)", ".senkrecht"))
        self.assertTrue(eingeschraenkt_auf("td:not(.a) .senkrecht", ".senkrecht"))
        self.assertFalse(eingeschraenkt_auf("td:not(.senkrecht)", ".senkrecht"))
        self.assertFalse(eingeschraenkt_auf("td:NOT(.senkrecht)", ".senkrecht"))
        self.assertFalse(eingeschraenkt_auf(".schritt:not(td.senkrecht) span", ".senkrecht"))
        self.assertFalse(eingeschraenkt_auf("table td", ".senkrecht"))
        self.assertEqual(ohne_not("td:not(.senkrecht)"), "td")


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

    def test_umbruch_nur_in_senkrechten_zellen(self):
        """Paket 5b: Ausnahme vom Nicht-Umbrechen gilt nur für .senkrecht.

        Jede Regel, die in der Tabelle Umbruch erlaubt, muss auf .senkrecht
        eingeschränkt sein; nicht senkrechte Zellen setzen kein Umbrechen inline.
        """
        klassen, ids = set(), set()
        for zeile in self.p.zeilen:
            for z in zeile:
                klassen.update(zell_klassen(z))
                if z["attrs"].get("id"):
                    ids.add(z["attrs"]["id"])
                if "senkrecht" in zell_klassen(z):
                    continue
                with self.subTest(zelle=z["text"]):
                    ws = inline_decl(z["attrs"].get("style")).get("white-space")
                    self.assertIn(ws, (None, "nowrap", "pre"), z["attrs"])
        for s, d in self.regeln:
            ws = d.get("white-space")
            if ws is None or ws in ("nowrap", "pre"):
                continue
            for alt in s.split(","):
                betrifft = (any(selektor_trifft_tag(alt, t) or selektor_trifft_tag(ohne_not(alt), t)
                                for t in ("table", "tr", "*") + ZELL_TAGS)
                            or any(selektor_erwaehnt(alt, "." + k) for k in klassen)
                            or any(selektor_erwaehnt(alt, "#" + i) for i in ids))
                if betrifft:
                    with self.subTest(selektor=alt):
                        self.assertTrue(eingeschraenkt_auf(alt, ".senkrecht"),
                                        f"Regel erlaubt Umbruch außerhalb von .senkrecht: {alt} {d}")


class Senkrecht(SeitenTest):
    """Paket 5b: Schrittzellen ab 3 Zeilen Höhe senkrecht."""

    def pruefe_klassen(self, rezept, zeilen):
        n_vorb = len(rezept["vorbereitung"])
        zellen = zellen_mit_klassen(zeilen)
        self.assertTrue(zellen)
        for z in zellen:
            with self.subTest(zelle=z["inhalt"], zeile=z["zeile"], spalte=z["spalte"]):
                ist_schritt = z["zeile"] >= n_vorb and z["spalte"] > 0 and z["inhalt"] != ""
                if ist_schritt:
                    self.assertIn("schritt", z["klassen"])
                    if z["rowspan"] >= 3:
                        self.assertIn("senkrecht", z["klassen"])
                    else:
                        self.assertNotIn("senkrecht", z["klassen"])
                else:
                    self.assertNotIn("senkrecht", z["klassen"])

    def test_regel_brownies(self):
        self.pruefe_klassen(self.rezept, self.p.zeilen)

    def test_regel_aufgeteilt(self):
        r = fixture("aufgeteilt.json")
        self.pruefe_klassen(r, einlesen(rezeptgraph.seite(copy.deepcopy(r))).zeilen)

    def test_regel_mit_quelle(self):
        r = fixture("mit_quelle.json")
        self.pruefe_klassen(r, einlesen(rezeptgraph.seite(copy.deepcopy(r))).zeilen)

    def test_brownies_konkret(self):
        schritte = [(z["inhalt"], "senkrecht" in z["klassen"])
                    for z in zellen_mit_klassen(self.p.zeilen) if "schritt" in z["klassen"]]
        self.assertEqual(schritte, [("melt", False), ("mix", True), ("mix", True),
                                    ("fold in", True), ("bake 170 °C 30 to 40 min", True)])

    def senkrecht_regeln(self):
        return [(s, d) for s, d in self.regeln if selektor_erwaehnt(s, ".senkrecht")]

    def test_css_schreibrichtung_von_unten_nach_oben(self):
        regeln = self.senkrecht_regeln()
        self.assertTrue(regeln, "keine CSS-Regel für .senkrecht")
        modi = {d.get("writing-mode") for _, d in regeln} - {None}
        transforms = " ".join(d.get("transform", "") for _, d in regeln).replace(" ", "")
        if "sideways-lr" in modi:
            return
        self.assertTrue(modi & {"vertical-rl", "vertical-lr"},
                        f"keine senkrechte Schreibrichtung für .senkrecht: {regeln}")
        self.assertRegex(transforms, r"rotate\((180deg|-180deg|0?\.5turn|-0?\.5turn)\)",
                         "senkrechter Text nicht von unten nach oben lesbar (rotate(180deg) fehlt)")

    def test_css_senkrechte_zellen_brechen_um(self):
        regeln = self.senkrecht_regeln()
        self.assertTrue(regeln, "keine CSS-Regel für .senkrecht")
        werte = [d.get("white-space") for _, d in regeln if "white-space" in d]
        self.assertIn("normal", werte, "für .senkrecht fehlt white-space: normal")
        for w in werte:
            self.assertNotIn(w, ("nowrap", "pre"))

    def test_css_lange_woerter_bleiben_in_der_zelle(self):
        """Muss: Lange Wörter umbrechen statt aus der senkrechten Zelle zu laufen."""
        regeln = [(s, d) for s, d in self.regeln
                  if any(eingeschraenkt_auf(alt, ".senkrecht") for alt in s.split(","))]
        self.assertTrue(regeln, "keine CSS-Regel für .senkrecht")
        umbruch = [s for s, d in regeln
                   if d.get("overflow-wrap") == "anywhere"
                   or d.get("word-break") in ("break-word", "break-all")]
        self.assertTrue(umbruch, "für .senkrecht fehlt overflow-wrap: anywhere "
                                 f"(oder word-break: break-word/break-all): {regeln}")
        trennung = [s for s, d in regeln if d.get("hyphens") == "auto"]
        self.assertTrue(trennung, f"für .senkrecht fehlt hyphens: auto: {regeln}")

    def pruefe_max_height(self, p):
        werte = []
        for zeile in p.zeilen:
            for z in zeile:
                if "senkrecht" not in zell_klassen(z):
                    continue
                kinder = child_elemente(p, z["attrs"])
                with self.subTest(zelle=norm("".join(z["text"])), rowspan=z["rowspan"]):
                    self.assertEqual(len(kinder), 1, f"nicht genau ein Kindelement: {kinder}")
                    mh = inline_decl(kinder[0][1].get("style")).get("max-height")
                    self.assertIsNotNone(mh, f"Kindelement ohne max-height: {kinder[0]}")
                    rem = rem_wert(mh)
                    self.assertIsNotNone(rem, f"max-height nicht in rem: {mh}")
                    self.assertLess(rem, z["rowspan"] * 2.2)
                    werte.append((z["rowspan"], rem))
        return werte

    def test_max_height_brownies(self):
        """Sollte: max-height wächst streng monoton mit rowspan (Brownies: 4, 5, 9)."""
        werte = self.pruefe_max_height(self.p)
        self.assertEqual(sorted({r for r, _ in werte}), [4, 5, 9])
        for r1, m1 in werte:
            for r2, m2 in werte:
                if r1 < r2:
                    self.assertLess(m1, m2, f"rowspan {r1}: {m1}rem, rowspan {r2}: {m2}rem")
                elif r1 == r2:
                    self.assertEqual(m1, m2, f"rowspan {r1}: {m1}rem vs. {m2}rem")

    def test_max_height_weitere_fixtures(self):
        for name in ("aufgeteilt.json", "mit_quelle.json"):
            with self.subTest(fixture=name):
                p = einlesen(rezeptgraph.seite(fixture(name)))
                self.pruefe_max_height(p)


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
