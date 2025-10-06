import json
import os
import re
from pathlib import Path
from datasette import hookimpl
import copy

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
        # Try multiple possible paths for units.json
        possible_paths = [
            Path(__file__).parent.parent / "data" / "units.json",  # Development path
            Path.cwd() / "data" / "units.json",  # Current working directory
            Path("/home/henrik/dev-projects/datasette-svk-layout/data/units.json")  # Absolute path
        ]
        
        _units_cache = {}
        for units_file in possible_paths:
            if units_file.exists():
                try:
                    with open(units_file, 'r', encoding='utf-8') as f:
                        _units_cache = {str(unit['orgnr']): unit['namn'] for unit in json.load(f)}
                    break
                except Exception as e:
                    continue
    return _units_cache

def load_database_types():
    """Load and cache database_types.json data"""
    global _database_types_cache
    if _database_types_cache is None:
        # Try multiple possible paths for database_types.json
        possible_paths = [
            Path(__file__).parent.parent / "data" / "database_types.json",  # Development path
            Path.cwd() / "data" / "database_types.json",  # Current working directory
            Path("/home/henrik/dev-projects/datasette-svk-layout/data/database_types.json")  # Absolute path
        ]
        
        _database_types_cache = {}
        for types_file in possible_paths:
            if types_file.exists():
                try:
                    with open(types_file, 'r', encoding='utf-8') as f:
                        _database_types_cache = json.load(f)
                    break
                except Exception as e:
                    continue
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
    
    # Debug logging (remove in production)
    print(f"DEBUG: table_name={table_name}, unit_name={unit_name}")
    print(f"DEBUG: db_config keys={list(db_config.keys()) if db_config else 'None'}")
    if 'tables' in db_config:
        print(f"DEBUG: available tables={list(db_config['tables'].keys())}")
    
    if unit_name and 'tables' in db_config and table_name in db_config['tables']:
        table_config = db_config['tables'][table_name]
        title = table_config.get('title', table_name)
        description = table_config.get('description', '').format(unit_name=unit_name)
        print(f"DEBUG: Found config for {table_name}: title={title}, description={description}")
        return {'title': title, 'description': description}
    
    print(f"DEBUG: No config found for {table_name}, using default")
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
def startup(datasette):
    """Inject database type configurations into datasette metadata at startup"""
    # Get all databases and inject type-based configurations
    for db_name in datasette.databases.keys():
        if db_name == "_internal":
            continue
            
        db_config = get_database_config(db_name)
        unit_name = get_unit_name(db_name)
        
        if db_config and unit_name:
            # Inject queries into database metadata
            if 'queries' in db_config:
                db_metadata = datasette._metadata.get("databases", {}).get(db_name, {})
                db_queries = db_metadata.get("queries", {})
                
                # Add formatted queries from database types
                for query_name, query_config in db_config['queries'].items():
                    formatted_query = copy.deepcopy(query_config)
                    
                    # Format title and description with unit name
                    if 'title' in formatted_query:
                        formatted_query['title'] = formatted_query['title'].format(unit_name=unit_name)
                    if 'description' in formatted_query:
                        formatted_query['description'] = formatted_query['description'].format(unit_name=unit_name)
                    
                    # Only add if not already defined in metadata
                    if query_name not in db_queries:
                        db_queries[query_name] = formatted_query
                
                # Update metadata
                if db_name not in datasette._metadata.get("databases", {}):
                    datasette._metadata.setdefault("databases", {})[db_name] = {}
                datasette._metadata["databases"][db_name]["queries"] = db_queries

@hookimpl
def database_actions(datasette, actor, database):
    """Add database-specific actions based on database type configuration"""
    # This could be used to add type-specific actions to database pages
    return []

@hookimpl
def extra_template_vars():
    """Add template functions for unit name lookups and database configuration"""
    # Clear caches to reload configuration on each request (for development)
    clear_caches()
    
    return {
        "get_unit_name": get_unit_name,
        "extract_orgnr": extract_orgnr,
        "get_database_type": get_database_type,
        "get_formatted_database_title": get_formatted_database_title,
        "get_formatted_database_description": get_formatted_database_description,
        "get_formatted_table_info": get_formatted_table_info,
        "get_formatted_queries": get_formatted_queries
    }

@hookimpl
def permission_allowed(datasette, actor, action, resource):
    """Apply database type permissions"""
    if action in ["execute-sql", "download"] and resource and len(resource) >= 1:
        database_name = resource[0]
        db_config = get_database_config(database_name)
        
        if 'allow' in db_config and action in db_config['allow']:
            allowed = db_config['allow'][action]
            
            # If it's a boolean, return it directly
            if isinstance(allowed, bool):
                return allowed
            
            # If it's a list, check if actor has required roles
            if isinstance(allowed, list) and actor:
                actor_roles = actor.get('roles', [])
                return any(role in allowed for role in actor_roles)
    
    # Fall back to default behavior
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
