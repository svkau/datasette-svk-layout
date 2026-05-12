# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Datasette plugin called `datasette-svk-layout` that provides a custom layout/theme for SvK's Datasette instance. It overrides Datasette's default templates and styling to provide a customized user interface.

## Development Commands

### Setup
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate
pip install -e '.[test]'
```

### Testing
```bash
# Run all tests
python -m pytest

# Run tests with async support (configured in pyproject.toml)
pytest
```

### Installation Testing
```bash
# Install the plugin in development mode
pip install -e .

# Test plugin installation
datasette install datasette-svk-layout
```

## Architecture

### Plugin Structure
- **Entry Point**: Registered as `svk_layout` in `pyproject.toml` entry points, pointing to `datasette_svk_layout` module
- **Templates**: Complete set of Jinja2 templates in `datasette_svk_layout/templates/` that override Datasette's default templates
- **Static Assets**: CSS, JavaScript, and other static files in `datasette_svk_layout/static/`
- **Hook Integration**: Uses Datasette's plugin hook system (minimal Python code in `__init__.py`)

### Key Components
- `base.html` - Main layout template with navigation, Swedish "Meny" text, and footer structure
- `app.css` - Custom CSS starting with Eric Meyer's reset, provides complete styling override
- Template partials (`_*.html`) - Reusable components for facets, crumbs, CodeMirror integration, etc.
- Database templates (`database.html`, `table.html`, `query.html`) - Views for different Datasette pages

### Plugin Mechanism
This is a template-only Datasette plugin that works by:
1. Being registered as a Datasette plugin via entry points
2. Providing complete template overrides for all major Datasette views
3. Serving custom static assets via Datasette's static file serving
4. Using Datasette's template inheritance and context system

The plugin requires no custom Python hooks beyond basic registration - it works entirely through template replacement and static asset serving.

## Recent Updates (Session Summary)

### 🎨 UI Modernization Completed
- **Header Enhancement**: Added Svenska kyrkan logo and gradient styling with official brand colors
- **Color System**: Implemented comprehensive Svenska kyrkan color palette in CSS custom properties
- **Card-based Design**: Transformed database listings, table listings, and query listings into modern card layouts
- **Form Improvements**: Enhanced SQL forms, buttons, and input styling with Swedish translations
- **Table Enhancements**: Added scrollable containers, improved typography, and better mobile responsiveness
- **Content Layout**: Improved spacing, typography scale, and content sectioning throughout

### 🌍 Swedish Localization
- **Breadcrumbs**: "home" → "🏠 Hem"
- **SQL Interface**: "Format SQL" → "Formatera SQL", "Run SQL" → "Kör SQL"
- **Hide/Show**: "hide" → "dölj", "show" → "visa" (with proper spacing)
- **Export Links**: Added icons 📋 for JSON and 📊 for CSV exports
- **UI Elements**: Comprehensive Swedish translation throughout interface

### 📊 Metadata Integration
- **metadata.json**: Created comprehensive metadata file with Swedish titles and descriptions for:
  - Databases: employees (Personalregister), sakila (Demonstrationsdatabas)
  - Tables: departments (Avdelningar), employees (Anställda), etc.
  - Queries: current_employees (Nuvarande anställda), department_overview (Avdelningsöversikt)
- **Dynamic Display**: Templates now show metadata-driven titles and descriptions on:
  - Index page: Database cards with Swedish titles and descriptions
  - Table pages: Swedish table titles and descriptions
  - Query pages: Swedish query titles and descriptions
- **Card Layouts**: Created matching card designs for both tables and canned queries with distinct styling

### 🔧 Technical Improvements
- **Template Context**: Solved metadata access patterns for different page contexts
- **CSS Architecture**: Organized styles with proper cascade and custom properties
- **Export Enhancement**: Visual icons for data export formats
- **Query Cards**: Added card-based layout for canned queries with descriptions

### 📋 Known Issues & Limitations
- **Metadata Context**: database.html template cannot access individual table metadata (same "out of context" issue as index.html initially had)
- **Template Scope**: Some templates have limited access to certain metadata structures

### 🚀 Future Scalability Discussion
- **Problem Identified**: Need to support 500+ databases (one per organizational unit) with identical structure
- **Proposed Solution**: Template-based metadata system with:
  - Unit registry file (`units.json`) with organizational numbers and names
  - Database naming pattern recognition (`sakila_{organisationsnummer}`)
  - Dynamic metadata application based on templates
  - ADFS integration for user-specific database filtering
  
 
### Future ideas on Metadata 
  1. Plugin enhancement to make metadata accessible in all template contexts
  2. Template context injection to ensure metadata is available everywhere
  3. Dynamic lookup system that works with your future 500+ database scaling needs

  We can revisit this when we work on the broader scalability solution for your organizational unit databases. For now, the interface maintains consistency where metadata access works (individual pages) while keeping
  maintenance simple.

### 📁 Files Modified
- `templates/index.html` - Database cards with metadata
- `templates/database.html` - Table and query cards with metadata
- `templates/table.html` - Table titles and descriptions from metadata
- `templates/query.html` - Query titles and descriptions from metadata  
- `templates/_crumbs.html` - Swedish breadcrumbs
- `static/app.css` - Complete styling overhaul with Svenska kyrkan branding
- `data/metadata.json` - Comprehensive metadata with Swedish translations

The project now provides a fully modernized, Swedish-localized Datasette interface with Svenska kyrkan branding and professional card-based layouts throughout.

## Latest Update - Plugin Installation & Database Types System

### 🔧 Plugin Installation Issue Resolved
- **Problem**: Plugin installation failing with `ModuleNotFoundError: No module named 'datasette_svk_layout'`
- **Root Cause**: Setuptools package discovery was not properly including the plugin module files
- **Solution**: Fixed `pyproject.toml` configuration to explicitly declare packages:
  ```toml
  [tool.setuptools]
  packages = ["datasette_svk_layout"]
  ```
- **Verification**: Plugin now installs correctly and loads in Datasette without errors

### 🎯 Database Types Configuration System
Created a comprehensive configuration system for managing 500+ organizational databases through database types:

#### **Configuration File**: `data/database_types.json`
- **Purpose**: Define titles, descriptions, queries, and permissions for entire database types
- **Structure**: Database type → templates → automatic unit name insertion
- **Scalability**: Configure once for all databases of same type (e.g., all "economics" databases)

#### **Features Implemented**:
1. **Dynamic Titles**: `"Ekonomisystem - {unit_name}"` → `"Ekonomisystem - Nationell nivå"`
2. **Dynamic Descriptions**: Templates with unit-specific content
3. **Canned Queries**: Auto-generated queries for each database type:
   - Economics: Budget summary, monthly transactions, top customers
   - Salaries: Salary overview, new hires, department costs
4. **Permission System**: Database-level and table-level access controls
5. **Template Functions**: New Jinja2 functions for accessing configurations

#### **Plugin Enhancement**:
- **New Python Functions**: Added template functions for unit name lookup and configuration
- **Startup Hook**: Injects database type configurations into Datasette metadata
- **Permission Hook**: Applies access controls based on database types
- **Template Updates**: Enhanced `index.html` and `database.html` to use configuration system

#### **Working Examples**:
- **Economics DB**: Shows "Ekonomisystem - Nationell nivå" with 3 auto-generated queries
- **Salaries DB**: Shows "Lönesystem - Sunne pastorat" with 3 auto-generated queries  
- **Query Cards**: Display with "Automatisk" badge to distinguish from manual queries
- **Unit Names**: Properly integrated from `units.json` (organizational registry)

#### **Benefits for 500+ Database Scaling**:
- ✅ **One Configuration**: Single file controls all databases of same type
- ✅ **Automatic Application**: No need to edit metadata.json for each database
- ✅ **Dynamic Content**: Unit names automatically inserted everywhere
- ✅ **Permission Control**: Role-based access by database type
- ✅ **Query Management**: Standard queries applied to all relevant databases

#### **Files Added/Modified**:
- `data/database_types.json` - Central configuration for database types
- `datasette_svk_layout/__init__.py` - Enhanced with configuration system
- `templates/database.html` - Updated to show dynamic queries and titles
- `templates/index.html` - Updated to use database type configurations

The system successfully demonstrates scalable management of organizational databases while maintaining the existing metadata.json system for specific overrides. Tested and verified working with automatic query generation and unit-specific naming.

## Latest Session - Template Type Mapping System & UI Refinements

### 🎯 Template Type Mapping System - IMPLEMENTED ✅

Successfully implemented the template type mapping system that was proposed in the previous session!

#### **How It Works**:

**Custom Jinja2 Template Loader**: Created `DatabaseTypeTemplateLoader` class in `__init__.py` that intercepts Jinja2's template loading process:

```python
class DatabaseTypeTemplateLoader(BaseLoader):
    """Intercepts template loading and redirects to type-specific templates"""

    def get_source(self, environment, template):
        # When Datasette tries to load database-aveny_2520026135.html
        # Our loader checks database_types.json for aveny type config
        # If "templates" mapping exists, loads database-aveny-type.html instead
