import json
import os
import re
from pathlib import Path
from datasette import hookimpl
from datasette.utils.asgi import Response
import copy
from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader, TemplateNotFound
from jinja2.loaders import BaseLoader

# Cache for units data and database types  
_units_cache = None
_database_types_cache = None

def clear_caches():
    """Clear all caches to reload data"""
    global _units_cache, _database_types_cache
    _units_cache = None
    _database_types_cache = None

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

def load_database_types():
    """Load and cache database_types.json data"""
    global _database_types_cache
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
    """Extract database type from database name"""
    if '_' in database_name:
        return database_name.split('_')[0]
    return database_name

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
        "get_query_description": get_query_desc
    }

@hookimpl
def permission_allowed(datasette, actor, action, resource):
    """
    Apply database type permissions from database_types.json.

    Strategy:
    - Database-level permissions (execute-sql, download) → metadata.json handles these
    - Table-level permissions (view-table, insert-row, etc.) → database_types.json handles these
    - This allows per-database unit_id in metadata.json + per-type roles in database_types.json
    """

    # Only handle table-level and row-level permissions from database_types.json
    # Let metadata.json handle database-level permissions (execute-sql, download)
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

                if 'allow' in table_config and action in table_config['allow']:
                    allowed = table_config['allow'][action]

                    # If it's a boolean, return it directly
                    if isinstance(allowed, bool):
                        return allowed

                    # If it's a list of roles, check if actor has required roles
                    if isinstance(allowed, list) and actor:
                        actor_roles = actor.get('roles', [])
                        # User needs at least one of the allowed roles
                        return any(role in allowed for role in actor_roles)

                    # If configured but actor is None, deny access
                    if isinstance(allowed, list) and not actor:
                        return False

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


@hookimpl
def register_routes():
    return [
        (r"^/(?P<database>[^/]+)/dokument/(?P<doc_id>[^/]+)$", serve_document),
        (r"^/(?P<database>[^/]+)/bilaga/(?P<bilaga_id>[^/]+)$", serve_bilaga),
    ]
