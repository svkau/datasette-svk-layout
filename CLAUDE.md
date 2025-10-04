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

### 📁 Files Modified
- `templates/index.html` - Database cards with metadata
- `templates/database.html` - Table and query cards with metadata
- `templates/table.html` - Table titles and descriptions from metadata
- `templates/query.html` - Query titles and descriptions from metadata  
- `templates/_crumbs.html` - Swedish breadcrumbs
- `static/app.css` - Complete styling overhaul with Svenska kyrkan branding
- `data/metadata.json` - Comprehensive metadata with Swedish translations

The project now provides a fully modernized, Swedish-localized Datasette interface with Svenska kyrkan branding and professional card-based layouts throughout.