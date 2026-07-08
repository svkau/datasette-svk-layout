# CLAUDE.md

> **⚠️ Detta är `datasette-1.0`-branchen (version 0.5.x) — avsedd för Datasette 1.0 (1.0a35+).**
> Datasette 0.x-spåret lever kvar på `main` (version 0.4.x) och är oförändrat. De två
> branscherna är parallella och mergas INTE ihop — 1.0-koden bryter 0.x och tvärtom.
> Se `## Datasette 1.0 vs 0.x` nedan för vad som skiljer. `dependencies` pinnar
> `datasette>=1.0a0` på denna branch.

## Project Overview

Datasette plugin (`datasette-svk-layout`) that provides a custom layout/theme for Svenska kyrkans Datasette instance. Swedish-localized UI with Svenska kyrkan branding.

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -e '.[test]'

# Run tests
pytest

# Run locally
datasette data/*.db --metadata data/metadata.json --plugins-dir dev_plugins/
```

## Architecture

### Plugin Structure
- **Entry point**: `svk_layout` in `pyproject.toml` -> `datasette_svk_layout` module
- **Templates**: Jinja2 overrides in `datasette_svk_layout/templates/`
- **Static assets**: CSS/JS in `datasette_svk_layout/static/`
- **Plugin hooks** in `__init__.py`: `startup`, `get_metadata`, `canned_queries`, `extra_template_vars`, `permission_resources_sql`, `permission_allowed`, `prepare_jinja2_environment`, `register_routes`
  - `permission_resources_sql` — **behörighetsprövning under Datasette 1.0** (se `## Datasette 1.0 vs 0.x`).
  - `permission_allowed` och `get_metadata` — kvar för Datasette 0.x men **no-ops på 1.0** (hookspecs borttagna; pluggy ignorerar tyst en hook utan matchande spec, så pluginet fungerar på båda versionerna).

### Configuration System

Resolution priority (highest first):
1. `data/metadata.json` - Specific overrides for individual databases/tables
2. `datasette_svk_layout/data/svk_metadata.db` - SQLite-databas med databas-nivå metadata och behörigheter
3. `datasette_svk_layout/data/database_types.json` - Shared config per database type
4. Default Datasette templates

> **1.0-avvikelse:** På Datasette 1.0 matar `get_metadata`-hooken INTE längre Datasette core
> (hookspec borttagen). Titlar/beskrivningar från `svk_metadata.db` renderas därför via
> mall-hjälparna (`get_formatted_database_title`/`-description`) som läser `MetadataDB` **direkt**.
> Följd: prioritetsordningen ovan (metadata.json > SQLite) gäller INTE för renderade titlar på
> 1.0 — mall-hjälpen kollar bara SQLite, aldrig metadata.json. Behörigheter (`allow`/`allow_sql`)
> som förr injicerades via `get_metadata` prövas inte heller längre den vägen — se
> `## Datasette 1.0 vs 0.x`.

### Database Type System

Manages 500+ organizational databases. Database names follow pattern `{type}_{orgnr}` (e.g. `aveny_2520026135`).

- `datasette_svk_layout/data/database_types.json` - Type definitions (titles, descriptions, queries, permissions, template mappings)
- `datasette_svk_layout/data/units.json` - Organizational unit registry (orgnr -> name)
- `DatabaseTypeTemplateLoader` in `__init__.py` - Routes database-specific template requests to type-level templates (supports `database-`, `query-`, `table-`, `row-` prefixes with per-name mappings)

### Key Files

| File | Purpose |
|------|---------|
| `datasette_svk_layout/__init__.py` | Plugin hooks, template loader, helper functions |
| `datasette_svk_layout/templates/base.html` | Main layout with navigation and footer |
| `datasette_svk_layout/static/app.css` | Complete styling with Svenska kyrkan branding |
| `datasette_svk_layout/data/database_types.json` | Type-based config with template mappings |
| `datasette_svk_layout/data/units.json` | Org unit registry (orgnr -> name) |
| `data/metadata.json` | Datasette metadata for specific databases |
| `datasette_svk_layout/data/svk_metadata.db` | SQLite metadata store (databas-nivå, skapas automatiskt) |
| `datasette_svk_layout/metadata_db.py` | MetadataDB-klass: schema, CRUD, allow-dict assemblering, cache |
| `datasette_svk_layout/admin_routes.py` | Admin-UI route handlers med behörighetskontroll |
| `datasette_svk_layout/migrate_metadata.py` | Migreringsskript för import från metadata.json |
| `datasette_svk_layout/create_record_fts.py` | Skapa FTS5-index för record-tabellen i Public_360-databaser |
| `dev_plugins/dev_mock_actor.example.py` | Mock actor plugin for local development |

### Database Types

| Type | Template prefix | Description |
|------|----------------|-------------|
| `Public_360` | `database-Public_360-type`, `query-Public_360-type-*`, `row-Public_360-type-*` | Ärendehandlingar (ERMS) med ärendesök, handlingssök, diariesökning och sekretessfiltrering |
| `aveny` | `database-aveny-type` | Ekonomihandlingar |
| `lonehandlingar` | `database-lonehandlingar-type`, `query-lonehandlingar-type-*`, `row-lonehandlingar-type-*` | Lönehandlingar med personsök, periodsök, lönespecifikationer |
| `hrm` | `database-hrm-type`, `query-hrm-type-*`, `row-hrm-type-*` | HR Personalsystem med personsök, reseräkningar, tidsredovisning och dokumentservering |

HRM-, lonehandlingar- och Public_360-typerna har per-query och per-row template-mappningar i `database_types.json` under `templates.queries` och `templates.rows`.

### Public_360 Type (ERMS-baserad)

Ärendehandlingar från ärendehanteringssystem baserat på Svenska kyrkans ERMS-anpassning. Framtida ERMS-typer från andra system kommer att ha liknande struktur.

**Databasstruktur:**
- `aggregation` (ärenden), `record` (handlingar), `appendix` (filer på disk via path), `agents`/`agenttypes`, `diary`, `restriction`, `dates`, `keyword`, `extraids`, `othertitles`
- Kopplingstabeller: `aggregationagent`, `recordagent`, `aggregationkeyword`, `recordkeyword`, `aggregationrestriction`, `recordrestriction`
- FTS5-index: `aggregation_fts` (inbyggd), `record_fts` (skapas via `create_record_fts.py`)
- Agent-tabellens kolumner: `id`, `idNumber`, `name`, `type_id` (FK). Agenttypes: `id`, `type` (OBS: inte `agenttype`)

**Sekretessmodell — två behörighetsroller:**
- `access.search_casefiles` — kan söka men sekretessmarkerade uppgifter filtreras:
  - Sekretessmarkerat ärende (`confidential=1` eller har `aggregationrestriction`): titel → "Skyddat ärende", agenter (sender/receiver/other/counterpart) → "Skyddad", alla handlingar döljs helt
  - Sekretessmarkerad handling (under icke-sekretessärende): titel → "Skyddad handling", agenter maskerade, bilagor dolda
- `access.search_casefiles_confidentiality` — full åtkomst till allt

**Sökfunktioner (3 sökvägar på landningssidan):**
- Fritextsök ärenden (canned query `SokArenden` → `aggregation_fts`)
- Diarielista med per-diarium sökning (inline `sql()` i diary row-template)
- Fritextsök handlingar (canned query `SokHandlingar` → `record_fts`)

**FTS-sökmönster:** `'"' || replace(trim(:text), ' ', '" "') || '"*'` — citerar varje ord (skyddar bindestreck) + prefix-wildcard på sista termen.

**LIMIT:** 200 för sökresultat, 500 för diarielista, med informationsmeddelande.

**FTS-script:** `python -m datasette_svk_layout.create_record_fts <db_path>` skapar `record_fts` med triggers.

### Template Helper Functions (available in Jinja2)

- `sql(query, params)` - Execute SQL in templates (async, requires database context)
- `get_unit_name(orgnr)` - Look up organizational unit name
- `get_database_type_config(database)` - Get type config for a database
- `get_column_label(database, table, column)` - Get readable column title

### Document Serving Routes

`register_routes` hook provides:
- `/{database}/dokument/{id}` - Serve documents from `AnstallningDokument` table
- `/{database}/bilaga/{id}` - Serve attachments from `Bilaga` table
- `/{database}/lonespec/{lonekorning_id}` - Serve salary specification HTML from `lonekorningar.lonespec` column

Dokument/bilaga auto-detects content type from magic bytes (PDF, images, Office docs). Lonespec serverar HTML-innehåll direkt (kräver URL-encoding av ID pga specialtecken).

### SQLite Metadata Database

`datasette_svk_layout/data/svk_metadata.db` lagrar databas-nivå metadata som alternativ till poster i `metadata.json`. Skapas automatiskt vid uppstart.

**Schema:**
- `database_metadata` - title, description, source, license per databas
- `database_permissions` - normaliserad tabell med (database_name, action, actor_key, actor_value)

Behörighetsrader lagras per `action`:
- `action = "view-database"` → enhetsspärr (`organizations_ids`)
- `action = "execute-sql"` → roller (`permissions`)

På Datasette 1.0 läses dessa rader av `permission_resources_sql`-hooken och används för aktiv
behörighetsprövning (se `## Datasette 1.0 vs 0.x`). De assembleras fortfarande till Datasettes
`allow`/`allow_sql`-dict av `get_metadata`-hooken, men den vägen prövas inte längre på 1.0 (används
bara av Datasette 0.x på `main`).

**Konfiguration** (valfri, i metadata.json):
```json
{"plugins": {"datasette-svk-layout": {"metadata_db_path": "datasette_svk_layout/data/svk_metadata.db"}}}
```

**MetadataDB-klass** (`metadata_db.py`): Singleton med rekursionsskydd (pga `get_metadata` hook → `plugin_config` → `metadata` → `get_metadata`). Använder direkt `sqlite3` (inte async) eftersom `get_metadata` hook är synkron.

**Viktigt om typkonvertering:** `database_permissions` lagrar alla `actor_value` som strängar. `_coerce_value()` konverterar numeriska strängar tillbaka till `int` vid utläsning, eftersom Datasette gör typkänslig matchning av allow-dicts mot actor-fält (t.ex. `organizations_ids` är heltal i actor).

**Extern integration (ESSArch):** Externa system kan registrera nya databaser direkt via `sqlite3` utan beroende på pluginet:
```python
import sqlite3
conn = sqlite3.connect("datasette_svk_layout/data/svk_metadata.db")
conn.execute(
    "INSERT OR IGNORE INTO database_permissions (database_name, action, actor_key, actor_value) VALUES (?, 'view-database', 'organizations_ids', ?)",
    (database_name, str(org_id))
)
conn.commit()
```
Notera: `actor_value` ska alltid lagras som sträng — konvertering till rätt typ sker vid utläsning.

### Admin-UI

Routes under `/-/admin/` (kräver admin-behörighet):
- `/-/admin/databases` - Lista/sök databaser
- `/-/admin/databases/{name}` - Redigera metadata och behörigheter
- `/-/admin/databases/{name}/delete` - Ta bort databaspost
- `/-/admin/import` - Importera från metadata.json (förhandsgranskning + import)
- `/-/admin/site` - Redigera startsidans "Om tjänsten"-text och snabblänkar
- `/-/admin/news` - Lista, skapa, redigera och ta bort nyheter
- `/-/admin/news/new` - Skapa ny nyhet
- `/-/admin/news/{id}` - Redigera nyhet
- `/-/admin/news/{id}/delete` - Ta bort nyhet

### Dynamiskt startsideinnehåll

Startsidans "Om tjänsten"-text, snabblänkar och nyhetsflöde lagras i `svk_metadata.db`:
- `site_content` — nyckel-värde (t.ex. `about_title`, `about_html`)
- `site_links` — snabblänkar med titel, URL och sorteringsordning
- `site_news` — nyheter med titel, HTML-body, författarnamn och datum

Data injiceras som `site_about`, `site_links`, `site_news` via `extra_template_vars()`. Fallback till hårdkodade standardvärden om databasen är tom.

**Migrering från metadata.json:**
```bash
python -m datasette_svk_layout.migrate_metadata [metadata_path] [db_path]
```

## Datasette 1.0 vs 0.x

Datasette 1.0 tog bort flera hooks/API:er som pluginet förlitade sig på under 0.x. Den här
branchen (0.5.x) hanterar det; `main` (0.4.x) är kvar på 0.x-beteendet.

### Behörighetsmodell — `permission_resources_sql`

I 1.0 togs hooken `permission_allowed` bort och `allow`-block som levereras via `get_metadata`
prövas inte längre (behörigheter flyttades från *metadata* till *config*). All enforcement sker
därför via den nya hooken `permission_resources_sql(datasette, actor, action)`:

- Hooken returnerar `PermissionSQL`-objekt vars SQL ger rader `(parent, child, allow, reason)`.
  Bygg dem enkelt med `PermissionRowCollector` från `datasette.default_permissions.helpers`.
- **Prejudens:** DENY slår ALLOW på samma nivå; child (tabell) slår parent (databas) slår global.
  Datasettes default ger global ALLOW för view-*, så pluginet emitterar **bara DENY-rader** — en
  parent-nivå DENY (`parent=db, child=NULL`) slår default-ALLOW och kaskaderar dessutom till alla
  tabeller och execute-sql på samma databas.
- **view-database:** DENY om aktörens `organizations_ids` inte matchar databasens registrerade enhet
  i `svk_metadata.db` (matchas med `datasette.utils.actor_matches_allow`). DENY även om databasens
  typ kräver tabellroller aktören helt saknar (döljer databasen ur indexet).
- **Tabellåtgärder** (`view-table` + mutationer): DENY om aktören saknar samtliga roller i tabellens
  `allow.permissions` i `database_types.json`.
- **execute-sql:** DENY om aktören inte matchar databasens `execute-sql`-roller.

De gamla `permission_allowed`-enhetstesterna (`tests/test_svk_layout.py`) testar en funktion som är
en no-op på 1.0 men behålls (giltiga för 0.x). Den faktiska 1.0-spärren täcks av
`test_permission_resources_sql_org_gating` (integrationstest med signerad `ds_actor`-cookie:
rätt enhet 200, fel enhet 403; hoppas över på 0.x).

### Mall-kontext (context-API ändrat i 1.0)

Överskrivna mallar anpassades till 1.0:s kontext:
- `database_color` är nu en **sträng**, inte en callable → `{{ database_color }}` (inte
  `database_color(database)`) i `table.html`, `row.html`, `database-aveny-type.html`.
- `table_actions()` → `actions()` i `table.html`.
- `filtered_table_rows_count` → `count` i `table.html`.

### Övrigt

- `get_metadata`-hooken finns inte längre i core; `datasette.metadata()` är borttagen (ersatt av
  async `get_database_metadata()`/`get_instance_metadata()`).
- `/-/plugins.json` returnerar `{"ok": true, "plugins": [...]}` (dict), inte en ren lista.
- Kör lokalt: `datasette` med plugin installerat mot `datasette>=1.0a0` (`--memory`-flagga, inte
  positionsargumentet `memory` som fanns i 0.x).

## Known Limitations

- `database.html` template cannot access individual table metadata directly
- Some templates have limited access to certain metadata structures
- **1.0:** config-prioriteten "metadata.json > SQLite" gäller inte för renderade titlar (mall-hjälpen
  läser bara `svk_metadata.db`) — se `### Configuration System`. Ej åtgärdad.

## Future Work

- ADFS integration for user-specific database filtering
- Additional database type configurations
- CSS: app.css defines `--svk-*` brand variables and generic aliases (`--primary-color` etc.) for type-specific templates
