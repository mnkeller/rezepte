"""HTML-Rezeptseite nach SPEC.md (SEITEN)."""

from html import escape

from .layout import layout
from .validierung import validieren

# Gemeinsame Basis aller Seiten (Startseite und Rezeptseiten): Schrift, Farben,
# Link-Stil. Das Aussehen steht allein hier und in den beiden CSS-Blöcken.
BASIS_CSS = """
*{box-sizing:border-box}
html, body{margin:0;padding:0;background:#fff;color:#111;font-family:"Plus Jakarta Sans",ui-sans-serif,-apple-system,"system-ui","Segoe UI",Roboto,"Helvetica Neue",sans-serif}
a{color:#111}
"""

CSS = BASIS_CSS + """
body { margin: 0 auto; padding: 1rem; max-width: 60rem; line-height: 1.4; }
.zurueck { display: inline-flex; align-items: center; min-height: 44px;
  margin: 0 0 1.25rem; padding: 0 1rem; border: 2px solid #111; font-weight: 600;
  color: #111; text-decoration: none; }
.zurueck:hover, .zurueck:focus-visible { background: #111; color: #fff;
  outline: 3px solid #111; outline-offset: 2px; }
h1 { margin: 0 0 .5rem; font-size: clamp(1.8rem, 5vw, 3rem); line-height: 1.1;
  letter-spacing: -0.02em; font-weight: 800;
  overflow-wrap: anywhere; hyphens: auto; -webkit-hyphens: auto; }
.portionen { margin: 0 0 1.25rem; color: #555; }
.hinweise { margin: 0 0 1rem; padding: .6rem .8rem; background: #f5f5f5;
  border-left: 4px solid #111; }
.hinweise p { margin: .2rem 0; }
.tabelle { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 0 1.25rem; }
.tabelle:focus-visible { outline: 3px solid #111; outline-offset: 2px; }
table { border-collapse: collapse; border: 4px solid #111; white-space: nowrap; }
td { border: 3px solid #111; padding: .3rem .6rem; white-space: nowrap;
  text-align: center; vertical-align: middle; }
td.zutat { text-align: left; }
td.senkrecht { padding: .3rem .2rem; }
.senkrecht > span { display: inline-block; writing-mode: vertical-rl;
  white-space: normal; text-align: center;
  overflow-wrap: anywhere; hyphens: auto; -webkit-hyphens: auto; }
.quelle { font-size: .9rem; word-break: break-all; }
.quelle a { color: #111; text-decoration: underline; }
"""

# Angenommene Höhe einer Tabellenzeile in rem: Padding .3rem oben und unten,
# eine Textzeile (line-height 1.4 bei 1rem) und der Rahmen. Daraus wird die
# max-height senkrechter Texte berechnet, damit sie umbrechen, statt die
# Tabelle zu strecken.
ZEILENHOEHE_REM = 2.1
# Abzug für Padding und Rahmen der senkrechten Zelle selbst.
SENKRECHT_ABZUG_REM = 0.8


def _zelle(z, n_vorbereitung):
    senkrecht = False
    if z["zeile"] < n_vorbereitung:
        klasse = "vorbereitung"
    elif z["spalte"] == 0:
        klasse = "zutat"
    elif z["inhalt"]:
        senkrecht = z["rowspan"] >= 3
        klasse = "schritt senkrecht" if senkrecht else "schritt"
    else:
        klasse = "leer"
    attrs = f' class="{klasse}"'
    if z["rowspan"] > 1:
        attrs += f' rowspan="{z["rowspan"]}"'
    if z["colspan"] > 1:
        attrs += f' colspan="{z["colspan"]}"'
    inhalt = escape(z["inhalt"])
    if senkrecht:
        hoehe = z["rowspan"] * ZEILENHOEHE_REM - SENKRECHT_ABZUG_REM
        inhalt = f'<span style="max-height: {hoehe:.1f}rem">{inhalt}</span>'
    return f"<td{attrs}>{inhalt}</td>"


def _tabelle(rezept):
    n_vorbereitung = len(rezept["vorbereitung"])
    zeilen = {}
    for z in layout(rezept):
        zeilen.setdefault(z["zeile"], []).append(_zelle(z, n_vorbereitung))
    teile = ["<table>"]
    for nr in sorted(zeilen):
        teile.append("<tr>" + "".join(zeilen[nr]) + "</tr>")
    teile.append("</table>")
    return "\n".join(teile)


