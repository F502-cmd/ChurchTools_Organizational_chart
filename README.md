# ChurchTools Organigramm-Generator

Zieht Gruppendaten (+ Kategorien) über die ChurchTools REST-API und erzeugt daraus automatisch ein Organigramm basierend auf den Kategorien (ChurchTools interne Gruppenhierarchien werden nicht beachtet) — als PDF (Druck/Archiv) und als in eine Webseite einbettbares SVG/HTML (skalierbar, kein Bild-Rendering nötig).

## Architektur

```
churchtools_orgchart/
├── churchtools_client.py     # HTTP-Client (Auth, Pagination, Retry)
├── models.py                 # Group, GroupCategory, OrgNode (Dataclasses)
├── orgchart_builder.py       # Rohdaten -> normalisierte Baumstruktur
├── renderer.py               # Baumstruktur -> Graphviz -> PDF/SVG
└── web_export.py             # SVG -> einbettbares HTML-Snippet
main.py                       # CLI, orchestriert die Pipeline
demo_mock_data.py             # Smoke-Test mit synthetischen Daten (kein CT nötig)
.env                          # Datei für Link & Token Speicherung
```

Die Pipeline ist bewusst in vier lose gekoppelte Schichten geschnitten, damit sich einzelne Teile austauschen lassen, ohne den Rest anzufassen (z.B. später ein anderes Rendering-Backend, oder ein CMS statt Ordner als Ausgabeziel).

## Setup

```pwsh
python -m venv .venv
.venv/bin/activate
pip install -r requirements.txt

# Graphviz-Systempaket (nicht nur die Python-Bindings!)
# (Paketmanager der Wahl nutzbar, bei Chocolatey auf Administrator-Konsole achten.)
choco install graphviz
```

### API-Zugangsdaten

1. In ChurchTools einloggen → eigenes Profil → Reiter **API**
2. Ein persönliches Login-/API-Token generieren
3. `CHURCHTOOLS_BASE_URL` und `CHURCHTOOLS_LOGIN_TOKEN` in `.env` eintragen

## Nutzung

```pwsh
# Smoke-Test ohne echte Zugangsdaten
python demo_mock_data.py

# Echter Lauf gegen echte ChurchTools-Instanz
python main.py

# Weitere Argumente einsehbar unter:
python main.py --help
```

### Verfügbare Parameter

| Parameter | Typ | Standardwert | Beschreibung |
| :--- | :---: | :--- | :--- |
| `--base-url` | `str` | *Wert aus `.env` (`CHURCHTOOLS_BASE_URL`)* | Die URL deiner ChurchTools-Instanz (z. B. `https://meine-gemeinde.church.tools`). |
| `--token` | `str` | *Wert aus `.env` (`CHURCHTOOLS_LOGIN_TOKEN`)* | Dein persönliches API-/Login-Token. Zu finden in ChurchTools unter *Profil -> API-Keys*. |
| `--output-dir` | `str` | `./output` | Das Zielverzeichnis, in dem die generierten PDF-, SVG- oder HTML-Dateien gespeichert werden. |
| `--title` | `str` | `{Your value in the code}` | Der Titel, der oben im generierten Diagramm angezeigt wird. |
| `--rankdir` | `str` | `TB` (Top-Down) | Die Ausrichtung des Organigramms. Erlaubte Werte: `TB` (oben nach unten) oder `LR` (links nach rechts). |
| `--addgroupleaders` | `argparse action` | `False`| Legt fest, ob die Namen der Gruppenleiter im Organigramm angezeigt werden sollen. Flag muss ohne Argument mit angegeben werden.|
| `--addgroupleaderphonenumber` | `argparse action` | `False` | Legt fest, ob die Telefonnummer der Gruppenleiter (falls hinterlegt) im Organigramm angezeigt werden sollen. Flag muss ohne Argument mit angegeben werden. Wird nur ausgeführt, wenn `addgroupleaders` auch geflagged ist.|
| `--addgroupleadermailaddress` | `argparse action` | `False` | Legt fest, ob die Mail-Addresse der Gruppenleiter im Organigramm angezeigt werden sollen. Flag muss ohne Argument mit angegeben werden. Wird nur ausgeführt, wenn `addgroupleaders` auch geflagged ist.|
| `--runner-export` | `argparse action` | `False` | Erzeugt die drei PDF-Varianten für den GitHub Runner. |

