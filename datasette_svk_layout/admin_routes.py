import json
from datasette.utils.asgi import Response, Forbidden


def _get_metadata_db():
    from datasette_svk_layout import _get_metadata_db as get_db
    return get_db()


async def _check_admin(datasette, request):
    """Check if current actor has admin permission."""
    actor = request.actor if hasattr(request, 'actor') else None
    if actor is None:
        return False
    return await datasette.permission_allowed(actor, "admin", default=False)


async def _render(datasette, request, template, context):
    """Render a template with admin context."""
    body = await datasette.render_template(template, context, request=request)
    return Response.html(body)


async def admin_databases(scope, receive, datasette, request):
    """List all databases in the metadata store."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    search = request.args.get("search", "")
    db_type = request.args.get("type", "")

    databases = mdb.list_databases(
        search=search or None,
        db_type=db_type or None,
    )

    # Add permission info to each database
    for db in databases:
        perms = mdb.get_database_permissions(db["database_name"])
        db["permissions"] = perms

    return await _render(datasette, request, "admin_databases.html", {
        "databases": databases,
        "search": search,
        "db_type": db_type,
    })


async def admin_database_edit(scope, receive, datasette, request):
    """Edit metadata and permissions for a single database."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    database_name = request.url_vars["database_name"]

    if request.method == "POST":
        post_vars = await request.post_vars()

        # Save metadata
        mdb.set_database_metadata(
            database_name,
            title=post_vars.get("title") or None,
            description=post_vars.get("description") or None,
            source=post_vars.get("source") or None,
            license=post_vars.get("license") or None,
        )

        # Save permissions for each action
        for action in ("view-database", "execute-sql"):
            roles_str = post_vars.get(f"perm_{action}_roles", "").strip()
            if roles_str:
                roles = [r.strip() for r in roles_str.split(",") if r.strip()]
                mdb.set_database_permissions(database_name, action, {"roles": roles})
            else:
                mdb.set_database_permissions(database_name, action, None)

        return Response.redirect(f"/-/admin/databases/{database_name}?saved=1")

    # GET: load current values
    metadata = mdb.get_database_metadata(database_name) or {}
    permissions = mdb.get_database_permissions(database_name)
    saved = request.args.get("saved", "")

    return await _render(datasette, request, "admin_database_edit.html", {
        "database_name": database_name,
        "metadata": metadata,
        "permissions": permissions,
        "saved": saved,
        "is_new": not metadata,
    })


async def admin_database_delete(scope, receive, datasette, request):
    """Delete a database entry from the metadata store."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    if request.method != "POST":
        return Response.text("Method not allowed", status=405)

    mdb = _get_metadata_db()
    database_name = request.url_vars["database_name"]
    mdb.delete_database(database_name)
    return Response.redirect("/-/admin/databases?deleted=1")


async def admin_import(scope, receive, datasette, request):
    """Import database-level metadata from metadata.json."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    result = None
    preview = None
    error = None

    if request.method == "POST":
        post_vars = await request.post_vars()
        action = post_vars.get("action", "preview")

        metadata_json = datasette._metadata_local
        if not metadata_json:
            error = "Ingen metadata.json hittades."
        elif action == "preview":
            # Show what would be imported
            databases = metadata_json.get("databases", {})
            preview = []
            for db_name, db_config in sorted(databases.items()):
                entry = {"name": db_name}
                entry["title"] = db_config.get("title", "")
                entry["description"] = db_config.get("description", "")
                entry["has_allow"] = "allow" in db_config
                entry["has_allow_sql"] = "allow_sql" in db_config
                preview.append(entry)
        elif action == "import":
            result = mdb.import_from_metadata_json(metadata_json)
    else:
        # GET: show info about what can be imported
        metadata_json = datasette._metadata_local
        if metadata_json:
            db_count = len(metadata_json.get("databases", {}))
        else:
            db_count = 0

    return await _render(datasette, request, "admin_import.html", {
        "result": result,
        "preview": preview,
        "error": error,
        "db_count": db_count if request.method == "GET" else None,
    })