def _allergen_hinweis(allergene):
    if allergene:
        liste = ", ".join(escape(a) for a in allergene)
        return (f"<p><strong>Allergene</strong> (von den 14 EU-Hauptallergenen): "
                f"{liste}</p>")
    return ("<p><strong>Allergene:</strong> keines der 14 EU-Hauptallergene "
            "in den Zutaten.</p>")


def seite(rezept):
    """Erzeugt die vollständige, eigenständige HTML-Seite eines Rezepts.
    Ungültige Rezepte enden als RezeptFehler."""
    validieren(rezept)  # wirft RezeptFehler, bevor Felder gelesen werden
    tabelle = _tabelle(rezept)
    titel = escape(rezept["titel"])
    teile = [
        "<!DOCTYPE html>",
        '<html lang="de">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{titel}</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        '<a class="zurueck" href="index.html">← Alle Rezepte</a>',
        f"<h1>{titel}</h1>",
    ]
    if rezept["portionen"]:
        teile.append(f'<p class="portionen">Portionen: {escape(rezept["portionen"])}</p>')
    teile += [
        f'<div class="tabelle" tabindex="0" role="region" aria-label="Rezepttabelle">\n{tabelle}\n</div>',
        '<div class="hinweise">',
        _allergen_hinweis(rezept["allergene"]),
        "<p>Abgeleitet aus den Zutaten. Spuren und Herstellerangaben sind nicht "
        "erfasst, daher ohne Gewähr.</p>",
        "</div>",
    ]
    quelle = rezept.get("quelle")
    if quelle:
        q = escape(quelle)
        teile.append(f'<p class="quelle">Quelle: <a href="{q}">{q}</a></p>')
    teile += ["</body>", "</html>", ""]
    return "\n".join(teile)


STARTSEITE_CSS = BASIS_CSS + """
body{padding:3rem 1rem 3rem;text-align:center;line-height:1.5}
h1{margin:0 0 2rem;font-size:clamp(2.8rem,9vw,6rem);line-height:1;letter-spacing:-0.02em;font-weight:300}
h1 strong{display:block;font-weight:800}
.untertitel{margin:0 auto 3rem;max-width:40rem;font-size:1.1rem;font-weight:500;color:#333}
.rezepte{list-style:none;margin:0 auto;padding:0;max-width:40rem;border-top:1px solid #111;text-align:left}
.rezepte li{border-bottom:1px solid #111}
.rezepte a{display:flex;justify-content:space-between;align-items:center;min-height:48px;padding:1.1rem 1rem;font-size:1.4rem;font-weight:600;color:#111;text-decoration:none;overflow-wrap:anywhere}
.rezepte a::after{content:"\\2192";margin-left:1rem;flex-shrink:0}
.rezepte a:hover,.rezepte a:focus-visible{background:#111;color:#fff;outline:3px solid #111;outline-offset:2px}
.leer{font-size:1.1rem}
.hinweis{margin:3rem 0 0;font-size:.9rem;color:#555}
.hinweis a{color:#555}
.hinweis a:hover,.hinweis a:focus{color:#111}
"""


def startseite(rezepte):
    """Erzeugt die eigenständige HTML-Startseite aus (slug, rezept)-Paaren.
    Die Liste ist nach Titel sortiert, unabhängig von der Eingabereihenfolge."""
    sortiert = sorted(rezepte, key=lambda p: (p[1]["titel"].casefold(), p[1]["titel"], p[0]))
    teile = [
        "<!DOCTYPE html>",
        '<html lang="de">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Rezepte, weniger schwer</title>",
        f"<style>{STARTSEITE_CSS}</style>",
        "</head>",
        "<body>",
        '<h1><strong>Rezepte</strong> weniger schwer</h1>',
        '<p class="untertitel">Zutaten, Schritte und Allergene auf einen Blick.</p>',
    ]
    if sortiert:
        teile.append('<ul class="rezepte">')
        for slug, rezept in sortiert:
            href = escape(slug + ".html")
            teile.append(f'<li><a href="{href}">{escape(rezept["titel"])}</a></li>')
        teile.append("</ul>")
    else:
        teile.append('<p class="leer">Noch keine Rezepte.</p>')
    teile += [
        '<p class="hinweis">Darstellung inspiriert von '
        '<a href="https://www.cookingforengineers.com/" rel="noopener noreferrer">Cooking for Engineers</a></p>',
        "</body>", "</html>", "",
    ]
    return "\n".join(teile)
