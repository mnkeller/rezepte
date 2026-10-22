# SPEC: Rezept-Graph: Rezeptseiten auf GitHub Pages

Stand: 22.10.2026, Kartentext unverändert übernommen.
Trello: https://trello.com/c/tl1JPys8/23-rezept-graph-rezeptseiten-auf-github-pages

---

Projekt: Sonstiges (Code). Erster Test der Umsetzungs-Pipeline (Coding, Review, Testing).

ZIEL
Michi gibt in Claude Code ein Foto oder einen Screenshot eines Rezepts. Daraus entsteht eine Rezeptseite mit Tabelle im Stil von "Cooking for Engineers" und wird auf GitHub Pages veröffentlicht. Zweck: Mitgebrachtes Essen mit QR-Code versehen, damit andere Zutaten, Allergene und Rezept sehen. Den QR-Code macht Michi selbst aus der URL.

ENTSCHEIDUNG 22.10.
Neuanfang. Der alte Code aus August wird nicht weiterverwendet. Fehlerbild damals: Senkrechte Linien endeten nicht an der passenden waagrechten Linie. Ursache vermutlich fehlende oder rahmenlose leere Durchlauf-Zellen.

ABLAUF
1. Claude Code liest das Foto und erzeugt eine JSON-Datei mit der Rezeptstruktur (einziger KI-Schritt).
2. Claude Code zeigt Michi Tabelle und Allergene als Vorschau zur Bestätigung.
3. Ein festes Render-Skript ohne KI erzeugt daraus die HTML-Seiten.
4. Commit und Push, GitHub Pages veröffentlicht.

DATENMODELL (JSON pro Rezept)
Titel, Portionen, Quelle (Link, falls vorhanden), Vorbereitungsschritte (volle Breite oben, z.B. "Ofen auf 170 °C vorheizen"), Zutaten in Verarbeitungsreihenfolge mit Menge, Einheit, Name, Schritte als Baum. Jeder Schritt hat eine Bezeichnung und eine Liste von Eingängen (Zutaten oder vorherige Schritte). Allergene werden aus den Zutaten abgeleitet und in der JSON gespeichert.

LAYOUT-REGELN (Kern, fest im Skript)
- Jede Fläche ist eine eigene Tabellenzelle mit vollem Rahmen, auch die leeren. Linien entstehen nur aus Zellgrenzen.
- Spalte eines Schritts = höchste Spalte seiner Eingänge + 1. Zutaten stehen in Spalte 0.
- Ein Schritt überspannt alle Zeilen der Zutaten, die in ihm stecken.
- Geht eine Zutat oder eine Gruppe direkt benachbarter Zutaten erst später ein, bekommt sie davor eine einzige leere Zelle über die übersprungenen Spalten.
- Vorbereitungsschritte als Zeilen über volle Breite oben.
- Rezepte, die kein Baum sind (Zwischenprodukt wird aufgeteilt), werden abgelehnt mit klarer Meldung.

SEITEN
- Startseite: Übersicht aller Rezepte, verlinkt.
- Je Rezept eine Seite: Titel, Allergen-Hinweis (EU-Hauptallergene, aus Zutaten abgeleitet), Hinweis auf Unvollständigkeit (Spuren und Herstellerangaben nicht erfasst, keine Gewähr), Tabelle, Quelle.
- Quelle: Wenn es eine gibt (Link), wird sie immer angezeigt. Claude Code fragt beim Einlesen danach, falls sie nicht im Foto steht.
- Mobil lesbar: Tabelle bei Bedarf horizontal scrollbar, kein Seitenumbruch der Tabelle.
- Deutsch und metrisch.

TESTS
- Brownie-Vorlage (Bild liegt im Repo, Michi legt es ab) als Referenz-JSON, Englisch erlaubt.
- Erwartete Zellstruktur als Fixture: für jede Zelle Zeile, Spalte, rowspan, colspan, Inhalt. Test vergleicht die gerenderte Tabelle damit.
- Erwartet für Brownies: Spalten melt | mix | mix | fold in | bake. Leere Zellen: Zucker bis Espresso 1 Spalte × 3 Zeilen, Eier 2 Spalten × 1 Zeile, Mehl bis Salz 3 Spalten × 4 Zeilen.
- Validierungstest: Nicht-Baum-Rezept wird abgelehnt.
- Screenshot-Prüfung der Brownie-Seite durch den Review-Schritt.

ABNAHME
Brownie-Seite sieht strukturell aus wie die Vorlage, alle Tests grün, Startseite und eine Rezeptseite sind online erreichbar, ein echtes Rezept per Foto einmal komplett durchgelaufen.

NÄCHSTER SCHRITT
Michi startet Claude Code am Mac mit dieser Karte und legt das Brownie-Bild ins Repo.

OFFEN
- GitHub-Repo ist vorhanden. Prüfen, ob es öffentlich ist bzw. Pages aktiviert werden kann (bei GitHub Free vermutlich nur mit öffentlichem Repo).

Alte Chats (außerhalb des Projekts): 12.08. https://claude.ai/chat/1ec0a78e-d963-44b1-a639-952a09e58499 und 13.08. https://claude.ai/chat/c94abdd3-10b4-477e-b882-201337099e13
