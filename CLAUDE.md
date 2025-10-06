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
- `data/database_types_example.json` - Complete example with permissions
- `datasette_svk_layout/__init__.py` - Enhanced with configuration system
- `templates/database.html` - Updated to show dynamic queries and titles
- `templates/index.html` - Updated to use database type configurations

The system successfully demonstrates scalable management of organizational databases while maintaining the existing metadata.json system for specific overrides. Tested and verified working with automatic query generation and unit-specific naming.

#### Future work on templates
I ask: Don't code anything now, but I would like to ask you about templates. I datasette you can name templates specific to a certain database. If I wanted special templates for the economics database, I'd hade to make 500 
  copies of those templates. It's the same problem as with metadata.json. Do you think we could do the same here: One set of templates for all economics databases?

Claude answers:  Excellent question! You're absolutely right - this is exactly the same scalability problem we just solved for metadata.json, but for templates.

  🎯 The Template Problem:

  Datasette's built-in template system allows:
  - database-economics_2520026135.html (specific to one database)
  - table-economics_2520026135-budgets.html (specific to one table)
  - But you'd need 500 copies for 500 economics databases

  ✅ Yes, We Can Solve This!

  We could extend our database types system to handle templates using the same approach:

  Concept: Template Type Mapping

  database_types.json:
  {
    "economics": {
      "templates": {
        "database": "database-economics-type.html",
        "table": "table-economics-type.html", 
        "query": "query-economics-type.html"
      }
    }
  }

  How It Would Work:

  1. Plugin Hook: Intercept Datasette's template resolution
  2. Type Detection: Check if database matches a type pattern (e.g., economics_*)
  3. Template Mapping: Redirect to the type-specific template
  4. Fallback: Use standard templates if no type match

  Template Resolution Order:

  economics_2520026135 → database-economics-type.html
  salaries_2520037173 → database-salaries-type.html
  unknown_database → database.html (standard)

  Benefits:

  - ✅ One template controls all 500 economics databases
  - ✅ Type-specific layouts (economics vs salaries vs members)
  - ✅ Centralized maintenance
  - ✅ Automatic application to new databases
  - ✅ Custom functionality per database type

  Implementation Options:

  1. Template Loader Hook: Custom Jinja2 template loader
  2. Template Path Manipulation: Modify template resolution in plugin
  3. Dynamic Template Selection: Hook into Datasette's template choosing

  Example Use Cases:

  - Economics databases: Special charts, budget widgets, financial KPIs
  - HR databases: Privacy warnings, role-based field hiding
  - Member databases: Contact forms, donation tracking, event calendars

  This would be a powerful extension of our database types system - making both metadata AND templates scalable for organizational databases!