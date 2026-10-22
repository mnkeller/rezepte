"""Zellraster eines Rezepts nach SPEC.md (LAYOUT-REGELN)."""

from .validierung import validieren


def _zutatentext(z):
    return " ".join(t for t in (z["menge"], z["einheit"], z["name"]) if t)


def layout(rezept):
    """Berechnet die Zellen {zeile, spalte, rowspan, colspan, inhalt} eines
    Rezepts, sortiert nach (zeile, spalte). Verändert das Rezept nicht.
    Ungültige Rezepte enden als RezeptFehler."""
    validieren(rezept)
    zutaten = {z["id"]: z for z in rezept["zutaten"]}
    schritte = {s["id"]: s for s in rezept["schritte"]}
    position = {z["id"]: i for i, z in enumerate(rezept["zutaten"])}
    eingegangen = {e for s in rezept["schritte"] for e in s["eingaenge"]}
    letzter = next(s["id"] for s in rezept["schritte"] if s["id"] not in eingegangen)

    spalte = {}

    def berechne_spalte(i):
        if i not in spalte:
            if i in zutaten:
                spalte[i] = 0
            else:
                spalte[i] = max(berechne_spalte(e) for e in schritte[i]["eingaenge"]) + 1
        return spalte[i]

    berechne_spalte(letzter)

    erste_pos = {}

    def berechne_erste_pos(i):
        if i not in erste_pos:
            if i in zutaten:
                erste_pos[i] = position[i]
            else:
                erste_pos[i] = min(berechne_erste_pos(e) for e in schritte[i]["eingaenge"])
        return erste_pos[i]

    berechne_erste_pos(letzter)

    # Eingänge jedes Schritts nach der frühesten ursprünglichen Zutatenposition
    # ordnen. Bereits zusammenhängende Rezepte bleiben so unverändert; sonst
    # hängt danach jeder Teilbaum zusammen.
    def kinder(i):
        return sorted(schritte[i]["eingaenge"], key=lambda e: erste_pos[e])

    reihenfolge = []

    def ausgeben(i):
        if i in zutaten:
            reihenfolge.append(i)
        else:
            for e in kinder(i):
                ausgeben(e)

    ausgeben(letzter)

    n_vb = len(rezept["vorbereitung"])
    breite = spalte[letzter] + 1
    zeile = {i: n_vb + k for k, i in enumerate(reihenfolge)}
    zellen = []

    def zelle(z, s, rowspan, colspan, inhalt):
        zellen.append({"zeile": z, "spalte": s, "rowspan": rowspan,
                       "colspan": colspan, "inhalt": inhalt})

    for k, text in enumerate(rezept["vorbereitung"]):
        zelle(k, 0, 1, breite, text)
    for i in reihenfolge:
        zelle(zeile[i], 0, 1, 1, _zutatentext(zutaten[i]))

    # Erste Zeile und Zeilenzahl jedes Teilbaums
    umfang = {}

    def berechne_umfang(i):
        if i in zutaten:
            umfang[i] = (zeile[i], 1)
        else:
            teile = [berechne_umfang(e) for e in schritte[i]["eingaenge"]]
            umfang[i] = (min(t[0] for t in teile), sum(t[1] for t in teile))
        return umfang[i]

    berechne_umfang(letzter)

    for sid in schritte:
        anfang, hoehe = umfang[sid]
        zelle(anfang, spalte[sid], hoehe, 1, schritte[sid]["text"])

        # Leere Zellen zwischen Eingang und Schritt. Direkt benachbarte Zutaten
        # bilden eine Gruppe mit einer einzigen leeren Zelle; ein Teilbaum aus
        # Schritten bekommt eine eigene.
        gruppe = None  # [anfang, hoehe, startspalte, ist_zutat]
        luecken = []
        for e in kinder(sid):
            e_anfang, e_hoehe = umfang[e]
            start = spalte[e] + 1
            if start >= spalte[sid]:
                gruppe = None
                continue
            if (gruppe is not None and e in zutaten and gruppe[3]
                    and gruppe[0] + gruppe[1] == e_anfang):
                gruppe[1] += e_hoehe
                continue
            gruppe = [e_anfang, e_hoehe, start, e in zutaten]
            luecken.append(gruppe)
        for g_anfang, g_hoehe, start, _ in luecken:
            zelle(g_anfang, start, g_hoehe, spalte[sid] - start, "")

    zellen.sort(key=lambda z: (z["zeile"], z["spalte"]))
    return zellen
