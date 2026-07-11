import json
import os
import re
from pathlib import Path
from datasette import hookimpl
from datasette.utils.asgi import Response
import copy
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader, TemplateNotFound
from jinja2.loaders import BaseLoader
from datasette_svk_layout.metadata_db import MetadataDB

import sqlite3

# Cache for units data and database types
_units_cache = None
_database_types_cache = None
_database_types_mtime = None
_metadata_db_instance = None

# Optional path to the svk-admin config store (svk_admin.db). When set (via the
# datasette-svk-layout ``config_db_path`` plugin config, resolved at startup),
# database-type configuration is read live from that store's ``database_types``
# table instead of the bundled snapshot — so edits made in the admin SPA take
# public effect. Falls back to the bundled database_types.json when unset.
_config_db_path = None

def clear_caches():
    """Clear all caches to reload data"""
    global _units_cache, _database_types_cache, _database_types_mtime
    _units_cache = None
    _database_types_cache = None
    _database_types_mtime = None
    if _metadata_db_instance:
        _metadata_db_instance._invalidate_cache()


_metadata_db_initializing = False

def _get_metadata_db(datasette=None):
    """Get or create the MetadataDB singleton."""
    global _metadata_db_instance, _metadata_db_initializing
    if _metadata_db_instance is not None:
        return _metadata_db_instance

    # Guard against recursion: get_metadata hook -> _get_metadata_db -> plugin_config -> metadata -> get_metadata
    if _metadata_db_initializing:
        return None
    _metadata_db_initializing = True

    try:
        db_path = str(Path(__file__).parent / "data" / "svk_metadata.db")
        if datasette:
            plugin_config = datasette.plugin_config("datasette-svk-layout") or {}
            db_path = plugin_config.get("metadata_db_path", db_path)

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _metadata_db_instance = MetadataDB(db_path)
        return _metadata_db_instance
    finally:
        _metadata_db_initializing = False

def load_units_data():
    """Load and cache units.json data"""
    global _units_cache
    if _units_cache is None:
        units_file = Path(__file__).parent / "data" / "units.json"
        _units_cache = {}
        try:
            with open(units_file, 'r', encoding='utf-8') as f:
                _units_cache = {str(unit['orgnr']): unit['namn'] for unit in json.load(f)}
        except Exception:
            pass
    return _units_cache

