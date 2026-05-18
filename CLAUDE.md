# CLAUDE.md

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
- **Plugin hooks** in `__init__.py`: `startup`, `get_metadata`, `canned_queries`, `extra_template_vars`, `permission_allowed`, `prepare_jinja2_environment`, `register_routes`

### Configuration System

Resolution priority (highest first):
1. `data/metadata.json` - Specific overrides for individual databases/tables
2. `datasette_svk_layout/data/svk_metadata.db` - SQLite-databas med databas-nivå metadata och behörigheter (injiceras via `get_metadata` hook)
3. `datasette_svk_layout/data/database_types.json` - Shared config per database type
4. Default Datasette templates

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
| `dev_plugins/dev_mock_actor.example.py` | Mock actor plugin for local development |

### Database Types

| Type | Template prefix | Description |
|------|----------------|-------------|
| `Public_360` | — | Ärendehandlingar (20 tabeller + 7 dolda) |
| `aveny` | `database-aveny-type` | Ekonomihandlingar |
| `lonehandlingar` | — | Lonehandlingar |
| `hrm` | `database-hrm-type`, `query-hrm-type-*`, `row-hrm-type-*` | HR Personalsystem med personsok, reserakningar, tidsredovisning och dokumentservering |

HRM-typen har per-query och per-row template-mappningar i `database_types.json` under `templates.queries` och `templates.rows`.

### Template Helper Functions (available in Jinja2)

- `sql(query, params)` - Execute SQL in templates (async, requires database context)
- `get_unit_name(orgnr)` - Look up organizational unit name
- `get_database_type_config(database)` - Get type config for a database
- `get_column_label(database, table, column)` - Get readable column title

### Document Serving Routes

`register_routes` hook provides:
- `/{database}/dokument/{id}` - Serve documents from `AnstallningDokument` table
- `/{database}/bilaga/{id}` - Serve attachments from `Bilaga` table

Auto-detects content type from magic bytes (PDF, images, Office docs).

### SQLite Metadata Database

`datasette_svk_layout/data/svk_metadata.db` lagrar databas-nivå metadata som alternativ till poster i `metadata.json`. Skapas automatiskt vid uppstart.

**Schema:**
- `database_metadata` - title, description, source, license per databas
- `database_permissions` - normaliserad tabell med (database_name, action, actor_key, actor_value)

Behörighetsrader assembleras till Datasettes `allow`-dict:
- `action = "view-database"` → `allow` i metadata
- `action = "execute-sql"` → `allow_sql` i metadata

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

**Migrering från metadata.json:**
```bash
python -m datasette_svk_layout.migrate_metadata [metadata_path] [db_path]
```

## Known Limitations

- `database.html` template cannot access individual table metadata directly
- Some templates have limited access to certain metadata structures

## Future Work

- ADFS integration for user-specific database filtering
- Additional database type configurations
- CSS: app.css defines `--svk-*` brand variables and generic aliases (`--primary-color` etc.) for type-specific templates
