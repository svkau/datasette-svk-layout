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
| `Public_360` | Ärendehandlingar (ERMS) med ärendesök, handlingssök, diariesökning och sekretessfiltrering |
| `aveny` | Ekonomihandlingar |
| `hrm` | HR-personalsystem med personsök, reseräkningar, tidsredovisning |
| `lonehandlingar` | Lönehandlingar med personsök, periodsök, lönespecifikationer |

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

### Behörighetsroller

| Roll | Beskrivning |
|------|-------------|
| `access.search_casefiles` | Åtkomst till ärendehandlingar med sekretessfiltrering (Public_360) |
| `access.search_casefiles_confidentiality` | Full åtkomst till ärendehandlingar inkl. sekretessmarkerade (Public_360) |
| `access.search_salaries` | Åtkomst till löne- och personaluppgifter (hrm, lonehandlingar) |
| `access.search_everything` | Åtkomst till alla underliggande tabeller + tabellnavigering på startsidorna |
| `access.search_admin` | Administratörsbehörighet (Admin-UI, SQL-körning) |

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
| `/-/admin/site` | Redigera "Om tjänsten"-text och snabblänkar |
| `/-/admin/news` | Lista nyheter |
| `/-/admin/news/new` | Skapa ny nyhet |
| `/-/admin/news/{id}` | Redigera nyhet |
| `/-/admin/news/{id}/delete` | Ta bort nyhet |

### Dynamiskt startsideinnehåll

Startsidans "Om tjänsten"-text, snabblänkar och nyhetsflöde är redigerbara via admin-UI. Data lagras i `svk_metadata.db`:

- **`site_content`** — nyckel-värde för fritext (t.ex. `about_title`, `about_html` med HTML-stöd)
- **`site_links`** — snabblänkar med titel, URL och sorteringsordning
- **`site_news`** — nyheter med titel, HTML-body, författarnamn (från actor) och datum

Om inget innehåll finns i databasen visas hårdkodade standardvärden.

### Migrering från metadata.json

```bash
python -m datasette_svk_layout.migrate_metadata [metadata_path] [db_path]
```

## Dokumentservering

Pluginet registrerar routes för att servera filer direkt från databasen:

- `/{database}/dokument/{id}` — Dokument från `AnstallningDokument`-tabellen (HRM)
- `/{database}/bilaga/{id}` — Bilagor från `Bilaga`-tabellen (HRM)
- `/{database}/lonespec/{lonekorning_id}` — Lönespecifikation som HTML från `lonekorningar.lonespec`-kolumnen (lonehandlingar)

Dokument och bilagor: innehållstyp detekteras automatiskt från filens magic bytes (PDF, bilder, Office-dokument). Lönespecifikationer serveras som HTML direkt i webbläsaren.

### Public_360 — ärendehandlingar med sekretessfiltrering

Public_360-typen bygger på Svenska kyrkans ERMS-anpassning och har sex anpassade templates:

- **Startsida** (`database-Public_360-type`) — Tre sökvägar: fritextsök ärenden, diarielista, fritextsök handlingar
- **Ärendesök** (`query-Public_360-type-SokArenden`) — Fritextsökning med sekretessfiltrering
- **Handlingssök** (`query-Public_360-type-SokHandlingar`) — Fritextsökning med sekretessfiltrering
- **Ärendedetalj** (`row-Public_360-type-aggregation`) — Aktörer, datum, nyckelord, handlingar, bilagor, sekretessmarkeringar
- **Handlingsdetalj** (`row-Public_360-type-record`) — Aktörer, bilagor, länk till ärende
- **Diarievy** (`row-Public_360-type-diary`) — Ärendelista med sökning inom diariet

**Sekretessfiltrering:** Användare med `access.search_casefiles` (utan `_confidentiality`) ser sekretessmarkerade ärenden med maskerad titel ("Skyddat ärende"), maskerade aktörer ("Skyddad") och dolda handlingar. Användare med `access.search_casefiles_confidentiality` ser allt.

**FTS-index för handlingar:** Record-tabellen behöver ett FTS5-index som skapas med:
```bash
python -m datasette_svk_layout.create_record_fts <db_path>
```

### Lonehandlingar — anpassade sökgränssnitt

Lonehandlingar-typen har fem anpassade templates:

- **Startsida** (`database-lonehandlingar-type`) — Två sökvägar: personsök och periodsök (ÅÅÅÅ-MM)
- **Personsök** (`query-lonehandlingar-type-Personer`) — Sök på namn, personnummer eller anställningsnummer
- **Periodsök** (`query-lonehandlingar-type-Lonekorningar`) — Visa alla lönekörningar för en given månad
- **Anställningsdetalj** (`row-lonehandlingar-type-anstallningar`) — Nyckeltal, anställningsperioder, lönetillägg
- **Lönekörningar** (`query-lonehandlingar-type-AnstallningLonekorningar`) — Lönekörningar med transaktionsdetaljer och länk till lönespecifikation

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
