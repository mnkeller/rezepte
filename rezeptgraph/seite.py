"""HTML-Rezeptseite nach SPEC.md (SEITEN)."""

from html import escape

from .layout import layout
from .validierung import validieren

CSS = """
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  margin: 0 auto; padding: 1rem; max-width: 60rem; color: #222; line-height: 1.4; }
h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
.portionen { margin: 0 0 1rem; color: #555; }
.hinweise { margin: 0 0 1rem; padding: .6rem .8rem; background: #f4f8f4;
  border-left: 4px solid #1e8c2e; }
.hinweise p { margin: .2rem 0; }
.tabelle { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 0 1rem; }
table { border-collapse: collapse; border: 3px solid #1e8c2e; white-space: nowrap; }
td { border: 2px solid #1e8c2e; padding: .3rem .6rem; white-space: nowrap;
  text-align: center; vertical-align: middle; }
td.zutat { text-align: left; }
td.senkrecht { padding: .3rem .2rem; }
.senkrecht > span { display: inline-block; writing-mode: vertical-rl;
  transform: rotate(180deg); white-space: normal; text-align: center;
  overflow-wrap: anywhere; hyphens: auto; -webkit-hyphens: auto; }
.quelle { font-size: .9rem; word-break: break-all; }
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
        f"<h1>{titel}</h1>",
    ]
    if rezept["portionen"]:
        teile.append(f'<p class="portionen">Portionen: {escape(rezept["portionen"])}</p>')
    teile += [
        '<div class="hinweise">',
        _allergen_hinweis(rezept["allergene"]),
        "<p>Abgeleitet aus den Zutaten. Spuren und Herstellerangaben sind nicht "
        "erfasst, daher ohne Gewähr.</p>",
        "</div>",
        f'<div class="tabelle">\n{tabelle}\n</div>',
    ]
    quelle = rezept.get("quelle")
    if quelle:
        q = escape(quelle)
        teile.append(f'<p class="quelle">Quelle: <a href="{q}">{q}</a></p>')
    teile += ["</body>", "</html>", ""]
    return "\n".join(teile)


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
        "<title>Rezepte</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Rezepte</h1>",
    ]
    if sortiert:
        teile.append('<ul class="rezepte">')
        for slug, rezept in sortiert:
            href = escape(slug + ".html")
            teile.append(f'<li><a href="{href}">{escape(rezept["titel"])}</a></li>')
        teile.append("</ul>")
    else:
        teile.append("<p>Noch keine Rezepte.</p>")
    teile += ["</body>", "</html>", ""]
    return "\n".join(teile)
