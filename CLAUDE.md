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
- **Plugin hooks** in `__init__.py`: `canned_queries`, `extra_template_vars`, `permission_allowed`, `prepare_jinja2_environment`, `register_routes`

### Three-layer Configuration System

Resolution priority (highest first):
1. `data/metadata.json` - Specific overrides for individual databases/tables
2. `datasette_svk_layout/data/database_types.json` - Shared config per database type
3. Default Datasette templates

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
| `dev_plugins/dev_mock_actor.example.py` | Mock actor plugin for local development |

### Database Types

| Type | Template prefix | Description |
|------|----------------|-------------|
| `aveny` | `database-aveny-type` | Ekonomihandlingar |
| `lonehandlingar` | — | Lonehandlingar |
| `vips` | — | Vips Online |
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

## Known Limitations

- `database.html` template cannot access individual table metadata directly
- Some templates have limited access to certain metadata structures

## Future Work

- ADFS integration for user-specific database filtering
- Additional database type configurations (vips, etc.)
- CSS: app.css defines `--svk-*` brand variables and generic aliases (`--primary-color` etc.) for type-specific templates