def _load_types_from_config_db(path):
    """Read {type_name: config} from an svk-admin svk_admin.db config store."""
    types = {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        for type_name, config in conn.execute(
            "SELECT type_name, config FROM database_types"
        ):
            try:
                types[type_name] = json.loads(config)
            except (ValueError, TypeError):
                pass
    finally:
        conn.close()
    return types


def load_database_types():
    """Load and cache database type configuration.

    When ``config_db_path`` is configured (svk-admin's editable store), types are
    read live from its ``database_types`` table and the cache is busted whenever
    that file's mtime changes, so admin edits take public effect without a
    restart. Otherwise the bundled ``database_types.json`` snapshot is used.
    """
    global _database_types_cache, _database_types_mtime

    if _config_db_path and os.path.exists(_config_db_path):
        try:
            mtime = os.path.getmtime(_config_db_path)
            if _database_types_cache is None or mtime != _database_types_mtime:
                _database_types_cache = _load_types_from_config_db(_config_db_path)
                _database_types_mtime = mtime
            return _database_types_cache
        except Exception:
            pass  # fall back to the bundled snapshot below

    if _database_types_cache is None:
        types_file = Path(__file__).parent / "data" / "database_types.json"
        _database_types_cache = {}
        try:
            with open(types_file, 'r', encoding='utf-8') as f:
                _database_types_cache = json.load(f)
        except Exception:
            pass
    return _database_types_cache

def get_database_config(database_name):
    """Get configuration for a database type"""
    db_type = get_database_type(database_name)
    database_types = load_database_types()
    return database_types.get(db_type, {})

def get_formatted_database_title(database_name):
    """Get formatted database title using type configuration"""
    # Check SQLite metadata first
    mdb = _get_metadata_db()
    if mdb:
        meta = mdb.get_database_metadata(database_name)
        if meta and meta.get('title'):
            return meta['title']

    unit_name = get_unit_name(database_name)
    db_config = get_database_config(database_name)

    if unit_name and 'title_template' in db_config:
        return db_config['title_template'].format(unit_name=unit_name)
    elif unit_name:
        db_type = get_database_type(database_name)
        return f"{db_type.title()} - {unit_name}"
    return None

def get_formatted_database_description(database_name):
    """Get formatted database description using type configuration"""
    # Check SQLite metadata first
    mdb = _get_metadata_db()
    if mdb:
        meta = mdb.get_database_metadata(database_name)
        if meta and meta.get('description'):
            return meta['description']

    unit_name = get_unit_name(database_name)
    db_config = get_database_config(database_name)

    if unit_name and 'description_template' in db_config:
        return db_config['description_template'].format(unit_name=unit_name)
    return None

def get_formatted_table_info(database_name, table_name):
    """Get formatted table title and description using type configuration"""
    unit_name = get_unit_name(database_name)
    db_config = get_database_config(database_name)

    if unit_name and 'tables' in db_config and table_name in db_config['tables']:
        table_config = db_config['tables'][table_name]
        title = table_config.get('title', table_name)
        description = table_config.get('description', '').format(unit_name=unit_name)
        return {'title': title, 'description': description}

    return {'title': table_name, 'description': None}

def get_unit_name(database_name):
    """Extract organisationsnummer from database name and return unit name"""
    orgnr = extract_orgnr(database_name)
    if orgnr:
        units = load_units_data()
        return units.get(orgnr, None)
    return None

def extract_orgnr(database_name):
    """Extract organisationsnummer from database name"""
    match = re.search(r'_(\d+)(?:\.db)?$', database_name)
    return match.group(1) if match else None

def get_database_type(database_name):
    """Extract database type from database name.

    Matches against known types in database_types.json (longest match first)
    to handle types with underscores like 'Public_360'.
    """
    database_types = load_database_types()
    for type_name in sorted(database_types.keys(), key=len, reverse=True):
        if database_name.startswith(type_name + '_'):
            return type_name
    # Fallback: first segment before underscore
    if '_' in database_name:
        return database_name.split('_')[0]
    return database_name

@hookimpl
def startup(datasette):
    """Initialize metadata database on startup."""
    _get_metadata_db(datasette)

    # Resolve the optional svk-admin config store path once. When set, database
    # type configuration is read live from it (see load_database_types).
    global _config_db_path
    plugin_config = datasette.plugin_config("datasette-svk-layout") or {}
    _config_db_path = plugin_config.get("config_db_path")


@hookimpl
def get_metadata(datasette, key, database, table):
    """Inject database-level metadata from SQLite store."""
    if table is not None:
        return {}
    db = _get_metadata_db(datasette)
    if db is None:
        return {}
    return db.get_all_metadata_as_datasette_dict()


@hookimpl
def canned_queries(datasette, database, actor):
    """Inject canned queries from database type configuration"""
    db_config = get_database_config(database)
    unit_name = get_unit_name(database)

    if not db_config or not unit_name or 'queries' not in db_config:
        return {}

    queries = {}
    for query_name, query_config in db_config['queries'].items():
        formatted_query = copy.deepcopy(query_config)
        if 'title' in formatted_query:
            formatted_query['title'] = formatted_query['title'].format(unit_name=unit_name)
        if 'description' in formatted_query:
            formatted_query['description'] = formatted_query['description'].format(unit_name=unit_name)
        queries[query_name] = formatted_query

    return queries


def get_column_label(database_name, table_name, column_name):
    """Get column label from database_types.json configuration"""
    db_config = get_database_config(database_name)

    if 'tables' in db_config and table_name in db_config['tables']:
        table_config = db_config['tables'][table_name]
        if 'columns' in table_config and column_name in table_config['columns']:
            col_config = table_config['columns'][column_name]
            if 'title' in col_config and col_config['title'] != '[COLUMN TITLE]':
                return col_config['title']

    return column_name

def get_query_description(datasette, database_name, query_name):
    """Get query description from metadata (injected by startup hook)"""
    try:
        metadata = datasette._metadata
        if ('databases' in metadata and
            database_name in metadata['databases'] and
            'queries' in metadata['databases'][database_name] and
            query_name in metadata['databases'][database_name]['queries']):
            query_meta = metadata['databases'][database_name]['queries'][query_name]
            return query_meta.get('description', None)
    except:
        pass
    return None

@hookimpl
def extra_template_vars(datasette, database):
    """Add template functions for unit name lookups and database configuration"""
    # Clear caches to reload configuration on each request (for development)
    clear_caches()

    # Create a wrapper function that has access to datasette
    def get_query_desc(database_name, query_name):
        return get_query_description(datasette, database_name, query_name)

    async def sql(query, params=None):
        """Execute SQL in templates. Requires Jinja2 async mode (used by Datasette)."""
        if database:
            db = datasette.get_database(database)
            result = await db.execute(query, params or {})
            return [dict(row) for row in result.rows]
        return []

    def get_site_about():
        mdb = _get_metadata_db()
        if not mdb:
            return {"title": "Om tjänsten", "html": ""}
        return {
            "title": mdb.get_site_content("about_title", "") or "Om tjänsten",
            "html": mdb.get_site_content("about_html", ""),
        }

    def get_site_links():
        mdb = _get_metadata_db()
        return mdb.get_site_links() if mdb else []

    def get_site_news():
        mdb = _get_metadata_db()
        return mdb.get_site_news(limit=5) if mdb else []

    return {
        "sql": sql,
        "get_unit_name": get_unit_name,
        "extract_orgnr": extract_orgnr,
        "get_database_type": get_database_type,
        "get_formatted_database_title": get_formatted_database_title,
        "get_formatted_database_description": get_formatted_database_description,
        "get_formatted_table_info": get_formatted_table_info,
        "get_formatted_queries": get_formatted_queries,
        "get_column_label": get_column_label,
        "get_query_description": get_query_desc,
        "get_database_type_config": get_database_config,
        "site_about": get_site_about(),
        "site_links": get_site_links(),
        "site_news": get_site_news(),
    }

_TABLE_ACTIONS = [
    "view-table", "insert-row", "update-row", "delete-row",
    "drop-table", "create-table", "alter-table",
]


def _type_required_permissions(database_name):
    """Return the union of role-permissions required by any table of a database's type.

    An actor must hold at least one of these to see the database at all.
    Empty set means the database type imposes no table-level role restriction.
    """
    db_config = get_database_config(database_name)
    required = set()
    for table_config in db_config.get("tables", {}).values():
        required.update(table_config.get("allow", {}).get("permissions", []))
    return required


@hookimpl
def permission_resources_sql(datasette, actor, action):
    """Datasette 1.0 permission enforcement.

    In Datasette 1.0 the ``permission_allowed`` hook was removed and ``allow``
    blocks delivered via ``get_metadata`` are no longer consulted for permission
    checks (they moved to ``config``). Enforcement therefore lives here for the
    1.0 branch. The legacy ``permission_allowed`` hook below is kept for
    Datasette 0.x — on each version the non-matching hook is silently ignored by
    pluggy.

    We emit DENY rows only. In the 1.0 permission model DENY beats ALLOW at the
    same level and a resource-level rule (parent/child) beats the global default
    ALLOW, so a per-database or per-table DENY overrides Datasette's default
    "allow" without us having to re-grant the common case.

    - view-database: actor's ``organizations_ids`` must match the database's
      registered org(s) in ``svk_metadata.db`` AND, if the database registered
      åtkomstroller (view-database ``permissions``), the actor must hold at least
      one of them; databases whose type requires table roles the actor entirely
      lacks are also hidden. A view-database DENY cascades to tables and SQL.
    - table actions (view-table + mutations): actor must hold at least one of the
      roles configured for the table in ``database_types.json``.
    - execute-sql: actor must match the database's ``allow_sql`` roles.
    """
    if action != "view-database" and action != "execute-sql" and action not in _TABLE_ACTIONS:
        return None

    try:
        from datasette.utils import actor_matches_allow
        from datasette.default_permissions.helpers import PermissionRowCollector
    except ImportError:
        # Datasette < 1.0 — this hook does not exist there; permission_allowed
        # (below) handles enforcement instead.
        return None

    actor_perms = set(actor.get("permissions", [])) if actor else set()
    mdb = _get_metadata_db(datasette)
    db_entries = mdb.get_all_metadata_as_datasette_dict().get("databases", {}) if mdb else {}
    collector = PermissionRowCollector(prefix="svk")

    # Organizations gating: any database whose registered organizations_ids do
    # not match the actor is denied at the database (parent) level. A
    # parent-level DENY also cascades to every table and to execute-sql on that
    # database, so a wrong-enhet actor is blocked from the database page, its
    # tables and its SQL alike.
    # The view-database allow may carry two independent gates:
    #   - organizations_ids (enhet), and/or
    #   - permissions (åtkomstroller, skrivna av svk-admin).
    # They combine with AND: the actor must match the enhet AND hold at least
    # one åtkomstroll. actor_matches_allow is OR *across keys*, so we must
    # evaluate each key on its own dict rather than the merged allow — otherwise
    # matching either the enhet or a role would wrongly grant access.
    db_denied = {}
    for database_name in datasette.databases:
        if database_name == "_internal":
            continue
        allow = db_entries.get(database_name, {}).get("allow") or {}
        org_rule = (
            {"organizations_ids": allow["organizations_ids"]}
            if allow.get("organizations_ids")
            else None
        )
        role_rule = (
            {"permissions": allow["permissions"]} if allow.get("permissions") else None
        )
        if org_rule and not actor_matches_allow(actor, org_rule):
            db_denied[database_name] = "svk: fel enhet (organizations_ids)"
        elif role_rule and not actor_matches_allow(actor, role_rule):
            db_denied[database_name] = "svk: saknar åtkomstroll (permissions)"

    for database_name in datasette.databases:
        if database_name == "_internal":
            continue

        if database_name in db_denied:
            collector.add(database_name, None, False, db_denied[database_name])
            continue

        if action == "view-database":
            # Hide the database when its type requires table roles the actor lacks entirely.
            required = _type_required_permissions(database_name)
            if required and not actor_perms.intersection(required):
                collector.add(database_name, None, False, "svk: saknar roll för databasens tabeller")

        elif action in _TABLE_ACTIONS:
            db_config = get_database_config(database_name)
            for table_name, table_config in db_config.get("tables", {}).items():
                required = table_config.get("allow", {}).get("permissions")
                if required and not actor_perms.intersection(required):
                    collector.add(database_name, table_name, False, "svk: saknar roll för tabell")

        elif action == "execute-sql":
            allow_sql = db_entries.get(database_name, {}).get("allow_sql")
            if allow_sql and not actor_matches_allow(actor, allow_sql):
                collector.add(database_name, None, False, "svk: saknar execute-sql roll")

    return collector.to_permission_sql()


@hookimpl
def permission_allowed(datasette, actor, action, resource):
    """
    Apply database type permissions from database_types.json.

    Strategy:
    - Database-level permissions (execute-sql, download) → metadata.json handles these
    - Table-level permissions (view-table, insert-row, etc.) → database_types.json handles these
    - This allows per-database unit_id in metadata.json + per-type roles in database_types.json

    NOTE: This hook only fires under Datasette 0.x. Under Datasette 1.0 it is
    silently ignored (the hookspec was removed); ``permission_resources_sql``
    above handles enforcement there instead.
    """

    # Hide database from index if actor lacks all table-level permissions
    if action == "view-database" and resource:
        database_name = resource if isinstance(resource, str) else resource[0]
        db_config = get_database_config(database_name)
        all_permissions = set()
        for table_config in db_config.get("tables", {}).values():
            perms = table_config.get("allow", {}).get("permissions", [])
            all_permissions.update(perms)
        if all_permissions:
            if not actor:
                return False
            actor_permissions = actor.get("permissions", [])
            if not any(p in all_permissions for p in actor_permissions):
                return False

    table_actions = [
        "view-table", "insert-row", "update-row", "delete-row",
        "drop-table", "create-table", "alter-table"
    ]

    if action in table_actions and resource:
        # Resource format: (database, table) for table-level permissions
        if len(resource) >= 2:
            database_name = resource[0]
            table_name = resource[1]

            db_config = get_database_config(database_name)

            # Check if this table has specific permissions in database_types.json
            if 'tables' in db_config and table_name in db_config['tables']:
                table_config = db_config['tables'][table_name]

                if 'allow' in table_config:
                    allow_config = table_config['allow']

                    # "permissions" key = general restriction on all actions
                    if 'permissions' in allow_config:
                        required = allow_config['permissions']
                        if not actor:
                            return False
                        actor_permissions = actor.get('permissions', [])
                        return any(perm in required for perm in actor_permissions)

    # Fall back to default behavior (metadata.json handles it)
    # This allows database-level permissions to be controlled by metadata.json
    return None

def get_formatted_queries(database_name):
    """Get formatted canned queries for a database"""
    unit_name = get_unit_name(database_name)
    db_config = get_database_config(database_name)

    if not unit_name or 'queries' not in db_config:
        return {}

    formatted_queries = {}
    for query_name, query_config in db_config['queries'].items():
        formatted_query = copy.deepcopy(query_config)

        # Format title and description with unit name
        if 'title' in formatted_query:
            formatted_query['title'] = formatted_query['title'].format(unit_name=unit_name)
        if 'description' in formatted_query:
            formatted_query['description'] = formatted_query['description'].format(unit_name=unit_name)

        formatted_queries[query_name] = formatted_query

    return formatted_queries

class DatabaseTypeTemplateLoader(BaseLoader):
    """
    Custom Jinja2 template loader that resolves database-specific templates to type-specific templates.

    For example:
    - database-aveny_2520026135.html → database-aveny-type.html (if configured)
    - table-aveny_2520026135-budgetar.html → table-aveny-type.html (if configured)
    """

    def __init__(self, fallback_loader):
        self.fallback_loader = fallback_loader

    def _try_load(self, environment, template_name):
        """Try to load a template, return None if not found."""
        try:
            return self.fallback_loader.get_source(environment, template_name)
        except TemplateNotFound:
            return None

    def _resolve_type_template(self, environment, db_name, prefix, item_name=None):
        """
        Resolve a type-specific template for a database.

        For 'database' prefix: checks templates.database
        For 'query'/'table'/'row' prefix: checks templates.queries/tables/rows dict
        for per-name mapping first, then falls back to templates.query/table/row.
        """
        db_config = get_database_config(db_name)
        if not db_config or 'templates' not in db_config:
            return None

        templates = db_config['templates']

        if prefix == 'database':
            if 'database' in templates:
                return self._try_load(environment, templates['database'])
        else:
            # Check per-name mapping first (e.g. templates.queries.Personer)
            plural_map = {'query': 'queries', 'row': 'rows', 'table': 'tables'}
            plural = plural_map.get(prefix, prefix + 's')
            if item_name and plural in templates:
                name_map = templates[plural]
                if isinstance(name_map, dict) and item_name in name_map:
                    result = self._try_load(environment, name_map[item_name])
                    if result:
                        return result

            # Fall back to generic type template (e.g. templates.query)
            singular = prefix.rstrip('s') if prefix.endswith('s') else prefix
            if singular in templates:
                return self._try_load(environment, templates[singular])

        return None

    def get_source(self, environment, template):
        """
        Intercept template loading and redirect to type-specific templates when configured.

        Handles: database-{db}.html, table-{db}-{name}.html, query-{db}-{name}.html, row-{db}-{name}.html
        """
        for prefix in ('database', 'table', 'query', 'row'):
            tag = prefix + '-'
            if template.startswith(tag) and template.endswith('.html'):
                inner = template[len(tag):-5]

                if prefix == 'database':
                    result = self._resolve_type_template(environment, inner, 'database')
                else:
                    parts = inner.split('-', 1)
                    if len(parts) == 2:
                        db_name, item_name = parts
                        result = self._resolve_type_template(environment, db_name, prefix, item_name)
                    else:
                        result = None

                if result:
                    return result
                break

        # Fall back to default loader
        return self.fallback_loader.get_source(environment, template)

    def list_templates(self):
        """List all available templates from fallback loader"""
        return self.fallback_loader.list_templates()

@hookimpl
def prepare_jinja2_environment(env):
    """
    Customize Jinja2 environment to use our custom template loader.
    This enables database type-specific template resolution.
    """
    # Wrap the existing loader with our custom loader
    env.loader = DatabaseTypeTemplateLoader(env.loader)


# === Document serving ===

def detect_content_type(data):
    """Detect file type from content (magic bytes)."""
    if not data:
        return "application/octet-stream", ".bin"
    if data[:4] == b'%PDF':
        return "application/pdf", ".pdf"
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png", ".png"
    elif data[:2] == b'\xff\xd8':
        return "image/jpeg", ".jpg"
    elif data[:4] == b'GIF8':
        return "image/gif", ".gif"
    elif data[:2] == b'PK':
        if b'word/' in data[:2000]:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
        elif b'xl/' in data[:2000]:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
        elif b'ppt/' in data[:2000]:
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"
        return "application/zip", ".zip"
    elif data[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        return "application/msword", ".doc"
    return "application/octet-stream", ".bin"


async def _serve_blob(datasette, request, table, id_column, file_column, name_column, not_found_msg):
    """Shared logic for serving binary blobs from database tables."""
    database = request.url_vars["database"]
    row_id = request.url_vars["doc_id"] if "doc_id" in request.url_vars else request.url_vars["bilaga_id"]

    db = datasette.get_database(database)
    result = await db.execute(
        f"SELECT [{file_column}], [{name_column}] FROM [{table}] WHERE [{id_column}] = :id",
        {"id": row_id}
    )
    row = result.first()

    if not row or not row[file_column]:
        return Response.text(not_found_msg, status=404)

    fil_data = row[file_column]
    if not isinstance(fil_data, bytes):
        fil_data = bytes(fil_data)

    original_filnamn = row[name_column] or "dokument"
    content_type, ext = detect_content_type(fil_data)
    base_name = os.path.splitext(original_filnamn)[0]
    filnamn = base_name + ext

    inline_types = ["application/pdf", "image/png", "image/jpeg", "image/gif"]
    disposition = "inline" if content_type in inline_types else "attachment"

    return Response(
        body=fil_data,
        status=200,
        headers={
            "Content-Type": content_type,
            "Content-Disposition": f'{disposition}; filename="{filnamn}"',
        },
        content_type=content_type,
    )


async def serve_document(scope, receive, datasette, request):
    return await _serve_blob(
        datasette, request,
        table="AnstallningDokument", id_column="Id",
        file_column="Fil", name_column="Filnamn",
        not_found_msg="Dokument hittades inte"
    )


async def serve_bilaga(scope, receive, datasette, request):
    return await _serve_blob(
        datasette, request,
        table="Bilaga", id_column="Id",
        file_column="Fil", name_column="Filnamn",
        not_found_msg="Bilaga hittades inte"
    )


async def serve_lonespec(scope, receive, datasette, request):
    from urllib.parse import unquote
    database = request.url_vars["database"]
    lonekorning_id = unquote(request.url_vars["lonekorning_id"])

    db = datasette.get_database(database)
    result = await db.execute(
        "SELECT lonespec, fornamn, efternamn, lonekorningsnummer FROM lonekorningar WHERE lonekorning_id = :id",
        {"id": lonekorning_id}
    )
    row = result.first()

    if not row or not row["lonespec"]:
        return Response.text("Lönespecifikation hittades inte", status=404)

    html_content = row["lonespec"]
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8")

    return Response(
        body=html_content,
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content_type="text/html; charset=utf-8",
    )


@hookimpl
def register_routes():
    from datasette_svk_layout.admin_routes import (
        admin_databases,
        admin_database_edit,
        admin_database_delete,
        admin_import,
        admin_site,
        admin_news_list,
        admin_news_new,
        admin_news_edit,
        admin_news_delete,
    )
    return [
        (r"^/(?P<database>[^/]+)/dokument/(?P<doc_id>[^/]+)$", serve_document),
        (r"^/(?P<database>[^/]+)/bilaga/(?P<bilaga_id>[^/]+)$", serve_bilaga),
        (r"^/(?P<database>[^/]+)/lonespec/(?P<lonekorning_id>.+)$", serve_lonespec),
        (r"^/-/admin/databases$", admin_databases),
        (r"^/-/admin/databases/(?P<database_name>[^/]+)/delete$", admin_database_delete),
        (r"^/-/admin/databases/(?P<database_name>[^/]+)$", admin_database_edit),
        (r"^/-/admin/import$", admin_import),
        (r"^/-/admin/site$", admin_site),
        (r"^/-/admin/news/new$", admin_news_new),
        (r"^/-/admin/news/(?P<news_id>\d+)/delete$", admin_news_delete),
        (r"^/-/admin/news/(?P<news_id>\d+)$", admin_news_edit),
        (r"^/-/admin/news$", admin_news_list),
    ]
