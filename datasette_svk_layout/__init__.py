import json
import os
import re
from pathlib import Path
from datasette import hookimpl
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

@hookimpl
def database_actions(datasette, actor, database):
    """Add database-specific actions based on database type configuration"""
    # This could be used to add type-specific actions to database pages
    return []

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
def extra_template_vars(datasette):
    """Add template functions for unit name lookups and database configuration"""
    # Clear caches to reload configuration on each request (for development)
    clear_caches()

    # Create a wrapper function that has access to datasette
    def get_query_desc(database_name, query_name):
        return get_query_description(datasette, database_name, query_name)

    return {
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

    def get_source(self, environment, template):
        """
        Intercept template loading and redirect to type-specific templates when configured.
        """
        # Check if this is a database-specific template
        # Pattern: database-{dbname}.html, table-{dbname}-{tablename}.html, query-{dbname}-{queryname}.html

        if template.startswith('database-') and template.endswith('.html'):
            # Extract database name from template
            db_name = template[9:-5]  # Remove 'database-' and '.html'

            # Get database type configuration
            db_type = get_database_type(db_name)
            db_config = get_database_config(db_name)

            if db_config and 'templates' in db_config and 'database' in db_config['templates']:
                # Try to load the type-specific template
                type_template = db_config['templates']['database']
                try:
                    return self.fallback_loader.get_source(environment, type_template)
                except TemplateNotFound:
                    pass  # Fall through to default behavior

        elif template.startswith('table-') and template.endswith('.html'):
            # Extract database and table name from template
            # Format: table-{dbname}-{tablename}.html
            parts = template[6:-5].split('-', 1)  # Remove 'table-' and '.html', split on first dash
            if len(parts) == 2:
                db_name, table_name = parts

                db_type = get_database_type(db_name)
                db_config = get_database_config(db_name)

                if db_config and 'templates' in db_config and 'table' in db_config['templates']:
                    type_template = db_config['templates']['table']
                    try:
                        return self.fallback_loader.get_source(environment, type_template)
                    except TemplateNotFound:
                        pass

        elif template.startswith('query-') and template.endswith('.html'):
            # Extract database and query name from template
            # Format: query-{dbname}-{queryname}.html
            parts = template[6:-5].split('-', 1)  # Remove 'query-' and '.html', split on first dash
            if len(parts) == 2:
                db_name, query_name = parts

                db_type = get_database_type(db_name)
                db_config = get_database_config(db_name)

                if db_config and 'templates' in db_config and 'query' in db_config['templates']:
                    type_template = db_config['templates']['query']
                    try:
                        return self.fallback_loader.get_source(environment, type_template)
                    except TemplateNotFound:
                        pass

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
