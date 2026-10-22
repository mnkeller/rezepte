# Rezeptformat (JSON)

Eine Datei pro Rezept in `rezepte/`, Dateiname = Slug der Seite (`brownies.json` → `brownies.html`).

```json
{
  "titel": "Brownies",
  "portionen": "16 Stück",
  "quelle": "https://www.cookingforengineers.com/recipe/...",
  "vorbereitung": [
    "Form (20 × 20 cm) fetten und mehlen",
    "Ofen auf 170 °C vorheizen"
  ],
  "zutaten": [
    {"id": "butter", "menge": "115", "einheit": "g", "name": "ungesalzene Butter"},
    {"id": "zucker", "menge": "200", "einheit": "g", "name": "Zucker"}
  ],
  "schritte": [
    {"id": "schmelzen", "text": "schmelzen", "eingaenge": ["butter"]},
    {"id": "mischen", "text": "mischen", "eingaenge": ["schmelzen", "zucker"]}
  ],
  "allergene": ["Milch"]
}
```

## Felder

| Feld | Pflicht | Inhalt |
|---|---|---|
| `titel` | ja | nicht leerer Text |
| `portionen` | ja | Text, z.B. "4" oder "1 Blech" |
| `quelle` | nein | Link (http/https). Fehlt das Feld oder ist es `null`, gibt es keine Quelle. |
| `vorbereitung` | ja | Liste von Texten, darf leer sein. Erscheinen als Zeilen über volle Breite oben. |
| `zutaten` | ja | Liste, mindestens eine, in Verarbeitungsreihenfolge (von oben nach unten) |
| `zutaten[].id` | ja | eindeutig im Rezept |
| `zutaten[].menge` | ja | Text, darf leer sein (z.B. "1/2", "") |
| `zutaten[].einheit` | ja | Text, darf leer sein |
| `zutaten[].name` | ja | nicht leerer Text |
| `schritte` | ja | Liste, mindestens einer |
| `schritte[].id` | ja | eindeutig im Rezept, auch gegenüber Zutaten-IDs |
| `schritte[].text` | ja | Bezeichnung in der Zelle |
| `schritte[].eingaenge` | ja | nicht leere Liste von Zutaten- oder Schritt-IDs |
| `allergene` | ja | Liste aus den 14 EU-Hauptallergenen (Schreibweise siehe unten), darf leer sein |

Zelltext einer Zutat: `menge`, `einheit` und `name` mit je einem Leerzeichen verbunden, leere Teile entfallen.

## Baumregel

- Jede Zutat geht in genau einen Schritt ein.
- Jeder Schritt außer dem letzten geht in genau einen weiteren Schritt ein.
- Es gibt genau einen letzten Schritt (geht nirgends ein); von ihm aus sind alle Zutaten und Schritte erreichbar.
- Keine Zyklen.

Wird ein Zwischenprodukt aufgeteilt (ein Schritt geht in zwei Schritte ein), ist das kein Baum. Das Rezept wird mit Meldung abgelehnt.

## Aufgeteilte Zutat

"Die Hälfte des Zuckers jetzt, die andere Hälfte später": zwei Zutatenzeilen mit eigener ID und je der Teilmenge, z.B.

```json
{"id": "zucker1", "menge": "100", "einheit": "g", "name": "Zucker (1. Hälfte)"},
{"id": "zucker2", "menge": "100", "einheit": "g", "name": "Zucker (2. Hälfte)"}
```

## Allergene (Schreibweise)

Glutenhaltiges Getreide, Krebstiere, Eier, Fische, Erdnüsse, Soja, Milch, Schalenfrüchte, Sellerie, Senf, Sesam, Schwefeldioxid und Sulfite, Lupinen, Weichtiere
