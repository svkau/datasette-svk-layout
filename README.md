# datasette-svk-layout

[![Tests](https://github.com/svkau/datasette-svk-layout/actions/workflows/test.yml/badge.svg)](https://github.com/svkau/datasette-svk-layout/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/svkau/datasette-svk-layout/blob/main/LICENSE)

Datasette-plugin som ger Svenska kyrkans Datasette-instans ett anpassat tema, databas-typsystem, behörighetshantering och admin-gränssnitt.

## Funktioner

- **Svenska kyrkan-tema** — Anpassad layout med SvK-branding, svenskt gränssnitt
- **Databas-typsystem** — Typbaserad konfiguration för 500+ organisationsdatabaser (Public_360, aveny, hrm, lonehandlingar)
- **Template-mappning** — Automatisk routing av databas-specifika mallar till typnivå-mallar
- **Behörighetshantering** — Tvålagers-modell med organisationstillhörighet (databasnivå) och rollbaserade behörigheter (tabellnivå)
- **SQLite metadata-databas** — Lagrar metadata och behörigheter per databas, frikopplat från metadata.json
- **Admin-UI** — Webbaserat gränssnitt för att hantera databaser, metadata och behörigheter
- **Dokumentservering** — Routes för att visa dokument och bilagor direkt från databasen
- **Canned queries** — Fördefinierade sökfrågor per databastyp

## Installation

Installera pluginet i samma miljö som Datasette:

```bash
pip install datasette-svk-layout
```

Eller installera direkt från GitHub:

```bash
pip install git+https://github.com/svkau/datasette-svk-layout.git
```

## Konfiguration

### metadata.json

Pluginet kan konfigureras via Datasettes `metadata.json`. Den enda plugin-specifika inställningen är sökvägen till metadata-databasen:

```json
{
  "plugins": {
    "datasette-svk-layout": {
      "metadata_db_path": "path/to/svk_metadata.db"
    }
  }
}
```

Om `metadata_db_path` utelämnas används standardplatsen `datasette_svk_layout/data/svk_metadata.db` (inuti plugin-paketet).

### Konfigurationsprioritet

Metadata löses i följande ordning (högst prioritet först):

1. `metadata.json` — Specifika överskrivningar för enskilda databaser/tabeller
2. `svk_metadata.db` — SQLite-databas med metadata och behörigheter per databas
3. `database_types.json` — Delad konfiguration per databastyp
4. Datasettes standardmallar

## Databas-typsystem

Databasnamn följer mönstret `{typ}_{orgnr}`, t.ex. `hrm_2520037173` eller `Public_360_2520026135`.

Typdefinitioner i `datasette_svk_layout/data/database_types.json` styr:

- **Titlar och beskrivningar** — Mallar med `{unit_name}` som ersätts med organisationens namn
- **Tabellmetadata** — Titlar, beskrivningar och kolumnbeskrivningar per tabell
- **Behörigheter** — Vilka roller som krävs för åtkomst till tabeller
- **Canned queries** — Fördefinierade sökfrågor
- **Template-mappningar** — Vilka mallar som ska användas för databas-, tabell-, fråge- och radvyer

### Tillgängliga typer

| Typ | Beskrivning |
|-----|-------------|
| `Public_360` | Ärendehandlingar från ärendehanteringssystem |
| `aveny` | Ekonomihandlingar |
| `hrm` | HR-personalsystem med personsök, reseräkningar, tidsredovisning |
| `lonehandlingar` | Lönehandlingar |

### Organisationsregister

`datasette_svk_layout/data/units.json` mappar organisationsnummer till namn, t.ex. `2520026135` → `Härnösands stift`.

## Behörighetsmodell

Pluginet implementerar en tvålagers-behörighetsmodell:

### 1. Databasnivå — Organisationstillhörighet

Styr vilka databaser en användare ser. Konfigureras i `svk_metadata.db` (eller `metadata.json`) med `allow`-block som matchar mot aktörens `organizations_ids`:

```json
{
  "allow": {
    "organizations_ids": [2520026135]
  }
}
```

### 2. Tabellnivå — Rollbaserade behörigheter

Styr åtkomst till tabeller inom en databas. Konfigureras i `database_types.json` under varje tabells `allow.permissions`:

```json
{
  "allow": {
    "permissions": ["access.search_casefiles", "access.search_everything"]
  }
}
```

Om alla tabeller kräver behörigheter och användaren saknar rätt roll, döljs databasen automatiskt.

## SQLite metadata-databas

`svk_metadata.db` lagrar metadata och behörigheter utan att behöva redigera `metadata.json`.

### Schema

- **`database_metadata`** — title, description, source, license per databas
- **`database_permissions`** — Normaliserade rader med (database_name, action, actor_key, actor_value)

### Extern integration

Externa system (t.ex. ESSArch) kan registrera databaser direkt via SQLite:

```python
import sqlite3
conn = sqlite3.connect("datasette_svk_layout/data/svk_metadata.db")
conn.execute(
    "INSERT OR IGNORE INTO database_permissions "
    "(database_name, action, actor_key, actor_value) "
    "VALUES (?, 'view-database', 'organizations_ids', ?)",
    (database_name, str(org_id))
)
conn.commit()
```

Notera: `actor_value` lagras alltid som sträng — konvertering till rätt typ sker vid utläsning.

## Admin-UI

Webbaserat gränssnitt under `/-/admin/` (kräver `access.search_admin`):

| Route | Funktion |
|-------|----------|
| `/-/admin/databases` | Lista och sök databaser |
| `/-/admin/databases/{name}` | Redigera metadata och behörigheter |
| `/-/admin/databases/{name}/delete` | Ta bort databaspost |
| `/-/admin/import` | Importera från metadata.json |

### Migrering från metadata.json

```bash
python -m datasette_svk_layout.migrate_metadata [metadata_path] [db_path]
```

## Dokumentservering

Pluginet registrerar routes för att servera filer direkt från databasen:

- `/{database}/dokument/{id}` — Dokument från `AnstallningDokument`-tabellen
- `/{database}/bilaga/{id}` — Bilagor från `Bilaga`-tabellen

Innehållstyp detekteras automatiskt från filens magic bytes (PDF, bilder, Office-dokument).

## Template-hjälpfunktioner

Följande funktioner är tillgängliga i Jinja2-mallar:

| Funktion | Beskrivning |
|----------|-------------|
| `sql(query, params)` | Kör SQL-fråga i mallen (async, kräver databaskontext) |
| `get_unit_name(orgnr)` | Slå upp organisationsnamn |
| `get_database_type_config(database)` | Hämta typkonfiguration för en databas |
| `get_column_label(database, table, column)` | Hämta läsbar kolumnrubrik |

## Utveckling

```bash
# Klona repot
git clone https://github.com/svkau/datasette-svk-layout.git
cd datasette-svk-layout

# Skapa virtualenv
python -m venv venv
source venv/bin/activate

# Installera med testberoenden
pip install -e '.[test]'

# Kör tester
pytest

# Kör lokalt
datasette data/*.db --metadata data/metadata.json --plugins-dir dev_plugins/
```

### Lokal utveckling med mock-aktör

Kopiera `dev_plugins/dev_mock_actor.example.py` till `dev_plugins/dev_mock_actor.py` och skapa en `actor.json` i projektroten med önskad aktörsinformation.

## Licens

Apache License 2.0
