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