```

**Template Resolution Flow**:
```
User visits: /aveny_2520026135
  ↓
Datasette tries: database-aveny_2520026135.html
  ↓
Our loader intercepts and checks database_types.json
  ↓
Finds: "aveny" type with templates.database = "database-aveny-type.html"
  ↓
Loads: database-aveny-type.html instead
```

**Configuration in database_types.json**:
```json
{
  "aveny": {
    "title_template": "Ekonomihandlingar - {unit_name}",
    "description_template": "Arkiverade uttag från ekonomisystem",
    "templates": {
      "database": "database-aveny-type.html"
    },
    "queries": { ... },
    "tables": { ... }
  }
}
```

#### **Features Implemented**:

1. **Custom Template Loader**: Registered via `prepare_jinja2_environment` hook
2. **Pattern Matching**: Extracts database type from database name (`aveny_2520026135` → `aveny`)
3. **Template Mapping**: Supports `database`, `table`, and `query` template types
4. **Fallback System**: If no type template exists, uses standard Datasette templates
5. **Demo Template**: Created `database-aveny-type.html` with green notice box showing it's active

#### **Benefits**:

- ✅ **One template for all databases of same type**: `database-aveny-type.html` applies to all 500+ aveny databases
- ✅ **Type-specific layouts**: Can create unique interfaces for economics, HR, membership databases
- ✅ **Centralized maintenance**: Update one file, affects all databases of that type
- ✅ **No duplication**: No need to create 500 copies of the same template
- ✅ **Automatic application**: New databases automatically use type templates

#### **Example Use Cases**:

- **Economics databases** (`aveny_*`): Budget widgets, financial KPIs, expense charts
- **HR databases** (`lonehandlingar_*`): Privacy warnings, salary analytics, org charts
- **Membership databases** (`vips_*`): Contact forms, donation tracking, event calendars

#### **Files Modified**:
- `datasette_svk_layout/__init__.py` - Added `DatabaseTypeTemplateLoader` class and `prepare_jinja2_environment` hook
- `data/database_types.json` - Added `"templates": {"database": "database-aveny-type.html"}` to aveny type
- `datasette_svk_layout/templates/database-aveny-type.html` - Created demo type-specific template with visual indicator

### 🎨 UI Refinements

#### **View Cards Styling**:
- Updated view cards to match table card styling
- Views now display with same card layout as tables
- Added support for titles and descriptions from `database_types.json` for views
- Removed custom pink gradient background from view cards for consistency

#### **Column Title Display**:
- Created custom `_table.html` template to display column titles from `database_types.json`
- Column headers now show readable titles instead of raw database column names
- Template uses `get_column_label(database, table, column.name)` function
- Maintains all table functionality (sorting, filtering, etc.)

#### **Breadcrumb Improvements**:
- Breadcrumbs now use formatted titles at all levels (database and table)
- Database breadcrumbs show formatted titles from database_types configuration
- Table breadcrumbs show metadata titles instead of raw table names

#### **Description Blocks**:
- Added consistent description styling across database.html, table.html, and query.html
- All description blocks use same gradient background and wine-red border
- Replaced license/source information blocks with descriptions from database_types.json

#### **Index Page Layout**:
- Replaced license/source section with two-column "Om tjänsten" (About) and "Snabblänkar" (Quick Links) layout
- Added grid-based responsive design for site information

#### **SQL View Example**:
- Created `budgetsammanfattning` view in aveny database as working example
- View aggregates budget data by year and category
- Demonstrates how SQL views appear in Datasette interface

### 🔧 Technical Architecture

The plugin now has three layers of configuration:

1. **metadata.json** (Optional): Specific overrides for individual databases/tables
2. **database_types.json** (Type-level): Shared configuration for all databases of same type
3. **Type-specific templates** (Layout): Custom layouts for entire database types

**Resolution Priority**:
```
Specific metadata.json override
  ↓ (if not found)