---

### Beispiele zur Nutzung

**1. Starten mit Standardeinstellungen (nutzt `.env` und Standard-Titel):**
```pwsh
python main.py
```

**2. Benutzerdefinierter Titel und Ausrichtung von links nach rechts (LR):**
```pwsh
python main.py --title "Unser Team 2026" --rankdir LR
```

**3. Generierung ohne Telefonnummern der Gruppenleiter:**
```pwsh
python main.py --addgroupleaderphonenumber False
```

Ergebnis in `./output/`:
- `orgchart.pdf` — druckfertig
- `orgchart.svg` — vektorbasiert, für eigene Web-Einbindung
- `orgchart_embed.html` — fertiges, responsives Snippet zum Einbetten
  (z.B. per `<iframe src="orgchart_embed.html">` oder Inhalt direkt in
  eine bestehende Seite kopieren)

### GitHub Runner

Der Workflow verwendet den speziellen Runner-Export:

```pwsh
python main.py --runner-export
```

Dabei werden die Leiter- und Kontaktdaten nur einmal aus ChurchTools geladen
und anschließend diese drei Dateien erzeugt und nach Cloudflare R2 hochgeladen:

- `Orgchart.pdf` — Organigramm ohne Leiterdaten
- `Orgchart_phone.pdf` — mit Leiternamen und Telefonnummern
- `Orgchart_mail.pdf` — mit Leiternamen und E-Mail-Adressen

## Test mit Curl

Zum Test der API & Verbindung kann eine beliebige Gruppe aus der Kommandozeile heraus ausgegeben werden.

```pwsh
(curl -s -H "Authorization: Login <persönlicher-API-Token>" "https://<gemeinde-link>.krz.tools/api/groups?limit=1" | ConvertFrom-Json).data[0].information
```

## Wichtiger Hinweis zur ChurchTools-API

Die REST-API wird pro Instanz live per OpenAPI/Swagger dokumentiert unter:

```
https://<gemeinde-link>.church.tools/api
```

Feld- und Endpunktnamen (insbesondere für Gruppenkategorien) unterscheiden sich leicht je nach installierter Version und Hosting-Variante. Der Client ist nach dem aktuell dokumentierten, gängigen Muster gebaut.

## Authentifizierung

- Auth: Header `Authorization: Login <token>`

## Endpunkte

### Authentifizierung & Status
* **Verbindungs-Test**: `GET /api/whoami`
  * Python-Methode: `whoami() -> dict`
  * *Prüft die Validität des Tokens und die Verbindung zum Server.*

### Gruppen
* **Gruppen-IDs abrufen**: `GET /api/groups/ids` (paginiert)
  * Python-Methode: `get_group_ids() -> list[dict]`
  * *Liefert alle für den API-Nutzer sichtbaren Gruppen-IDs.*
* **Details einer Gruppe**: `GET /api/groups/{group_id}`
  * Python-Methode: `get_group_by_id(group_id: int) -> dict`
  * *Liefert die Rohdaten einer spezifischen Gruppe.*
* **Kategorien**: `GET /api/group/groupcategories` (paginiert)
  * Python-Methode: `get_group_categories() -> list[dict]`
  * *Liefert alle für den API-Benutzer sichtbaren Gruppenkategorien.*

### Gruppenmitglieder & Personen
* **Gruppenmitglieder abrufen**: `GET /api/groups/{group_id}/members`
  * Python-Methode: `get_group_members_by_id(group_id: int, role_ids: list[int]) -> dict`
  * Query-Parameter: `role_ids[]` (Filtert die Mitglieder nach bestimmten Rollen-IDs)
  * *Liefert die Rohdaten aller Mitglieder einer Gruppe gefiltert nach Rolle.*
* **Details einer Person**: `GET /api/persons/{personId}`
  * Python-Methode: `get_person_by_id(personId: int) -> dict`
  * *Liefert die Rohdaten zu einer spezifischen Person anhand ihrer ID.*


## Upcoming Features:
- Unterstützung zur Ausgabe von Leitern & Mitarbeitern