database_types.json configuration
  ↓ (if not found)
Default values / standard templates
```

### 📁 Key Files

#### Configuration:
- `datasette_svk_layout/data/database_types.json` - Type-based configuration with template mappings
- `datasette_svk_layout/data/units.json` - Organizational unit registry (orgnr → name mapping)
- `data/metadata.json` - Optional specific overrides

#### Templates:
- `templates/database.html` - Standard database page template
- `templates/database-aveny-type.html` - Type-specific template for aveny databases
- `templates/table.html` - Standard table page template
- `templates/_table.html` - Custom table rendering with column titles
- `templates/query.html` - Query results template
- `templates/_crumbs.html` - Breadcrumb navigation with formatted titles

#### Python:
- `datasette_svk_layout/__init__.py` - Plugin hooks, template loader, helper functions

### 🎯 System Scalability

The system is now fully prepared for 500+ organizational databases:

- ✅ **Metadata scaling**: database_types.json handles all databases of same type
- ✅ **Template scaling**: Type-specific templates apply automatically
- ✅ **Query scaling**: Canned queries auto-generated for each database type
- ✅ **Permission scaling**: Role-based access controls by type
- ✅ **Naming scaling**: Unit names automatically inserted from units.json

### 📝 Future Enhancements (Not Yet Implemented)

- ADFS integration for user-specific database filtering
- Table-level and query-level type-specific templates
- Additional database type configurations (vips, member databases, etc.)
- Custom widgets and charts for specific database types
- Advanced permission rules and field-level access controls